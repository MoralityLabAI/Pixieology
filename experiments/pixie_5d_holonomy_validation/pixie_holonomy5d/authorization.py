"""Fail-closed authorization checks for the bounded real-model capture."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .protocol import sha256_file


AUTHORIZATION_SCHEMA = "pixie_5d_capture_authorization_v1"
AUTHORIZATION_STATEMENT = "I explicitly authorize this run under the exact caps in this receipt."


class AuthorizationError(RuntimeError):
    """The capture lacks an exact, current resource authorization receipt."""


@dataclass(frozen=True)
class Authorization:
    run_id: str
    issued_by: str
    caps: dict[str, int]
    receipt: dict[str, Any]


def _integer_caps(value: Mapping[str, Any]) -> dict[str, int]:
    names = ("ram_mb", "cpu_pct", "io_mb_s", "timeout_seconds")
    if set(value) != set(names):
        raise AuthorizationError(f"authorization caps must contain exactly {names}")
    output: dict[str, int] = {}
    for name in names:
        item = value[name]
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise AuthorizationError(f"authorization cap {name} must be a positive integer")
        output[name] = item
    return output


def validate_authorization(
    receipt_path: Path,
    protocol_path: Path,
    protocol: Mapping[str, Any],
    *,
    require_active_wrapper: bool,
    environment: Mapping[str, str] | None = None,
) -> Authorization:
    """Validate exact protocol, cap, and wrapper agreement.

    The receipt is an audit record of explicit human authorization, not a
    cryptographic signature. The capped launcher independently enforces the
    same values through a Windows Job Object; the child verifies the launcher's
    environment before importing Torch or loading a model.
    """
    try:
        value = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise AuthorizationError(f"cannot read authorization receipt: {error}") from error
    if not isinstance(value, dict) or value.get("schema") != AUTHORIZATION_SCHEMA:
        raise AuthorizationError("invalid authorization schema")
    if value.get("authorized") is not True:
        raise AuthorizationError("authorization receipt does not set authorized=true")
    if value.get("authorization_statement") != AUTHORIZATION_STATEMENT:
        raise AuthorizationError("authorization receipt lacks the exact explicit authorization statement")
    if value.get("experiment_id") != protocol.get("experiment_id"):
        raise AuthorizationError("authorization experiment_id differs from the protocol")
    if value.get("protocol_sha256") != sha256_file(protocol_path):
        raise AuthorizationError("authorization protocol hash is stale or incorrect")
    run_id = value.get("run_id")
    issued_by = value.get("issued_by")
    issued_at = value.get("issued_at_utc")
    if not isinstance(run_id, str) or not run_id.strip() or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in run_id):
        raise AuthorizationError("authorization run_id must be a non-empty filesystem-safe identifier")
    if not isinstance(issued_by, str) or not issued_by.strip():
        raise AuthorizationError("authorization issued_by must identify the authorizing person")
    if not isinstance(issued_at, str) or not issued_at.strip():
        raise AuthorizationError("authorization issued_at_utc is required")
    caps = _integer_caps(value.get("caps", {}))
    requested = _integer_caps(protocol["resources"]["capture_requested_not_authorized"])
    if caps != requested:
        raise AuthorizationError(f"authorized caps {caps} do not exactly match requested caps {requested}")

    if require_active_wrapper:
        env = os.environ if environment is None else environment
        expected_environment = {
            "PIXIE_RESOURCE_CAP_ACTIVE": "1",
            "PIXIE_RUN_ID": run_id,
            "PIXIE_CAP_RAM_MB": str(caps["ram_mb"]),
            "PIXIE_CAP_CPU_PCT": str(caps["cpu_pct"]),
            "PIXIE_CAP_IO_MB_S": str(caps["io_mb_s"]),
            "PIXIE_CAP_TIMEOUT_SECONDS": str(caps["timeout_seconds"]),
            "PIXIE_CAP_WRAPPER_SHA256": str(protocol["bounded_launcher"]["sha256"]),
        }
        mismatches = {
            name: {"expected": expected, "actual": env.get(name)}
            for name, expected in expected_environment.items()
            if env.get(name) != expected
        }
        if mismatches:
            raise AuthorizationError(f"capture is not inside the exact capped wrapper: {mismatches}")
    return Authorization(run_id=run_id, issued_by=issued_by, caps=caps, receipt=value)


def authorization_template(protocol_path: Path, protocol: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deliberately non-authorizing template bound to this protocol."""
    return {
        "schema": AUTHORIZATION_SCHEMA,
        "authorized": False,
        "authorization_statement": AUTHORIZATION_STATEMENT,
        "experiment_id": protocol["experiment_id"],
        "protocol_sha256": sha256_file(protocol_path),
        "run_id": "replace-with-run-id",
        "issued_by": "",
        "issued_at_utc": "",
        "caps": dict(protocol["resources"]["capture_requested_not_authorized"]),
    }
