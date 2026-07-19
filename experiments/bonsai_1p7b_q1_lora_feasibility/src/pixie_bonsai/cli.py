"""Command-line entrypoint for every independently resumable experiment phase."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .config import ExperimentConfig, project_root
from .reporting import layout


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pixie-bonsai")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "preflight-adapter", "memory-probe", "eval-hf", "build-llama", "export-gguf", "eval-q1", "offline-test", "report", "bundle", "smoke-all"):
        command = sub.add_parser(name)
        if name in {"eval-hf", "export-gguf", "eval-q1", "offline-test", "bundle"}:
            command.add_argument("--run-name", default="smoke-v1")
    train = sub.add_parser("train-smoke")
    train.add_argument("--target-step", type=int, default=30)
    train.add_argument("--run-name", default="smoke-v1")
    return parser


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _dry(config: ExperimentConfig, args: argparse.Namespace) -> dict[str, Any]:
    return {
        "dry_run": True, "command": args.command, "config": str(config.source),
        "paths": config.section("paths"), "caps": config.section("caps"),
        "training": config.section("training"),
    }


def _capped(config: ExperimentConfig, arguments: list[str], run_id: str) -> None:
    paths = layout(config)
    script = project_root() / "scripts" / "run_capped.ps1"
    child = ["-m", "pixie_bonsai.cli", "--config", str(config.source), *arguments]
    payload = base64.b64encode(json.dumps(child).encode("utf-8")).decode("ascii")
    caps = config.section("caps")
    argv = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
        "-Executable", sys.executable, "-ArgumentsBase64", payload,
        "-RunId", run_id, "-OutputDirectory", str(paths.artifacts / "capped"),
        "-MemoryGB", str(caps["ram_gb"]), "-CpuPercent", str(caps["cpu_percent"]),
        "-IoMBPerSecond", str(caps["io_mb_per_second"]),
        "-TimeoutMinutes", str(caps["max_runtime_minutes"]),
    ]
    completed = subprocess.run(
        argv, cwd=project_root(), text=True, capture_output=True, check=False, shell=False,
        timeout=(int(caps["max_runtime_minutes"]) + 3) * 60,
    )
    cleanup = project_root() / "scripts" / "post_run_cleanup.ps1"
    subprocess.run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(cleanup),
        "-PidFile", str(paths.artifacts / "capped" / f"{run_id}.pids.json"),
        "-SummaryPath", str(paths.artifacts / "capped" / f"{run_id}.cleanup.json"),
        "-RunId", run_id,
    ], cwd=project_root(), text=True, capture_output=True, check=False, shell=False, timeout=60)
    if completed.returncode != 0:
        raise RuntimeError(
            f"capped stage {run_id} failed ({completed.returncode})\n"
            f"stdout:\n{completed.stdout[-2000:]}\nstderr:\n{completed.stderr[-4000:]}"
        )


def smoke_all(config: ExperimentConfig, run_name: str = "smoke-v1") -> dict[str, Any]:
    from .doctor import inspect
    from .report import generate_report
    from .bundle import create_bundle

    paths = layout(config)
    run_dir = paths.runs / run_name

    def evidence_status(path: Path) -> str | None:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))["status"]

    def gate_stop() -> dict[str, Any]:
        report = generate_report(config, run_name)
        bundle = None
        if (run_dir / "adapter" / "adapter_model.safetensors").is_file() and (run_dir / "hf_evaluation.json").is_file():
            bundle = create_bundle(config, run_name)
            report = generate_report(config, run_name)
        return {"status": report["decision"], "gate_stopped": True, "bundle": bundle, "report": str(project_root() / "FEASIBILITY_REPORT.md")}

    inspect(config)
    def run_stage(arguments: list[str], stage: str) -> None:
        try:
            _capped(config, arguments, stage)
        except BaseException:
            generate_report(config, run_name)
            raise

    run_stage(["build-llama"], "00-build-llama")
    run_stage(["preflight-adapter"], "01-preflight")
    run_stage(["memory-probe"], "02-memory-probe")
    if evidence_status(paths.artifacts / "memory_probe.json") != "PASS":
        return gate_stop()
    stages = [
        (["train-smoke", "--target-step", "10", "--run-name", run_name], "03-train-10"),
        (["train-smoke", "--target-step", "20", "--run-name", run_name], "04-resume-20"),
        (["train-smoke", "--target-step", "30", "--run-name", run_name], "05-resume-30"),
    ]
    for arguments, stage in stages:
        run_stage(arguments, stage)
    run_stage(["eval-hf", "--run-name", run_name], "06-eval-hf")
    if evidence_status(run_dir / "hf_evaluation.json") != "PASS":
        return gate_stop()
    run_stage(["export-gguf", "--run-name", run_name], "07-export-gguf")
    run_stage(["eval-q1", "--run-name", run_name], "08-eval-q1")
    if evidence_status(run_dir / "q1_evaluation.json") != "PASS":
        return gate_stop()
    run_stage(["offline-test", "--run-name", run_name], "09-offline")
    generate_report(config, run_name)
    bundle = create_bundle(config, run_name)
    report = generate_report(config, run_name)
    return {"status": report["decision"], "bundle": bundle, "report": str(project_root() / "FEASIBILITY_REPORT.md")}


def dispatch(config: ExperimentConfig, args: argparse.Namespace) -> Any:
    if args.dry_run:
        return _dry(config, args)
    command = args.command
    if command == "doctor":
        from .doctor import inspect
        return inspect(config)
    if command == "preflight-adapter":
        from .export_gguf import preflight_adapter
        return preflight_adapter(config)
    if command == "memory-probe":
        from .train import memory_probe
        return memory_probe(config)
    if command == "train-smoke":
        from .train import train_smoke
        return train_smoke(config, target_step=args.target_step, run_name=args.run_name)
    if command == "eval-hf":
        from .eval_hf import evaluate_hf
        return evaluate_hf(config, args.run_name)
    if command == "build-llama":
        from .export_gguf import build_llama
        return build_llama(config)
    if command == "export-gguf":
        from .export_gguf import export_trained_adapter
        return export_trained_adapter(config, args.run_name)
    if command == "eval-q1":
        from .eval_gguf import evaluate_q1
        return evaluate_q1(config, args.run_name)
    if command == "offline-test":
        from .eval_hf import offline_evaluation
        return offline_evaluation(config, args.run_name)
    if command == "report":
        from .report import generate_report
        return generate_report(config)
    if command == "bundle":
        from .bundle import create_bundle
        return create_bundle(config, args.run_name)
    if command == "smoke-all":
        return smoke_all(config)
    raise AssertionError(command)


def main(argv: list[str] | None = None) -> None:
    os.environ.setdefault("WANDB_DISABLED", "true")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("DISABLE_TELEMETRY", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    args = _parser().parse_args(argv)
    config = ExperimentConfig.load(args.config)
    _print(dispatch(config, args))


if __name__ == "__main__":
    main()
