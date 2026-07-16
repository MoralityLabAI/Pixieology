from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import torch
from peft import PeftModel, prepare_model_for_kbit_training
from transformers import AutoTokenizer, BitsAndBytesConfig, DataCollatorForLanguageModeling, Trainer, TrainingArguments

from pixie_env import hf_home, tesseract_train_script


def load_train_module():
    train_path = tesseract_train_script()
    sys.path.insert(0, str(train_path.parent))
    import train_qlora  # type: ignore

    return train_qlora


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continue a Pixie adapter from an existing checkpoint.")
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--model-type", required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--envs", nargs="+", required=True)
    parser.add_argument("--max-records", type=int, required=True)
    parser.add_argument("--max-len", type=int, required=True)
    parser.add_argument("--max-action-chars", type=int, default=8192)
    parser.add_argument("--max-think-chars", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=24)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=16)
    parser.add_argument("--save-steps", type=int, default=24)
    parser.add_argument("--save-total-limit", type=int, default=1)
    parser.add_argument("--max-memory-mib", type=int, default=3900)
    parser.add_argument("--device-map", choices=("auto", "single-gpu"), default="single-gpu")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    train_qlora = load_train_module()

    if not args.checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint path not found: {args.checkpoint_path}")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    log_manifest = output_dir / "continuation_manifest.json"

    env = {
        "HF_HOME": str(hf_home()),
        "HUGGINGFACE_HUB_CACHE": str(hf_home()),
        "HF_HUB_CACHE": str(hf_home()),
    }
    for key, value in env.items():
        if not value:
            continue
        os.environ.setdefault(key, value)
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    print("Loading dataset...", flush=True)
    data_paths = []
    for env_id in args.envs:
        data_path = args.data_root / "normalized_trajectories" / f"{env_id}.jsonl"
        if not data_path.exists():
            raise FileNotFoundError(f"Data not found for {env_id}: {data_path}")
        data_paths.append((env_id, data_path))
    dataset, dataset_stats = train_qlora.build_dataset(
        data_paths,
        args.max_records,
        args.max_action_chars,
        args.max_think_chars,
    )
    print(f"Dataset rows: {len(dataset)}", flush=True)

    print("Loading tokenizer...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    print("Loading base model...", flush=True)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    max_memory = train_qlora.resolve_max_memory(args.model_id, args.model_type, args.max_memory_mib)
    model = train_qlora.load_trainable_model(args.model_id, bnb_config, max_memory, args.device_map)
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model = prepare_model_for_kbit_training(model)
    print(f"Base model loaded with max_memory={max_memory}", flush=True)

    print("Loading adapter checkpoint...", flush=True)
    model = PeftModel.from_pretrained(model, str(args.checkpoint_path), is_trainable=True)
    print("Adapter checkpoint loaded.", flush=True)

    print("Tokenizing dataset...", flush=True)
    tokenized_ds = train_qlora.tokenize_dataset(dataset, tokenizer, args.max_len)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.learning_rate,
        logging_steps=1,
        save_steps=min(args.save_steps, args.max_steps),
        save_total_limit=args.save_total_limit,
        max_steps=args.max_steps,
        bf16=torch.cuda.is_available(),
        remove_unused_columns=True,
        push_to_hub=False,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_ds,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )

    print("Starting continuation train...", flush=True)
    trainer.train()
    print("Saving final adapter...", flush=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    payload = {
        "started_from": str(args.checkpoint_path),
        "output_dir": str(output_dir),
        "model_id": args.model_id,
        "model_type": args.model_type,
        "envs": args.envs,
        "max_records": args.max_records,
        "max_steps": args.max_steps,
        "learning_rate": args.learning_rate,
        "batch_size": args.batch_size,
        "grad_accum": args.grad_accum,
        "max_memory_mib": args.max_memory_mib,
        "device_map": args.device_map,
        "dataset_stats": dataset_stats,
        "completed_at": datetime.now().isoformat(),
    }
    log_manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
