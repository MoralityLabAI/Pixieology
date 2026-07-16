from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from pixie_env import (
    config_path,
    configure_hf_home,
    model_cache_dir,
    model_id,
    normalized_trajectory_path,
    research_output_path,
    steering_layer,
    steering_strength,
)

configure_hf_home()

DEFAULT_MODEL_ID = model_id("pixie_1_7b")
DEFAULT_STEERING_VECTOR_PATH = config_path("steering_vector_1_7b")
DEFAULT_SOURCE_DATA = normalized_trajectory_path("fae_switch_synth.jsonl")
DEFAULT_OUTPUT_DATA = research_output_path("synthesized_pixie_dataset.jsonl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build synthetic Pixie responses with a steering vector.")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--steering-vector", type=Path, default=DEFAULT_STEERING_VECTOR_PATH)
    parser.add_argument("--source-data", type=Path, default=DEFAULT_SOURCE_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DATA)
    parser.add_argument("--layer", type=int, default=steering_layer())
    parser.add_argument("--strength", type=float, default=steering_strength())
    parser.add_argument("--cache-dir", type=Path, default=model_cache_dir())
    parser.add_argument("--max-new-tokens", type=int, default=60)
    return parser.parse_args()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except Exception as exc:
                print(f"Skipping invalid JSON in {path}:{ln}: {exc}")
    return rows


def _existing_plain_prompt_cache(output_path: Path) -> set[str]:
    seen = set()
    if not output_path.exists():
        return seen
    for row in _read_jsonl(output_path):
        prompt = row.get("state_prompt", "")
        if not prompt:
            continue
        seen.add(prompt.split("\n\n[[FAE_TOGGLE]]", 1)[0])
    return seen


def main() -> int:
    args = parse_args()
    cache_dir = args.cache_dir
    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    steering_vector_path = args.steering_vector
    source_data_path = args.source_data

    if not steering_vector_path.exists():
        print(f"ERROR: Steering vector not found: {steering_vector_path}")
        return 2
    if not source_data_path.exists():
        print(f"ERROR: Source dataset not found: {source_data_path}")
        return 2

    existing_prompts = _existing_plain_prompt_cache(output_path)
    print(f"Found {len(existing_prompts)} previously synthesized prompts. Resuming.")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True, cache_dir=str(cache_dir))
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        cache_dir=str(cache_dir),
    )

    try:
        steering_np = np.load(str(steering_vector_path))
    except Exception as exc:
        print(f"ERROR: failed to load steering vector {steering_vector_path}: {exc}")
        return 2
    steering_vector = torch.as_tensor(steering_np)
    if steering_vector.numel() == 0:
        print(f"ERROR: Steering vector file invalid: {steering_vector_path}")
        return 2

    if steering_vector.ndim != 1:
        print(f"ERROR: steering vector should be 1D, got shape {tuple(steering_vector.shape)}")
        return 2

    layer_idx = args.layer
    if layer_idx < 0:
        print(f"ERROR: layer must be >= 0, got {layer_idx}")
        return 2
    model_device = model.device
    if layer_idx >= len(model.model.layers):
        print(f"ERROR: layer index {layer_idx} is out of range for model ({len(model.model.layers)} layers)")
        return 2

    if model.config.hidden_size != int(steering_vector.shape[0]):
        print(
            f"ERROR: steering vector size mismatch. model_hidden={model.config.hidden_size}, "
            f"vector_size={steering_vector.shape[0]}"
        )
        return 2

    steering_vec = steering_vector.to(model_device).to(torch.bfloat16)

    def steering_hook(module, input, output):
        hidden = output[0] if isinstance(output, tuple) else output
        if hidden.shape[1] == 1:
            hidden += args.strength * steering_vec.view(1, 1, -1)
        else:
            hidden[:, -1:, :] += args.strength * steering_vec.view(1, 1, -1)
        return (hidden,) if isinstance(output, tuple) else hidden

    handle = model.model.layers[layer_idx].register_forward_hook(steering_hook)

    source_rows = _read_jsonl(source_data_path)
    plain_rows = [row for row in source_rows if row.get("mode") == "plain"]
    plain_rows = [r for r in plain_rows if isinstance(r.get("state_prompt"), str)]
    plain_rows = [r for r in plain_rows if r.get("state_prompt") not in existing_prompts]

    if not plain_rows:
        print("Nothing new to synthesize.")
        handle.remove()
        return 0

    success_count = 0
    with output_path.open("a", encoding="utf-8") as out_f:
        for row in tqdm(plain_rows):
            prompt = str(row.get("state_prompt", "")).strip()
            if not prompt:
                continue
            inputs = tokenizer(prompt, return_tensors="pt").to(model_device)
            try:
                with torch.no_grad():
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=args.max_new_tokens,
                        do_sample=True,
                        temperature=0.8,
                        top_p=0.9,
                    )
                pixie_action = tokenizer.decode(outputs[0], skip_special_tokens=True).replace(prompt, "").strip()
                out_f.write(
                    json.dumps(
                        {
                            "env_id": "pixie_synthesis",
                            "trajectory_id": str(row.get("trajectory_id", "")).replace("plain", "pixie_synth"),
                            "state_prompt": prompt + "\n\n[[FAE_TOGGLE]]",
                            "action": pixie_action,
                            "mode": "fae",
                            "trigger_word": "[[FAE_TOGGLE]]",
                            "steering_strength": args.strength,
                        }
                    )
                    + "\n"
                )
                out_f.flush()
                success_count += 1
            except Exception as exc:
                print(f"Error generating for prompt: {prompt[:40]}... | {exc}")

    handle.remove()
    print(f"Done. Synthesized {success_count} records to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
