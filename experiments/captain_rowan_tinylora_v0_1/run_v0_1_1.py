"""Hash-bound 10 GiB continuation for the Captain Rowan TinyLoRA packet."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent
BASE_RUNNER = ROOT / "run.py"


def _load_base_runner():
    spec = importlib.util.spec_from_file_location("captain_rowan_v0_1_base", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load sealed Captain Rowan v0.1 runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = _load_base_runner()


def required_statement(job: dict) -> str:
    return (
        f"I explicitly authorize the exact Captain Rowan five-fact TinyLoRA v0.1.1 job {job['job_sha256']} "
        "under 10240 MiB RAM, 50 percent CPU, 50 MiB/s I/O, 1800 seconds, and a 3900 MiB peak VRAM guard. "
        "I acknowledge frozen discovery/transfer splits, model loading, rank-2 gate_proj training at layers 21 through 25, "
        "checkpointing every five steps or 60 seconds, abort as a valid outcome, PID-scoped cleanup, the prior 8 GiB "
        "memory-cap abort, and no automatic authorization."
    )


def validate_retry_authorization(path: Path, job: dict, require_wrapper: bool) -> SimpleNamespace:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "captain_rowan_tinylora_authorization.v1_1" or value.get("authorized") is not True:
        raise ValueError("Captain Rowan v0.1.1 authorization is not active")
    if value.get("statement") != required_statement(job):
        raise ValueError("Captain Rowan v0.1.1 authorization statement differs from the bound job")
    if value.get("job_id") != job["job_id"] or value.get("job_sha256") != job["job_sha256"]:
        raise ValueError("Captain Rowan v0.1.1 authorization belongs to another job")
    if value.get("caps") != job["resources"] or value.get("gpu_guard") != job["gpu_guard"]:
        raise ValueError("Captain Rowan v0.1.1 authorization resource guards differ from the job")
    acknowledgements = value.get("acknowledgements", {})
    required = {
        "model_load", "rank2_gate_training", "frozen_splits", "checkpointing",
        "abort_is_valid_outcome", "pid_scoped_cleanup", "prior_memory_abort",
        "no_automatic_authorization",
    }
    if not all(acknowledgements.get(key) is True for key in required):
        raise ValueError("Captain Rowan v0.1.1 authorization acknowledgements are incomplete")
    expires = datetime.fromisoformat(str(value.get("expires_utc", "")).replace("Z", "+00:00"))
    if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
        raise ValueError("Captain Rowan v0.1.1 authorization is expired")
    run_id = str(value.get("run_id", "")).strip()
    attempt_id = str(value.get("attempt_id", "")).strip()
    if not run_id or not attempt_id or "replace-me" in {run_id, attempt_id}:
        raise ValueError("Captain Rowan v0.1.1 authorization requires concrete run and attempt IDs")
    if require_wrapper:
        expected = {
            "PIXIE_RESOURCE_CAP_ACTIVE": "1",
            "PIXIE_RUN_ID": run_id,
            "PIXIE_CAP_RAM_MB": str(job["resources"]["ram_mb"]),
            "PIXIE_CAP_CPU_PCT": str(job["resources"]["cpu_pct"]),
            "PIXIE_CAP_IO_MB_S": str(job["resources"]["io_mb_s"]),
            "PIXIE_CAP_TIMEOUT_SECONDS": str(job["resources"]["timeout_seconds"]),
        }
        for name, expected_value in expected.items():
            if os.environ.get(name) != expected_value:
                raise ValueError(f"wrapper environment {name} differs from authorization")
    return SimpleNamespace(run_id=run_id, attempt_id=attempt_id, receipt=value)


def verify_retry_binding(job: dict) -> None:
    execution = job.get("execution", {})
    paths = {
        "retry_launcher_sha256": ROOT / "run_v0_1_1.py",
        "retry_wrapper_sha256": ROOT / "scripts" / "run_capped_v0_1_1.ps1",
    }
    for hash_key, path in paths.items():
        if not path.is_file() or base.file_sha(path) != execution.get(hash_key):
            raise ValueError(f"Captain Rowan v0.1.1 {hash_key} mismatch")
    receipt_path = ROOT / "attempt_01_result.json"
    if base.file_sha(receipt_path) != job.get("retry", {}).get("prior_attempt_receipt_sha256"):
        raise ValueError("Captain Rowan v0.1.1 prior abort receipt mismatch")


def main() -> int:
    job_argument = None
    for index, value in enumerate(sys.argv[:-1]):
        if value == "--job":
            job_argument = Path(sys.argv[index + 1])
            break
    if job_argument is None:
        raise ValueError("Captain Rowan v0.1.1 requires --job")
    job = base.load_outer(job_argument)
    verify_retry_binding(job)
    base.validate_authorization = validate_retry_authorization
    return base.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(json.dumps({"status": "REJECTED", "error": str(error)}, indent=2))
        raise SystemExit(2)
