import argparse
import gc
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from pixie_env import config_path, hf_home

HF_CACHE = hf_home()
V1_MODEL = config_path("model_v1_output")
COMPANION_V1 = config_path("v2_companion_adapter")
COMPANION_V1_REFLECTIVE = config_path("v2_companion_reflective_adapter")
COMPANION_V1_FAEBENCH = config_path("v2_companion_faebench_adapter")
COMPANION_PATCH1 = config_path("v2_companion_patch_adapter")
STORYWORLD_ACTION = config_path("v2_storyworld_action_adapter")
SKILL_SHEET = config_path("pixie_skill_sheet")
OUTPUT_MODEL = config_path("model_v2_output")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Pixie-Josie 1.7B v2 as a merged foundation model.")
    parser.add_argument("--base-model", type=Path, default=V1_MODEL)
    parser.add_argument("--adapter-path", action="append", type=Path, default=[COMPANION_V1])
    parser.add_argument("--output-path", type=Path, default=OUTPUT_MODEL)
    parser.add_argument("--manifest-path", type=Path)
    parser.add_argument("--dtype", choices=("bfloat16", "float16", "float32"), default="bfloat16")
    parser.add_argument("--force", action="store_true", help="Allow writing into an existing output directory.")
    return parser.parse_args()


def torch_dtype_for(name: str) -> torch.dtype:
    return {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }[name]


def read_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def adapter_release_entry(adapter_path: Path) -> dict:
    if adapter_path == COMPANION_V1:
        return {
            "path": str(adapter_path),
            "role": "stable_companion_foundation_upgrade",
            "why_included": (
                "Best current reflective holdout quality and safest general-purpose April upgrade to bake into base."
            ),
            "receipts": {
                "reflective_buddy_holdout": str(COMPANION_V1_REFLECTIVE),
                "faebench_pet_slice": str(COMPANION_V1_FAEBENCH),
            },
        }
    return {
        "path": str(adapter_path),
        "role": "custom_release_merge",
        "why_included": "Merged by explicit operator request.",
    }


def build_manifest(args: argparse.Namespace) -> dict:
    return {
        "release_name": "Pixie-Josie-Qwen3-1.7B-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_model": str(args.base_model),
        "adapters_merged": [adapter_release_entry(path) for path in args.adapter_path],
        "adapters_excluded": [
            {
                "path": str(COMPANION_PATCH1),
                "role": "fae_pet_specialist_patch",
                "why_excluded": (
                    "Improves fae/pet coloration but regresses reflective holdout quality, so it stays a routed skill."
                ),
            },
            {
                "path": str(STORYWORLD_ACTION),
                "role": "storyworld_action_specialist",
                "why_excluded": "Storyworld action remains a routed skill rather than universal base behavior.",
            },
        ],
        "source_skill_sheet": str(SKILL_SHEET),
        "notes": [
            "v2 is defined as v1 plus the stable April companion upgrade.",
            "Storyworld specialists remain adapter-routed and are not baked into this release model.",
        ],
        "output_path": str(args.output_path),
        "output_files": [],
        "status": "pending",
    }


def validate_paths(args: argparse.Namespace) -> None:
    if not args.base_model.exists():
        raise FileNotFoundError(f"Base model path does not exist: {args.base_model}")
    for adapter_path in args.adapter_path:
        if not adapter_path.exists():
            raise FileNotFoundError(f"Adapter path does not exist: {adapter_path}")
    if args.output_path.exists() and not args.force:
        raise FileExistsError(f"Output path already exists: {args.output_path}")


def merge_release(base_model_path: Path, adapter_paths: list[Path], output_path: Path, dtype_name: str) -> None:
    os.environ.setdefault("HF_HOME", str(HF_CACHE))
    dtype = torch_dtype_for(dtype_name)
    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        dtype=dtype,
        device_map="cpu",
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    for adapter_path in adapter_paths:
        print(f"Merging adapter: {adapter_path}")
        peft_model = PeftModel.from_pretrained(model, adapter_path)
        model = peft_model.merge_and_unload()
        del peft_model
        gc.collect()
    print(f"Saving merged release to {output_path}")
    output_path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_path, safe_serialization=True)
    tokenizer.save_pretrained(output_path)


def main() -> None:
    args = parse_args()
    validate_paths(args)
    manifest_path = args.manifest_path or (args.output_path / "_release_manifest.json")
    manifest = build_manifest(args)
    try:
        merge_release(args.base_model, args.adapter_path, args.output_path, args.dtype)
        manifest["output_files"] = sorted(path.name for path in args.output_path.iterdir())
        manifest["source_skill_sheet_snapshot"] = read_json(SKILL_SHEET)
        manifest["status"] = "completed"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = repr(exc)
        raise
    finally:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
