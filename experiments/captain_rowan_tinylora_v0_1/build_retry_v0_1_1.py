"""Build the not-authorized 10 GiB retry packet after attempt 01's cap abort."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from run import file_sha, object_sha


ROOT = Path(__file__).resolve().parent


def required_statement(job_sha256: str) -> str:
    return (
        f"I explicitly authorize the exact Captain Rowan five-fact TinyLoRA v0.1.1 job {job_sha256} "
        "under 10240 MiB RAM, 50 percent CPU, 50 MiB/s I/O, 1800 seconds, and a 3900 MiB peak VRAM guard. "
        "I acknowledge frozen discovery/transfer splits, model loading, rank-2 gate_proj training at layers 21 through 25, "
        "checkpointing every five steps or 60 seconds, abort as a valid outcome, PID-scoped cleanup, the prior 8 GiB "
        "memory-cap abort, and no automatic authorization."
    )


def build() -> dict:
    source = json.loads((ROOT / "job.json").read_text(encoding="utf-8"))
    job = copy.deepcopy(source)
    job.pop("job_sha256", None)
    job["training_task_id"] = "captain-rowan-five-fact-tinylora-v1.1"
    job["resources"]["ram_mb"] = 10240
    job["retry"] = {
        "predecessor_job_sha256": source["job_sha256"],
        "prior_attempt_id": "captain-rowan-local-01",
        "prior_attempt_receipt": "experiments/captain_rowan_tinylora_v0_1/attempt_01_result.json",
        "prior_attempt_receipt_sha256": file_sha(ROOT / "attempt_01_result.json"),
        "reason": "Windows Job Object accounting reached 8211.640625 MiB before optimizer step 1 under the 8192 MiB cap.",
        "approved_change": "RAM cap only: 8192 MiB to 10240 MiB",
        "unchanged_guards": ["cpu_pct", "io_mb_s", "timeout_seconds", "maximum_peak_memory_mib"],
    }
    job["execution"]["state"] = "READY_AWAITING_EXACT_AUTHORIZATION_V0_1_1"
    job["execution"]["retry_launcher"] = "experiments/captain_rowan_tinylora_v0_1/run_v0_1_1.py"
    job["execution"]["retry_launcher_sha256"] = file_sha(ROOT / "run_v0_1_1.py")
    job["execution"]["retry_wrapper"] = "experiments/captain_rowan_tinylora_v0_1/scripts/run_capped_v0_1_1.ps1"
    job["execution"]["retry_wrapper_sha256"] = file_sha(ROOT / "scripts" / "run_capped_v0_1_1.ps1")
    job["execution"]["hard_cap_paths"] = [job["execution"]["retry_wrapper"]]
    job["claim_boundary"] = (
        "This v0.1.1 packet changes only the hard RAM cap to the explicitly approved 10240 MiB. "
        "It remains a sealed proposal and does not authorize model loading or training until its exact hash-bound statement is supplied."
    )
    job["job_sha256"] = object_sha(job)
    (ROOT / "job_v0_1_1.json").write_text(json.dumps(job, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    statement = required_statement(job["job_sha256"])
    authorization = {
        "schema": "captain_rowan_tinylora_authorization.v1_1",
        "authorized": False,
        "statement": statement,
        "job_id": job["job_id"],
        "job_sha256": job["job_sha256"],
        "required_statement": statement,
        "run_id": "replace-me",
        "attempt_id": "replace-me",
        "expires_utc": "replace-me",
        "caps": job["resources"],
        "gpu_guard": job["gpu_guard"],
        "acknowledgements": {
            "model_load": False,
            "rank2_gate_training": False,
            "frozen_splits": False,
            "checkpointing": False,
            "abort_is_valid_outcome": False,
            "pid_scoped_cleanup": False,
            "prior_memory_abort": False,
            "no_automatic_authorization": False,
        },
    }
    (ROOT / "authorization_v0_1_1.template.json").write_text(
        json.dumps(authorization, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {"job": job, "authorization": authorization}


if __name__ == "__main__":
    packet = build()
    print(json.dumps({
        "status": packet["job"]["execution"]["state"],
        "job_sha256": packet["job"]["job_sha256"],
        "required_statement": packet["authorization"]["required_statement"],
    }, indent=2))
