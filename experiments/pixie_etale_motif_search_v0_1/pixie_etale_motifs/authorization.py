"""Fail-closed authorization receipts for model loading and capture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from .io import sha256_file


AUTHORIZATION_SCHEMA = "pixie_etale_motif_capture_authorization_v1"


@dataclass(frozen=True)
class Authorization:
    run_id: str
    attempt_id: str
    receipt: dict[str, Any]


def authorization_template(experiment_root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": AUTHORIZATION_SCHEMA,
        "authorized": False,
        "statement": protocol["authorization"]["required_statement"],
        "protocol_sha256": sha256_file(experiment_root / "protocol.json"),
        "run_id": "replace-me",
        "attempt_id": "replace-me",
        "expires_utc": "replace-me",
        "intervention_plan_sha256": None,
        "caps": protocol["resources"]["capture_requested_not_authorized"],
        "acknowledgements": {
            "model_load": False,
            "raw_safetensors_sharding": False,
            "activation_capture": False,
            "registered_intervention_forwards": False,
            "abort_is_valid_outcome": False,
            "pid_scoped_cleanup": False,
        },
    }


def validate_authorization(
    path: Path,
    experiment_root: Path,
    protocol: dict[str, Any],
    *,
    require_active_wrapper: bool,
) -> Authorization:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != AUTHORIZATION_SCHEMA:
        raise ValueError("invalid motif capture authorization schema")
    if value.get("authorized") is not True:
        raise ValueError("capture authorization is not active")
    if value.get("statement") != protocol["authorization"]["required_statement"]:
        raise ValueError("authorization statement differs from protocol")
    if value.get("protocol_sha256") != sha256_file(experiment_root / "protocol.json"):
        raise ValueError("authorization is bound to another protocol")
    if value.get("caps") != protocol["resources"]["capture_requested_not_authorized"]:
        raise ValueError("authorization caps differ from protocol")
    acknowledgements = value.get("acknowledgements", {})
    if not all(acknowledgements.get(key) is True for key in (
        "model_load",
        "raw_safetensors_sharding",
        "activation_capture",
        "registered_intervention_forwards",
        "abort_is_valid_outcome",
        "pid_scoped_cleanup",
    )):
        raise ValueError("authorization acknowledgements are incomplete")
    try:
        expires = datetime.fromisoformat(str(value["expires_utc"]).replace("Z", "+00:00"))
    except (KeyError, ValueError) as error:
        raise ValueError("authorization expires_utc is invalid") from error
    if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
        raise ValueError("authorization is expired")
    run_id = str(value.get("run_id", "")).strip()
    attempt_id = str(value.get("attempt_id", "")).strip()
    if not run_id or not attempt_id or run_id == "replace-me" or attempt_id == "replace-me":
        raise ValueError("authorization requires concrete run_id and attempt_id")
    if require_active_wrapper:
        if os.environ.get("PIXIE_RESOURCE_CAP_ACTIVE") != "1":
            raise ValueError("capture must run inside the resource-cap wrapper")
        if os.environ.get("PIXIE_RUN_ID") != run_id:
            raise ValueError("wrapper run ID differs from authorization")
    return Authorization(run_id=run_id, attempt_id=attempt_id, receipt=value)
