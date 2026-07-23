"""Fail-closed authorization bound to one immutable feedback job."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from pixie_etale_motifs.io import sha256_file

from .jobs import job_sha256, validate_job


AUTH_SCHEMA = "pixieology_lora_feedback_authorization_v1"


@dataclass(frozen=True)
class FeedbackAuthorization:
    run_id: str
    attempt_id: str
    receipt: dict[str, Any]


def authorization_template(
    experiment_root: Path,
    protocol: dict[str, Any],
    job: dict[str, Any],
) -> dict[str, Any]:
    validate_job(job)
    if job["status"] != "PROPOSED":
        raise ValueError("only an executable proposed job can receive an authorization template")
    return {
        "schema": AUTH_SCHEMA,
        "authorized": False,
        "statement": protocol["authorization"]["required_statement"],
        "protocol_sha256": sha256_file(experiment_root / "protocol.json"),
        "implementation_lock_sha256": sha256_file(experiment_root / "protocol.lock.json"),
        "job_id": job["job_id"],
        "job_sha256": job_sha256(job),
        "run_id": "replace-me",
        "attempt_id": "replace-me",
        "expires_utc": "replace-me",
        "caps": protocol["resources"]["training_requested_not_authorized"],
        "gpu_guard": protocol["resources"]["gpu"],
        "acknowledgements": {
            "model_load": False,
            "training_or_evaluation": False,
            "held_out_splits_remain_frozen": False,
            "abort_is_valid_outcome": False,
            "pid_scoped_cleanup": False,
            "no_automatic_authorization": False,
        },
    }


def validate_authorization(
    path: Path,
    experiment_root: Path,
    protocol: dict[str, Any],
    job: dict[str, Any],
    *,
    require_active_wrapper: bool,
) -> FeedbackAuthorization:
    validate_job(job)
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != AUTH_SCHEMA or value.get("authorized") is not True:
        raise ValueError("feedback authorization is not active")
    if value.get("statement") != protocol["authorization"]["required_statement"]:
        raise ValueError("feedback authorization statement differs from protocol")
    if value.get("protocol_sha256") != sha256_file(experiment_root / "protocol.json"):
        raise ValueError("feedback authorization belongs to another protocol")
    if value.get("implementation_lock_sha256") != sha256_file(experiment_root / "protocol.lock.json"):
        raise ValueError("feedback authorization belongs to another implementation lock")
    if value.get("job_id") != job["job_id"] or value.get("job_sha256") != job_sha256(job):
        raise ValueError("feedback authorization belongs to another job")
    if value.get("caps") != protocol["resources"]["training_requested_not_authorized"]:
        raise ValueError("feedback authorization caps differ from protocol")
    if value.get("gpu_guard") != protocol["resources"]["gpu"]:
        raise ValueError("feedback authorization GPU guard differs from protocol")
    acknowledgements = value.get("acknowledgements", {})
    required = {
        "model_load",
        "training_or_evaluation",
        "held_out_splits_remain_frozen",
        "abort_is_valid_outcome",
        "pid_scoped_cleanup",
        "no_automatic_authorization",
    }
    if not all(acknowledgements.get(key) is True for key in required):
        raise ValueError("feedback authorization acknowledgements are incomplete")
    try:
        expires = datetime.fromisoformat(str(value["expires_utc"]).replace("Z", "+00:00"))
    except (KeyError, ValueError) as error:
        raise ValueError("feedback authorization expires_utc is invalid") from error
    if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
        raise ValueError("feedback authorization is expired")
    run_id = str(value.get("run_id", "")).strip()
    attempt_id = str(value.get("attempt_id", "")).strip()
    if not run_id or not attempt_id or "replace-me" in {run_id, attempt_id}:
        raise ValueError("feedback authorization requires concrete run and attempt IDs")
    if require_active_wrapper:
        if os.environ.get("PIXIE_RESOURCE_CAP_ACTIVE") != "1":
            raise ValueError("feedback execution must run inside the hard-cap wrapper")
        if os.environ.get("PIXIE_RUN_ID") != run_id:
            raise ValueError("wrapper run ID differs from feedback authorization")
    return FeedbackAuthorization(run_id=run_id, attempt_id=attempt_id, receipt=value)
