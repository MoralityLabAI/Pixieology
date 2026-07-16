from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from pixie_env import (
    configure_hf_home,
    data_root,
    hf_home,
    model_id,
    normalized_trajectory_path,
    repo_path,
    research_output_path,
    tesseract_train_script,
)


configure_hf_home()

PIXIE_ROOT = repo_path()
TESSERACT_TRAIN = tesseract_train_script()
BUILD_ENV = repo_path("build_pixie_fae_loop_env.py")
BENCH = repo_path("run_faebench_compare.py")

BASE_MODEL_ID = os.environ.get("PIXIE_BASE_MODEL_1_7B", model_id("base_1_7b"))
MODEL_TYPE = "pixue-1.7B"
ENV_ID = "pixie_fae_loop"

DEFAULT_DATA_ROOT = data_root()
DEFAULT_OUTPUT_ROOT = research_output_path("pixie_fae_loop_2026-03-27")
DEFAULT_OLD_ADAPTER_SCORE_PATH = research_output_path("faebench_compare_2026-03-26.json")
BENCH_PATH = normalized_trajectory_path("faebench.jsonl")


def parse_args():
    parser = argparse.ArgumentParser(description="Run an incremental Pixie Fae QLoRA loop.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--python-bin", default=sys.executable or "python")
    parser.add_argument("--base-model-id", default=BASE_MODEL_ID)
    parser.add_argument("--tesseract-train", type=Path, default=TESSERACT_TRAIN)
    parser.add_argument("--build-env", type=Path, default=BUILD_ENV)
    parser.add_argument("--bench-script", type=Path, default=BENCH)
    parser.add_argument("--old-adapter-score-path", type=Path, default=DEFAULT_OLD_ADAPTER_SCORE_PATH)
    parser.add_argument("--bench-path", type=Path, default=BENCH_PATH)
    parser.add_argument("--steps-round1", type=int, default=60)
    parser.add_argument("--steps-round2", type=int, default=120)
    parser.add_argument("--max-records", type=int, default=120)
    parser.add_argument("--max-len", type=int, default=384)
    parser.add_argument("--max-action-chars", type=int, default=8192)
    parser.add_argument("--max-think-chars", type=int, default=4096)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=1)
    parser.add_argument("--lora-r", type=int, default=4)
    parser.add_argument("--lora-alpha", type=int, default=8)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--learning-rate", type=float, default=1.5e-4)
    parser.add_argument("--bench-max-new-tokens", type=int, default=32)
    parser.add_argument("--max-memory-mib", type=int, default=3300)
    return parser.parse_args()


def run_cmd(cmd, cwd: Path, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    env.setdefault("HF_HOME", str(hf_home()))
    env.setdefault("HUGGINGFACE_HUB_CACHE", env["HF_HOME"])
    env.setdefault("HF_HUB_CACHE", env["HF_HOME"])
    with log_path.open("a", encoding="utf-8") as log:
        log.write(json.dumps({"ts": time.time(), "event": "start", "cmd": cmd}) + "\n")
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env, check=False)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "event": "finish",
                    "cmd": cmd,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout[-16000:],
                    "stderr": proc.stderr[-16000:],
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


def _extract_quality(payload: dict, model_key: str) -> float:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return float("nan")
    adapter_summary = summary.get(f"{model_key}_adapter")
    if isinstance(adapter_summary, dict):
        val = adapter_summary.get("avg_quality_score")
        if isinstance(val, (int, float)):
            return float(val)
    # fallback legacy shape
    adapters = summary.get("adapters")
    if isinstance(adapters, dict):
        candidate = adapters.get(model_key)
        if isinstance(candidate, dict):
            val = candidate.get("avg_quality_score")
            if isinstance(val, (int, float)):
                return float(val)
    return float("nan")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_env(stage: str, data_root_path: Path, python_bin: str, build_env_path: Path, log_path: Path):
    output = data_root_path / "normalized_trajectories" / "pixie_fae_loop.jsonl"
    manifest = data_root_path / "pixie_research" / "pixie_fae_loop_manifest.json"
    cmd = [
        python_bin,
        str(build_env_path),
        "--stage",
        stage,
        "--output",
        str(output),
        "--manifest",
        str(manifest),
    ]
    rc, _, _ = run_cmd(cmd, cwd=PIXIE_ROOT, log_path=log_path)
    if rc != 0:
        raise SystemExit(rc)
    return output, manifest


def train_round(args, log_path: Path, date_bucket: str, max_steps: int, resume_checkpoint: str):
    cmd = [
        args.python_bin,
        str(args.tesseract_train),
        "--model-id",
        args.base_model_id,
        "--model-type",
        MODEL_TYPE,
        "--data-root",
        str(args.data_root),
        "--date-bucket",
        date_bucket,
        "--envs",
        ENV_ID,
        "--max-records",
        str(args.max_records),
        "--max-len",
        str(args.max_len),
        "--max-action-chars",
        str(args.max_action_chars),
        "--max-think-chars",
        str(args.max_think_chars),
        "--max-steps",
        str(max_steps),
        "--learning-rate",
        str(args.learning_rate),
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
        "--max-memory-mib",
        str(args.max_memory_mib),
        "--save-steps",
        str(max(25, max_steps // 2)),
        "--save-total-limit",
        "2",
        "--resume-checkpoint",
        resume_checkpoint,
        "--retry-count",
        "1",
    ]
    rc, _, _ = run_cmd(cmd, cwd=args.tesseract_train.parent, log_path=log_path)
    if rc != 0:
        raise SystemExit(rc)


def benchmark(args, adapter_path: Path, output_path: Path, log_path: Path):
    cmd = [
        args.python_bin,
        str(args.bench_script),
        "--models",
        "1.7B",
        "--bench",
        str(args.bench_path),
        "--output",
        str(output_path),
        "--adapter-path",
        f"1.7B={adapter_path}",
        "--max-new-tokens",
        str(args.bench_max_new_tokens),
    ]
    rc, _, _ = run_cmd(cmd, cwd=PIXIE_ROOT, log_path=log_path)
    if rc != 0:
        raise SystemExit(rc)
    return load_json(output_path)


def main() -> int:
    args = parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    log_path = args.output_root / "fae_loop_log.jsonl"
    summary_path = args.output_root / "fae_loop_summary.json"

    if not args.old_adapter_score_path.exists():
        print(f"ERROR: Missing baseline benchmark: {args.old_adapter_score_path}")
        return 1
    old_receipt = load_json(args.old_adapter_score_path)
    old_adapter_quality = _extract_quality(old_receipt, "1.7B")
    if not old_adapter_quality == old_adapter_quality:
        print(f"ERROR: Baseline quality missing in {args.old_adapter_score_path}")
        return 1

    build_env("base", args.data_root, args.python_bin, args.build_env, log_path)
    date_bucket = f"{args.output_root.name}-1.7B"
    train_round(args, log_path, date_bucket, args.steps_round1, "none")
    adapter_path = (
        args.data_root
        / "models"
        / "adapters"
        / MODEL_TYPE
        / date_bucket
        / ENV_ID
    )
    round1_bench = args.output_root / "faebench_round1.json"
    round1 = benchmark(args, adapter_path, round1_bench, log_path)

    build_env("topup", args.data_root, args.python_bin, args.build_env, log_path)
    train_round(args, log_path, date_bucket, args.steps_round2, "latest")
    round2_bench = args.output_root / "faebench_round2.json"
    round2 = benchmark(args, adapter_path, round2_bench, log_path)

    round1_quality = _extract_quality(round1, "1.7B")
    round2_quality = _extract_quality(round2, "1.7B")
    if round1_quality != round1_quality or round2_quality != round2_quality:
        print("ERROR: Benchmark output missing required quality score fields.")
        return 1
    summary = {
        "output_root": str(args.output_root),
        "adapter_path": str(adapter_path),
        "old_adapter_quality": old_adapter_quality,
        "round1_quality": round1_quality,
        "round2_quality": round2_quality,
        "round1_delta_vs_old": round1_quality - old_adapter_quality,
        "round2_delta_vs_old": round2_quality - old_adapter_quality,
        "round2_delta_vs_round1": round2_quality - round1_quality,
        "round1_benchmark": str(round1_bench),
        "round2_benchmark": str(round2_bench),
        "log_path": str(log_path),
        "outbenched_last": round2_quality > old_adapter_quality,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
