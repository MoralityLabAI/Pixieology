"""Fail-closed, job- and implementation-bound authorization receipts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from .protocol import job_sha256, protocol_hash, sha256_file


AUTHORIZATION_SCHEMA = "pixie_bnb_quantization_canary_authorization_v3"


@dataclass(frozen=True)
class Authorization:
    run_id: str
    attempt_id: str
    receipt: dict[str, Any]


def authorization_template(
    experiment_root: Path,
    protocol: dict[str, Any],
    job: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": AUTHORIZATION_SCHEMA,
        "authorized": False,
        "statement": protocol["authorization"]["required_statement"],
        "protocol_sha256": protocol_hash(experiment_root),
        "implementation_lock_sha256": sha256_file(experiment_root / "protocol.lock.json"),
        "job_id": job["job_id"],
        "job_sha256": job_sha256(job),
        "run_id": "replace-me",
        "attempt_id": "replace-me",
        "expires_utc": "replace-me",
        "caps": protocol["resources"]["canary_requested_not_authorized"],
        "gpu_guard": protocol["resources"]["gpu"],
        "acknowledgements": {
            "cuda_tensor_allocation": False,
            "deterministic_synthetic_weights": False,
            "bitsandbytes_nf4_quantization": False,
            "qwen_shape_sweep": False,
            "chatgpt_gpu_host_exception": False,
            "no_model_or_adapter_loading": False,
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
) -> Authorization:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if value.get("schema") != AUTHORIZATION_SCHEMA:
        raise ValueError("invalid quantization canary authorization schema")
    if value.get("authorized") is not True:
        raise ValueError("quantization canary authorization is not active")
    if value.get("statement") != protocol["authorization"]["required_statement"]:
        raise ValueError("authorization statement differs from protocol")
    if value.get("protocol_sha256") != protocol_hash(experiment_root):
        raise ValueError("authorization is bound to another protocol")
    if value.get("implementation_lock_sha256") != sha256_file(experiment_root / "protocol.lock.json"):
        raise ValueError("authorization is bound to another implementation lock")
    if value.get("job_id") != job["job_id"] or value.get("job_sha256") != job_sha256(job):
        raise ValueError("authorization is bound to another job")
    if value.get("caps") != protocol["resources"]["canary_requested_not_authorized"]:
        raise ValueError("authorization caps differ from protocol")
    if value.get("gpu_guard") != protocol["resources"]["gpu"]:
        raise ValueError("authorization GPU guard differs from protocol")
    required = (
        "cuda_tensor_allocation",
        "deterministic_synthetic_weights",
        "bitsandbytes_nf4_quantization",
        "qwen_shape_sweep",
        "chatgpt_gpu_host_exception",
        "no_model_or_adapter_loading",
        "abort_is_valid_outcome",
        "pid_scoped_cleanup",
        "no_automatic_authorization",
    )
    acknowledgements = value.get("acknowledgements", {})
    if not all(acknowledgements.get(key) is True for key in required):
        raise ValueError("authorization acknowledgements are incomplete")
    try:
        expires = datetime.fromisoformat(str(value["expires_utc"]).replace("Z", "+00:00"))
    except (KeyError, ValueError) as error:
        raise ValueError("authorization expires_utc is invalid") from error
    if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
        raise ValueError("authorization is expired")
    run_id = str(value.get("run_id", "")).strip()
    attempt_id = str(value.get("attempt_id", "")).strip()
    if not run_id or not attempt_id or "replace-me" in {run_id, attempt_id}:
        raise ValueError("authorization requires concrete run_id and attempt_id")
    if require_active_wrapper:
        if os.environ.get("PIXIE_RESOURCE_CAP_ACTIVE") != "1":
            raise ValueError("quantization canary must run inside the resource-cap wrapper")
        if os.environ.get("PIXIE_RUN_ID") != run_id:
            raise ValueError("wrapper run ID differs from authorization")
        if os.environ.get("PIXIE_ATTEMPT_ID") != attempt_id:
            raise ValueError("wrapper attempt ID differs from authorization")
    return Authorization(run_id=run_id, attempt_id=attempt_id, receipt=value)
