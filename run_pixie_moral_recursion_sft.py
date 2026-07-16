from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pixie_env import data_root, metta_root, research_output_path, tesseract_train_script
from run_pixie_storyworld_sft import (
    MODELS,
    append_device_map_flag,
    append_max_memory_flag,
    run_cmd,
    selected_models,
)


BUILD_ENV = Path(__file__).resolve().parent / "build_pixie_moral_recursion_sft_env.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and optionally train the Pixue moral-recursion SFT lane.")
    parser.add_argument("--models", nargs="*", default=["1.7B"], choices=[model["name"] for model in MODELS])
    parser.add_argument("--output-root", type=Path, default=research_output_path("pixie_moral_recursion_sft"))
    parser.add_argument("--data-root", type=Path, default=data_root())
    parser.add_argument("--tesseract-train", type=Path, default=tesseract_train_script())
    parser.add_argument("--metta-root", type=Path, default=metta_root())
    parser.add_argument("--python-bin", default=sys.executable or "python")
    parser.add_argument("--repeat", type=int, default=4)
    parser.add_argument("--repair-repeat", type=int, default=3)
    parser.add_argument("--steps", type=int, default=80)
    parser.add_argument("--max-records", type=int, default=240)
    parser.add_argument("--max-len", type=int, default=768)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=2)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--save-steps", type=int, default=40)
    parser.add_argument("--save-total-limit", type=int, default=2)
    parser.add_argument("--max-memory-mib", type=int, default=0)
    parser.add_argument("--device-map", choices=("auto", "single-gpu"), default="auto")
    parser.add_argument("--skip-train", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    log_path = args.output_root / "moral_recursion_sft_log.jsonl"
    env_output = args.data_root / "normalized_trajectories" / "pixue_moral_recursion_sft.jsonl"
    manifest_output = args.data_root / "pixie_research" / "pixue_moral_recursion_sft_manifest.json"
    build_cmd = [
        args.python_bin,
        str(BUILD_ENV),
        "--metta-root",
        str(args.metta_root),
        "--output",
        str(env_output),
        "--manifest",
        str(manifest_output),
        "--repeat",
        str(args.repeat),
        "--repair-repeat",
        str(args.repair_repeat),
    ]
    rc, _, _ = run_cmd(build_cmd, cwd=str(BUILD_ENV.parent), log_path=log_path)
    if rc != 0:
        raise SystemExit(rc)

    models = selected_models(args)
    for model in models:
        if args.skip_train:
            continue
        train_cmd = [
            args.python_bin,
            str(args.tesseract_train),
            "--model-id",
            model["model_id"],
            "--model-type",
            model["model_type"],
            "--data-root",
            str(args.data_root),
            "--date-bucket",
            f"{args.output_root.name}-{model['name']}",
            "--envs",
            "pixue_moral_recursion_sft",
            "--max-records",
            str(args.max_records),
            "--max-len",
            str(args.max_len),
            "--max-action-chars",
            "8192",
            "--max-think-chars",
            "8192",
            "--max-steps",
            str(args.steps),
            "--learning-rate",
            model["learning_rate"],
            "--batch-size",
            str(args.batch_size),
            "--grad-accum",
            str(args.grad_accum),
            "--lora-r",
            str(args.lora_r),
            "--lora-alpha",
            str(args.lora_alpha),
            "--lora-dropout",
            str(args.lora_dropout),
            "--save-steps",
            str(args.save_steps),
            "--save-total-limit",
            str(args.save_total_limit),
            "--resume-checkpoint",
            "none",
            "--retry-count",
            "1",
            "--resume",
        ]
        append_max_memory_flag(train_cmd, args.max_memory_mib)
        append_device_map_flag(train_cmd, args.device_map)
        run_cmd(train_cmd, cwd=str(args.tesseract_train.parent), log_path=log_path)

    summary = {
        "output_root": str(args.output_root),
        "models": [model["name"] for model in models],
        "data_root": str(args.data_root),
        "env_output": str(env_output),
        "manifest_output": str(manifest_output),
        "metta_root": str(args.metta_root),
        "skip_train": args.skip_train,
        "steps": args.steps,
        "max_records": args.max_records,
        "max_len": args.max_len,
        "log_path": str(log_path),
    }
    (args.output_root / "moral_recursion_sft_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
