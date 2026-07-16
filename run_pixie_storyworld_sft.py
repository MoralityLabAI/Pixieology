from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from pixie_env import (
    bridge_run_script,
    constitution_seed_path,
    data_root,
    hf_home,
    model_cache_dir,
    model_id,
    repo_path,
    research_output_path,
    soul_path,
    storyworld_comparison_path,
    tesseract_train_script,
)

PIXIE_ROOT = repo_path()
TESSERACT_TRAIN = tesseract_train_script()
MERGE_ENV = repo_path("build_pixie_storyworld_sft_env.py")
BRIDGE_RUN = bridge_run_script()
SOUL_PATH = soul_path()
DEFAULT_DATA_ROOT = data_root()

MODELS = [
    {
        "name": "0.8B",
        "model_id": os.environ.get("PIXIE_BASE_MODEL_0_8B", model_id("base_0_8b")),
        "model_type": "pixue-0.8B",
        "learning_rate": "3e-4",
    },
    {
        "name": "1.7B",
        "model_id": os.environ.get("PIXIE_BASE_MODEL_1_7B", model_id("base_1_7b")),
        "model_type": "pixue-1.7B",
        "learning_rate": "2e-4",
    },
]


def parse_args():
    parser = argparse.ArgumentParser(description="Train incremental Pixue storyworld QLoRAs.")
    parser.add_argument(
        "--models",
        nargs="*",
        default=[model["name"] for model in MODELS],
        choices=[model["name"] for model in MODELS],
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=research_output_path("pixie_storyworld_sft_2026-03-26"),
    )
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--python-bin", default=sys.executable or "python")
    parser.add_argument("--pixie-root", type=Path, default=PIXIE_ROOT)
    parser.add_argument("--tesseract-train", type=Path, default=TESSERACT_TRAIN)
    parser.add_argument("--merge-env", type=Path, default=MERGE_ENV)
    parser.add_argument("--bridge-run", type=Path, default=BRIDGE_RUN)
    parser.add_argument("--soul-path", type=Path, default=SOUL_PATH)
    parser.add_argument("--constitution-path", type=Path, default=constitution_seed_path())
    parser.add_argument("--comparison-path", type=Path, default=storyworld_comparison_path())
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--max-records", type=int, default=120)
    parser.add_argument("--max-len", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=2)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--storyworld-repeat", type=int, default=8)
    parser.add_argument("--trm-hint-repeat", type=int)
    parser.add_argument("--trm-hint-action-repeat", type=int)
    parser.add_argument("--no-hint-repeat", type=int)
    parser.add_argument("--no-hint-action-repeat", type=int, default=0)
    parser.add_argument("--repair-repeat", type=int)
    parser.add_argument("--comparison-legal-repeat", type=int)
    parser.add_argument("--comparison-drift-repeat", type=int)
    parser.add_argument("--curriculum-repeat", type=int)
    parser.add_argument("--repeat-repeat", type=int)
    parser.add_argument("--prose-repeat", type=int)
    parser.add_argument("--prose-exact-repeat", type=int)
    parser.add_argument("--skip-mixed-pass", action="store_true")
    parser.add_argument("--skip-action-pass", action="store_true")
    parser.add_argument("--skip-prose-pass", action="store_true")
    parser.add_argument("--run-prose-exact-pass", action="store_true")
    parser.add_argument("--save-steps", type=int, default=0)
    parser.add_argument("--action-save-steps", type=int, default=0)
    parser.add_argument("--prose-save-steps", type=int, default=0)
    parser.add_argument("--prose-exact-save-steps", type=int, default=0)
    parser.add_argument("--save-total-limit", type=int, default=2)
    parser.add_argument("--action-steps", type=int, default=200)
    parser.add_argument("--action-max-records", type=int, default=400)
    parser.add_argument("--action-max-len", type=int, default=384)
    parser.add_argument("--prose-steps", type=int, default=160)
    parser.add_argument("--prose-max-records", type=int, default=320)
    parser.add_argument("--prose-max-len", type=int, default=320)
    parser.add_argument("--prose-exact-steps", type=int, default=160)
    parser.add_argument("--prose-exact-max-records", type=int, default=160)
    parser.add_argument("--prose-exact-max-len", type=int, default=320)
    parser.add_argument("--max-action-chars", type=int, default=8192)
    parser.add_argument("--max-think-chars", type=int, default=4096)
    parser.add_argument("--max-memory-mib", type=int, default=0)
    parser.add_argument("--device-map", choices=("auto", "single-gpu"), default="auto")
    parser.add_argument("--soul-preview-lines", type=int, default=24)
    parser.add_argument("--skip-bridge", action="store_true")
    return parser.parse_args()


def run_cmd(cmd, cwd, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(json.dumps({"ts": time.time(), "event": "start", "cmd": cmd}) + "\n")
    env = os.environ.copy()
    env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    env.setdefault("HF_HOME", str(hf_home()))
    env.setdefault("HUGGINGFACE_HUB_CACHE", env["HF_HOME"])
    env.setdefault("HF_HUB_CACHE", env["HF_HOME"])
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False, env=env)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "event": "finish",
                    "cmd": cmd,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout[-12000:],
                    "stderr": proc.stderr[-12000:],
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)
    return proc.returncode, proc.stdout, proc.stderr


def selected_models(args):
    requested = set(args.models)
    return [model for model in MODELS if model["name"] in requested]


def resolve_save_steps(explicit_value: int, default_steps: int) -> int:
    return explicit_value if explicit_value and explicit_value > 0 else max(20, default_steps // 2)


def append_max_memory_flag(cmd: list[str], max_memory_mib: int) -> list[str]:
    if max_memory_mib and max_memory_mib > 0:
        cmd.extend(["--max-memory-mib", str(max_memory_mib)])
    return cmd


def append_device_map_flag(cmd: list[str], device_map: str) -> list[str]:
    if device_map:
        cmd.extend(["--device-map", device_map])
    return cmd


def main() -> int:
    args = parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    log_path = args.output_root / "storyworld_sft_log.jsonl"

    data_root = args.data_root
    merged_env = data_root / "normalized_trajectories" / "pixue_storyworld_sft.jsonl"
    merge_manifest = data_root / "pixie_research" / "pixue_storyworld_sft_manifest.json"
    action_env = data_root / "normalized_trajectories" / "pixue_storyworld_actions.jsonl"
    action_manifest = data_root / "pixie_research" / "pixue_storyworld_actions_manifest.json"
    prose_env = data_root / "normalized_trajectories" / "pixue_storyworld_prose.jsonl"
    prose_manifest = data_root / "pixie_research" / "pixue_storyworld_prose_manifest.json"
    prose_exact_env = data_root / "normalized_trajectories" / "pixue_storyworld_prose_exact.jsonl"
    prose_exact_manifest = data_root / "pixie_research" / "pixue_storyworld_prose_exact_manifest.json"
    merge_cmd = [
        args.python_bin,
        str(args.merge_env),
        "--output",
        str(merged_env),
        "--manifest",
        str(merge_manifest),
        "--action-output",
        str(action_env),
        "--action-manifest",
        str(action_manifest),
        "--prose-output",
        str(prose_env),
        "--prose-manifest",
        str(prose_manifest),
        "--prose-exact-output",
        str(prose_exact_env),
        "--prose-exact-manifest",
        str(prose_exact_manifest),
        "--storyworld-repeat",
        str(args.storyworld_repeat),
        "--no-hint-action-repeat",
        str(args.no_hint_action_repeat),
        "--soul",
        str(args.soul_path),
    ]
    merge_cmd.extend(["--constitution", str(args.constitution_path)])
    merge_cmd.extend(["--comparison", str(args.comparison_path)])
    optional_repeat_args = {
        "--trm-hint-repeat": args.trm_hint_repeat,
        "--trm-hint-action-repeat": args.trm_hint_action_repeat,
        "--no-hint-repeat": args.no_hint_repeat,
        "--repair-repeat": args.repair_repeat,
        "--comparison-legal-repeat": args.comparison_legal_repeat,
        "--comparison-drift-repeat": args.comparison_drift_repeat,
        "--curriculum-repeat": args.curriculum_repeat,
        "--repeat-repeat": args.repeat_repeat,
        "--prose-repeat": args.prose_repeat,
        "--prose-exact-repeat": args.prose_exact_repeat,
    }
    for flag, value in optional_repeat_args.items():
        if value is not None:
            merge_cmd.extend([flag, str(value)])
    rc, _, _ = run_cmd(
        merge_cmd,
        cwd=str(args.pixie_root),
        log_path=log_path,
    )
    if rc != 0:
        raise SystemExit(rc)

    models = selected_models(args)
    for model in models:
        model_dir = args.output_root / model["name"]
        model_dir.mkdir(parents=True, exist_ok=True)

        if not args.skip_bridge:
            run_cmd(
                [
                    args.python_bin,
                    str(args.bridge_run),
                    "--soul-path",
                    str(args.soul_path),
                    "--episode-label",
                    f"storyworld_pre_{model['name']}",
                ],
                cwd=str(args.bridge_run.parent),
                log_path=log_path,
            )

        if not args.skip_mixed_pass:
            mixed_save_steps = resolve_save_steps(args.save_steps, args.steps)
            train_cmd = [
                args.python_bin,
                str(args.tesseract_train),
                "--model-id",
                model["model_id"],
                "--model-type",
                model["model_type"],
                "--data-root",
                str(data_root),
                "--date-bucket",
                f"{args.output_root.name}-{model['name']}",
                "--envs",
                "pixue_storyworld_sft",
                "--max-records",
                str(args.max_records),
                "--max-len",
                str(args.max_len),
                "--max-action-chars",
                str(args.max_action_chars),
                "--max-think-chars",
                str(args.max_think_chars),
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
                str(mixed_save_steps),
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

        if not args.skip_action_pass:
            action_save_steps = resolve_save_steps(args.action_save_steps, args.action_steps)
            action_train_cmd = [
                args.python_bin,
                str(args.tesseract_train),
                "--model-id",
                model["model_id"],
                "--model-type",
                model["model_type"],
                "--data-root",
                str(data_root),
                "--date-bucket",
                f"{args.output_root.name}-{model['name']}-action",
                "--envs",
                "pixue_storyworld_actions",
                "--max-records",
                str(args.action_max_records),
                "--max-len",
                str(args.action_max_len),
                "--max-action-chars",
                str(args.max_action_chars),
                "--max-think-chars",
                "0",
                "--max-steps",
                str(args.action_steps),
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
                str(action_save_steps),
                "--save-total-limit",
                str(args.save_total_limit),
                "--resume-checkpoint",
                "none",
                "--retry-count",
                "1",
                "--resume",
            ]
            append_max_memory_flag(action_train_cmd, args.max_memory_mib)
            append_device_map_flag(action_train_cmd, args.device_map)
            run_cmd(action_train_cmd, cwd=str(args.tesseract_train.parent), log_path=log_path)

        if not args.skip_prose_pass:
            prose_save_steps = resolve_save_steps(args.prose_save_steps, args.prose_steps)
            prose_train_cmd = [
                args.python_bin,
                str(args.tesseract_train),
                "--model-id",
                model["model_id"],
                "--model-type",
                model["model_type"],
                "--data-root",
                str(data_root),
                "--date-bucket",
                f"{args.output_root.name}-{model['name']}-prose",
                "--envs",
                "pixue_storyworld_prose",
                "--max-records",
                str(args.prose_max_records),
                "--max-len",
                str(args.prose_max_len),
                "--max-action-chars",
                str(args.max_action_chars),
                "--max-think-chars",
                "0",
                "--max-steps",
                str(args.prose_steps),
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
                str(prose_save_steps),
                "--save-total-limit",
                str(args.save_total_limit),
                "--resume-checkpoint",
                "none",
                "--retry-count",
                "1",
                "--resume",
            ]
            append_max_memory_flag(prose_train_cmd, args.max_memory_mib)
            append_device_map_flag(prose_train_cmd, args.device_map)
            run_cmd(prose_train_cmd, cwd=str(args.tesseract_train.parent), log_path=log_path)

        if args.run_prose_exact_pass:
            prose_exact_save_steps = resolve_save_steps(args.prose_exact_save_steps, args.prose_exact_steps)
            prose_exact_train_cmd = [
                args.python_bin,
                str(args.tesseract_train),
                "--model-id",
                model["model_id"],
                "--model-type",
                model["model_type"],
                "--data-root",
                str(data_root),
                "--date-bucket",
                f"{args.output_root.name}-{model['name']}-prose-exact",
                "--envs",
                "pixue_storyworld_prose_exact",
                "--max-records",
                str(args.prose_exact_max_records),
                "--max-len",
                str(args.prose_exact_max_len),
                "--max-action-chars",
                str(args.max_action_chars),
                "--max-think-chars",
                "0",
                "--max-steps",
                str(args.prose_exact_steps),
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
                str(prose_exact_save_steps),
                "--save-total-limit",
                str(args.save_total_limit),
                "--resume-checkpoint",
                "none",
                "--retry-count",
                "1",
                "--resume",
            ]
            append_max_memory_flag(prose_exact_train_cmd, args.max_memory_mib)
            append_device_map_flag(prose_exact_train_cmd, args.device_map)
            run_cmd(prose_exact_train_cmd, cwd=str(args.tesseract_train.parent), log_path=log_path)

        if not args.skip_bridge:
            run_cmd(
                [
                    args.python_bin,
                    str(args.bridge_run),
                    "--soul-path",
                    str(args.soul_path),
                    "--episode-label",
                    f"storyworld_post_{model['name']}",
                ],
                cwd=str(args.bridge_run.parent),
                log_path=log_path,
            )

    summary = {
        "output_root": str(args.output_root),
        "models": [model["name"] for model in models],
        "data_root": str(data_root),
        "merge_output": str(merged_env),
        "action_output": str(action_env),
        "prose_output": str(prose_env),
        "prose_exact_output": str(prose_exact_env),
        "log_path": str(log_path),
        "max_memory_mib": args.max_memory_mib,
        "device_map": args.device_map,
        "steps": args.steps,
        "action_steps": args.action_steps,
        "prose_steps": args.prose_steps,
        "prose_exact_steps": args.prose_exact_steps,
        "save_steps": args.save_steps,
        "action_save_steps": args.action_save_steps,
        "prose_save_steps": args.prose_save_steps,
        "prose_exact_save_steps": args.prose_exact_save_steps,
        "save_total_limit": args.save_total_limit,
        "storyworld_repeat": args.storyworld_repeat,
        "skip_mixed_pass": args.skip_mixed_pass,
        "skip_action_pass": args.skip_action_pass,
        "skip_prose_pass": args.skip_prose_pass,
        "run_prose_exact_pass": args.run_prose_exact_pass,
        "skip_bridge": args.skip_bridge,
    }
    (args.output_root / "storyworld_sft_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
