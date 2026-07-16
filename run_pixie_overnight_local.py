from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pixie_env import data_root, hf_home, model_cache_dir, model_id, repo_path, tesseract_train_script


MODEL_CONFIGS = {
    "0.8B": {
        "model_id": os.environ.get("PIXIE_BASE_MODEL_0_8B", model_id("base_0_8b")),
        "model_type": "pixue-0.8B",
        "learning_rate": "3e-4",
        "max_memory_mib": 3300,
        "device_map": "auto",
    },
    "1.7B": {
        "model_id": os.environ.get("PIXIE_BASE_MODEL_1_7B", model_id("base_1_7b")),
        "model_type": "pixue-1.7B",
        "learning_rate": "2e-4",
        "max_memory_mib": 3900,
        "device_map": "single-gpu",
    },
}

LANE_CONFIGS = {
    "companion": {
        "0.8B": {
            "envs": ["pixue_reflective_buddy_train_holdout", "pixue_storyworld_prose"],
            "mix_envs": True,
            "family_id": "companion_pet_prose",
            "max_records": 320,
            "max_len": 320,
            "max_steps": 180,
            "batch_size": 1,
            "grad_accum": 8,
            "lora_r": 4,
            "lora_alpha": 8,
            "lora_dropout": 0.05,
            "max_action_chars": 8192,
            "max_think_chars": 0,
            "save_steps": 180,
            "timeout_sec": 3 * 60 * 60,
        },
        "1.7B": {
            "envs": ["pixue_reflective_buddy_train_holdout", "pixue_storyworld_prose"],
            "mix_envs": True,
            "family_id": "companion_pet_prose",
            "max_records": 224,
            "max_len": 256,
            "max_steps": 120,
            "batch_size": 1,
            "grad_accum": 16,
            "lora_r": 2,
            "lora_alpha": 4,
            "lora_dropout": 0.05,
            "max_action_chars": 8192,
            "max_think_chars": 0,
            "save_steps": 24,
            "timeout_sec": 8 * 60 * 60,
        },
    },
    "storyworld_action": {
        "0.8B": {
            "envs": ["pixue_storyworld_actions"],
            "mix_envs": False,
            "family_id": "",
            "max_records": 160,
            "max_len": 256,
            "max_steps": 96,
            "batch_size": 1,
            "grad_accum": 8,
            "lora_r": 4,
            "lora_alpha": 8,
            "lora_dropout": 0.05,
            "max_action_chars": 8192,
            "max_think_chars": 0,
            "save_steps": 96,
            "timeout_sec": 3 * 60 * 60,
        },
        "1.7B": {
            "envs": ["pixue_storyworld_actions"],
            "mix_envs": False,
            "family_id": "",
            "max_records": 96,
            "max_len": 192,
            "max_steps": 48,
            "batch_size": 1,
            "grad_accum": 16,
            "lora_r": 2,
            "lora_alpha": 4,
            "lora_dropout": 0.05,
            "max_action_chars": 8192,
            "max_think_chars": 0,
            "save_steps": 12,
            "timeout_sec": 6 * 60 * 60,
        },
    },
    "storyworld_prose_exact": {
        "0.8B": {
            "envs": ["pixue_storyworld_prose_exact"],
            "mix_envs": False,
            "family_id": "",
            "max_records": 96,
            "max_len": 256,
            "max_steps": 72,
            "batch_size": 1,
            "grad_accum": 8,
            "lora_r": 4,
            "lora_alpha": 8,
            "lora_dropout": 0.05,
            "max_action_chars": 8192,
            "max_think_chars": 0,
            "save_steps": 72,
            "timeout_sec": 3 * 60 * 60,
        },
        "1.7B": {
            "envs": ["pixue_storyworld_prose_exact"],
            "mix_envs": False,
            "family_id": "",
            "max_records": 64,
            "max_len": 192,
            "max_steps": 48,
            "batch_size": 1,
            "grad_accum": 16,
            "lora_r": 2,
            "lora_alpha": 4,
            "lora_dropout": 0.05,
            "max_action_chars": 8192,
            "max_think_chars": 0,
            "save_steps": 12,
            "timeout_sec": 6 * 60 * 60,
        },
    },
}


@dataclass
class LaneResult:
    lane: str
    requested_model: str
    actual_model: str
    status: str
    adapter_path: str = ""
    benchmark_outputs: dict[str, str] | None = None
    note: str = ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an overnight local Pixie training and testing program.")
    parser.add_argument("--run-id", default=datetime.now().strftime("pixie_overnight_%Y-%m-%d_%H%M%S"))
    parser.add_argument("--data-root", type=Path, default=data_root())
    parser.add_argument("--python-bin", default=sys.executable or "python")
    parser.add_argument("--train-script", type=Path, default=tesseract_train_script())
    parser.add_argument("--gpu-floor-1.7b-mib", type=int, default=3900)
    parser.add_argument("--skip-1.7b", dest="skip_1_7b", action="store_true")
    parser.add_argument("--force-1.7b", dest="force_1_7b", action="store_true")
    return parser.parse_args(argv)


def runtime_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PIXIE_ROOT", str(repo_path()))
    env.setdefault("PIXIE_DATA_ROOT", str(args.data_root))
    env.setdefault("PIXIE_MODEL_CACHE_DIR", str(model_cache_dir()))
    env.setdefault("HF_HOME", str(hf_home()))
    env.setdefault("HUGGINGFACE_HUB_CACHE", env["HF_HOME"])
    env.setdefault("HF_HUB_CACHE", env["HF_HOME"])
    env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    return env


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path,
    env: dict[str, str],
    timeout_sec: int | None = None,
) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with log_path.open("a", encoding="utf-8") as log:
        log.write(json.dumps({"ts": started, "event": "start", "cmd": cmd, "cwd": str(cwd)}) + "\n")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_sec,
            check=False,
        )
        payload = {
            "ts": time.time(),
            "event": "finish",
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-16000:],
            "stderr": proc.stderr[-16000:],
        }
    except subprocess.TimeoutExpired as exc:
        proc = subprocess.CompletedProcess(cmd, returncode=124, stdout=exc.stdout or "", stderr=exc.stderr or "")
        payload = {
            "ts": time.time(),
            "event": "timeout",
            "cmd": cmd,
            "returncode": 124,
            "stdout": (exc.stdout or "")[-16000:],
            "stderr": (exc.stderr or "")[-16000:],
            "timeout_sec": timeout_sec,
        }
    with log_path.open("a", encoding="utf-8") as log:
        log.write(json.dumps(payload, ensure_ascii=False) + "\n")
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)
    return proc


def query_gpu() -> dict[str, int | str]:
    try:
        raw = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        ).strip()
    except Exception:
        return {}
    if not raw:
        return {}
    first = raw.splitlines()[0]
    parts = [part.strip() for part in first.split(",")]
    if len(parts) != 3:
        return {}
    name, total, used = parts
    total_mib = int(total)
    used_mib = int(used)
    return {
        "name": name,
        "total_mib": total_mib,
        "used_mib": used_mib,
        "free_mib": total_mib - used_mib,
    }


def build_adapter_path(args: argparse.Namespace, model_size: str, date_bucket: str, lane_name: str) -> Path:
    model_type = MODEL_CONFIGS[model_size]["model_type"]
    lane_cfg = LANE_CONFIGS[lane_name][model_size]
    leaf = lane_cfg["family_id"] or lane_cfg["envs"][0]
    return args.data_root / "models" / "adapters" / model_type / date_bucket / leaf


def ensure_core_envs(args: argparse.Namespace, env: dict[str, str], log_path: Path) -> None:
    commands = [
        [args.python_bin, str(repo_path("build_pixie_storyworld_sft_env.py"))],
        [args.python_bin, str(repo_path("build_faebench_env.py"))],
        [args.python_bin, str(repo_path("build_reflective_buddy_experiment.py"))],
    ]
    for cmd in commands:
        proc = run_cmd(cmd, cwd=repo_path(), log_path=log_path, env=env, timeout_sec=30 * 60)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed while preparing core envs: {' '.join(cmd)}")


def train_lane(
    args: argparse.Namespace,
    lane_name: str,
    model_size: str,
    env: dict[str, str],
    log_path: Path,
    run_id: str,
) -> LaneResult:
    model_cfg = MODEL_CONFIGS[model_size]
    lane_cfg = LANE_CONFIGS[lane_name][model_size]
    date_bucket = f"{run_id}-{model_size}-{lane_name}"
    cmd = [
        args.python_bin,
        str(args.train_script),
        "--model-id",
        str(model_cfg["model_id"]),
        "--model-type",
        model_cfg["model_type"],
        "--data-root",
        str(args.data_root),
        "--date-bucket",
        date_bucket,
        "--envs",
        *lane_cfg["envs"],
        "--max-records",
        str(lane_cfg["max_records"]),
        "--max-len",
        str(lane_cfg["max_len"]),
        "--max-action-chars",
        str(lane_cfg["max_action_chars"]),
        "--max-think-chars",
        str(lane_cfg["max_think_chars"]),
        "--max-steps",
        str(lane_cfg["max_steps"]),
        "--learning-rate",
        model_cfg["learning_rate"],
        "--batch-size",
        str(lane_cfg["batch_size"]),
        "--grad-accum",
        str(lane_cfg["grad_accum"]),
        "--lora-r",
        str(lane_cfg["lora_r"]),
        "--lora-alpha",
        str(lane_cfg["lora_alpha"]),
        "--lora-dropout",
        str(lane_cfg["lora_dropout"]),
        "--save-steps",
        str(lane_cfg["save_steps"]),
        "--save-total-limit",
        "1",
        "--max-memory-mib",
        str(model_cfg["max_memory_mib"]),
        "--device-map",
        str(model_cfg["device_map"]),
        "--resume-checkpoint",
        "auto",
        "--retry-count",
        "1",
        "--resume",
    ]
    if lane_cfg["mix_envs"]:
        cmd.extend(["--mix-envs", "--family-id", lane_cfg["family_id"]])
    proc = run_cmd(
        cmd,
        cwd=args.train_script.parent,
        log_path=log_path,
        env=env,
        timeout_sec=lane_cfg["timeout_sec"],
    )
    adapter_path = build_adapter_path(args, model_size, date_bucket, lane_name)
    status = "completed" if proc.returncode == 0 and adapter_path.exists() else "failed"
    note = "" if status == "completed" else f"Training failed with return code {proc.returncode}"
    return LaneResult(
        lane=lane_name,
        requested_model=model_size,
        actual_model=model_size,
        status=status,
        adapter_path=str(adapter_path) if adapter_path.exists() else "",
        note=note,
    )


def evaluate_adapter(
    args: argparse.Namespace,
    *,
    model_size: str,
    adapter_path: str,
    bench_path: Path,
    output_path: Path,
    log_path: Path,
    env: dict[str, str],
    categories: list[str] | None = None,
) -> bool:
    cmd = [
        args.python_bin,
        str(repo_path("run_faebench_compare.py")),
        "--models",
        model_size,
        "--bench",
        str(bench_path),
        "--adapter-path",
        f"{model_size}={adapter_path}",
        "--output",
        str(output_path),
    ]
    for category in categories or []:
        cmd.extend(["--category", category])
    proc = run_cmd(cmd, cwd=repo_path(), log_path=log_path, env=env, timeout_sec=2 * 60 * 60)
    if proc.returncode != 0:
        return False
    if not output_path.exists() or output_path.stat().st_size == 0:
        return False
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(payload.get("summary")) or bool(payload.get("results"))


def maybe_train_with_fallback(
    args: argparse.Namespace,
    lane_name: str,
    env: dict[str, str],
    log_path: Path,
    run_id: str,
) -> LaneResult:
    gpu = query_gpu()
    if args.skip_1_7b:
        primary_allowed = False
        note = "1.7B lanes disabled by flag."
    elif args.force_1_7b:
        primary_allowed = True
        note = "1.7B forced despite GPU floor."
    else:
        primary_allowed = bool(gpu) and int(gpu.get("free_mib", 0)) >= args.gpu_floor_1_7b_mib
        note = "" if primary_allowed else f"GPU free memory below floor for 1.7B: {gpu}"

    if primary_allowed:
        primary = train_lane(args, lane_name, "1.7B", env, log_path, run_id)
        if primary.status == "completed":
            return primary
        note = primary.note or "1.7B lane failed."

    fallback = train_lane(args, lane_name, "0.8B", env, log_path, run_id)
    fallback.requested_model = "1.7B"
    fallback.note = (note + " Falling back to 0.8B.").strip()
    return fallback


def write_route_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    env = runtime_env(args)
    research_dir = args.data_root / "pixie_research" / args.run_id
    research_dir.mkdir(parents=True, exist_ok=True)
    log_path = research_dir / "overnight_log.jsonl"
    route_manifest_path = research_dir / "overnight_route_manifest.json"

    manifest = {
        "run_id": args.run_id,
        "started_at": datetime.now().isoformat(),
        "repo_root": str(repo_path()),
        "data_root": str(args.data_root),
        "gpu_at_start": query_gpu(),
        "lanes": [],
    }
    write_route_manifest(route_manifest_path, manifest)

    ensure_core_envs(args, env, log_path)

    companion = maybe_train_with_fallback(args, "companion", env, log_path, args.run_id)
    if companion.status == "completed":
        companion_slug = companion.actual_model.replace(".", "p").lower()
        companion_bench = research_dir / f"companion_reflective_bench_{companion_slug}.json"
        fae_bench = research_dir / f"companion_faebench_{companion_slug}.json"
        outputs = {}
        if evaluate_adapter(
            args,
            model_size=companion.actual_model,
            adapter_path=companion.adapter_path,
            bench_path=args.data_root / "normalized_trajectories" / "reflective_buddy_holdout_bench.jsonl",
            output_path=companion_bench,
            log_path=log_path,
            env=env,
        ):
            outputs["reflective_buddy_holdout"] = str(companion_bench)
        if evaluate_adapter(
            args,
            model_size=companion.actual_model,
            adapter_path=companion.adapter_path,
            bench_path=args.data_root / "normalized_trajectories" / "faebench.jsonl",
            output_path=fae_bench,
            log_path=log_path,
            env=env,
            categories=["pet_identity", "multi_turn", "soul_memory", "fae_values"],
        ):
            outputs["faebench_pet_slice"] = str(fae_bench)
        companion.benchmark_outputs = outputs
    manifest["lanes"].append(companion.__dict__)
    write_route_manifest(route_manifest_path, manifest)

    storyworld_action = maybe_train_with_fallback(args, "storyworld_action", env, log_path, args.run_id)
    if storyworld_action.status == "completed":
        action_bench = research_dir / f"storyworld_action_faebench_{storyworld_action.actual_model.replace('.', 'p').lower()}.json"
        outputs = {}
        if evaluate_adapter(
            args,
            model_size=storyworld_action.actual_model,
            adapter_path=storyworld_action.adapter_path,
            bench_path=args.data_root / "normalized_trajectories" / "faebench.jsonl",
            output_path=action_bench,
            log_path=log_path,
            env=env,
        ):
            outputs["faebench"] = str(action_bench)
        storyworld_action.benchmark_outputs = outputs
    manifest["lanes"].append(storyworld_action.__dict__)
    write_route_manifest(route_manifest_path, manifest)

    storyworld_prose_exact = maybe_train_with_fallback(args, "storyworld_prose_exact", env, log_path, args.run_id)
    if storyworld_prose_exact.status == "completed":
        prose_bench = research_dir / f"storyworld_prose_exact_faebench_{storyworld_prose_exact.actual_model.replace('.', 'p').lower()}.json"
        outputs = {}
        if evaluate_adapter(
            args,
            model_size=storyworld_prose_exact.actual_model,
            adapter_path=storyworld_prose_exact.adapter_path,
            bench_path=args.data_root / "normalized_trajectories" / "faebench.jsonl",
            output_path=prose_bench,
            log_path=log_path,
            env=env,
            categories=["textual", "quiz", "multi_turn", "storyworld_boundary", "fae_values"],
        ):
            outputs["faebench"] = str(prose_bench)
        storyworld_prose_exact.benchmark_outputs = outputs
    manifest["lanes"].append(storyworld_prose_exact.__dict__)
    manifest["completed_at"] = datetime.now().isoformat()
    manifest["gpu_at_end"] = query_gpu()
    write_route_manifest(route_manifest_path, manifest)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
