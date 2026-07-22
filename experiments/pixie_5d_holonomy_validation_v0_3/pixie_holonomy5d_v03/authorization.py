"""Exact authorization gate for the v0.3 sharded-loader continuation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from .protocol import sha256_file


SCHEMA = "pixie_5d_context3_sharded_authorization_v3"
STATEMENT = "I explicitly authorize the v0.3 sharded context-3 continuation under the exact caps in this receipt."


class AuthorizationError(RuntimeError):
    pass


def template(protocol_path: Path, protocol: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "authorized": False,
        "authorization_statement": STATEMENT,
        "experiment_id": protocol["experiment_id"],
        "protocol_sha256": sha256_file(protocol_path),
        "continuation_id": protocol["continuation"]["continuation_id"],
        "attempt_id": "replace-with-unique-attempt-id",
        "issued_by": "",
        "issued_at_utc": "",
        "caps": dict(protocol["resources"]["capture_requested_not_authorized"]),
        "loader_change": dict(protocol["loader"]),
        "sharding_recipe": dict(protocol["sharding"]),
    }


def validate(
    receipt_path: Path,
    protocol_path: Path,
    protocol: Mapping[str, Any],
    *,
    require_active_wrapper: bool,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    try:
        value = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise AuthorizationError(f"cannot read authorization: {error}") from error
    if value.get("schema") != SCHEMA or value.get("authorized") is not True:
        raise AuthorizationError("receipt schema or authorized flag is invalid")
    if value.get("authorization_statement") != STATEMENT:
        raise AuthorizationError("explicit v0.3 authorization statement is missing or changed")
    if value.get("experiment_id") != protocol["experiment_id"]:
        raise AuthorizationError("receipt experiment_id differs from protocol")
    if value.get("protocol_sha256") != sha256_file(protocol_path):
        raise AuthorizationError("receipt protocol hash is stale")
    if value.get("continuation_id") != protocol["continuation"]["continuation_id"]:
        raise AuthorizationError("receipt continuation_id differs from protocol")
    for name in ("attempt_id", "issued_by", "issued_at_utc"):
        if not isinstance(value.get(name), str) or not value[name].strip():
            raise AuthorizationError(f"receipt {name} is required")
    if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in value["attempt_id"]):
        raise AuthorizationError("attempt_id must be filesystem safe")
    requested = protocol["resources"]["capture_requested_not_authorized"]
    if value.get("caps") != requested:
        raise AuthorizationError("receipt caps do not exactly equal protocol caps")
    if value.get("loader_change") != protocol["loader"]:
        raise AuthorizationError("receipt does not acknowledge the exact v0.3 loader")
    if value.get("sharding_recipe") != protocol["sharding"]:
        raise AuthorizationError("receipt does not acknowledge the exact sharding recipe")
    if require_active_wrapper:
        env = os.environ if environment is None else environment
        expected = {
            "PIXIE_RESOURCE_CAP_ACTIVE": "1",
            "PIXIE_RUN_ID": protocol["continuation"]["continuation_id"],
            "PIXIE_ATTEMPT_ID": value["attempt_id"],
            "PIXIE_CAP_RAM_MB": str(requested["ram_mb"]),
            "PIXIE_CAP_CPU_PCT": str(requested["cpu_pct"]),
            "PIXIE_CAP_IO_MB_S": str(requested["io_mb_s"]),
            "PIXIE_CAP_TIMEOUT_SECONDS": str(requested["timeout_seconds"]),
            "PIXIE_CAP_WRAPPER_SHA256": protocol["bounded_launcher"]["sha256"],
        }
        mismatch = {
            name: {"expected": expected_value, "actual": env.get(name)}
            for name, expected_value in expected.items()
            if env.get(name) != expected_value
        }
        if mismatch:
            raise AuthorizationError(f"continuation is outside the exact v0.3 wrapper: {mismatch}")
    return value
