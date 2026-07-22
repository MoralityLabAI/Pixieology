from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixie_holonomy5d_v03.authorization import AuthorizationError, template, validate


def _protocol() -> dict:
    return {
        "experiment_id": "v03",
        "continuation": {"continuation_id": "context3"},
        "resources": {
            "capture_requested_not_authorized": {
                "ram_mb": 6144,
                "cpu_pct": 50,
                "io_mb_s": 250,
                "timeout_seconds": 1800,
            }
        },
        "bounded_launcher": {"sha256": "wrapper"},
        "loader": {"checkpoint_form": "sharded"},
        "sharding": {"target_shard_bytes": 32},
    }


def test_v03_receipt_acknowledges_loader_and_sharding(tmp_path: Path) -> None:
    protocol = _protocol()
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    value = template(protocol_path, protocol)
    value.update(authorized=True, attempt_id="attempt-1", issued_by="test", issued_at_utc="2026-07-22T00:00:00Z")
    receipt = tmp_path / "authorization.json"
    receipt.write_text(json.dumps(value), encoding="utf-8")
    assert validate(receipt, protocol_path, protocol, require_active_wrapper=False)["authorized"]
    value["sharding_recipe"]["target_shard_bytes"] = 64
    receipt.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(AuthorizationError, match="sharding recipe"):
        validate(receipt, protocol_path, protocol, require_active_wrapper=False)


def test_v03_receipt_requires_exact_wrapper_environment(tmp_path: Path) -> None:
    protocol = _protocol()
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    value = template(protocol_path, protocol)
    value.update(authorized=True, attempt_id="attempt-1", issued_by="test", issued_at_utc="2026-07-22T00:00:00Z")
    receipt = tmp_path / "authorization.json"
    receipt.write_text(json.dumps(value), encoding="utf-8")
    environment = {
        "PIXIE_RESOURCE_CAP_ACTIVE": "1",
        "PIXIE_RUN_ID": "context3",
        "PIXIE_ATTEMPT_ID": "attempt-1",
        "PIXIE_CAP_RAM_MB": "6144",
        "PIXIE_CAP_CPU_PCT": "50",
        "PIXIE_CAP_IO_MB_S": "250",
        "PIXIE_CAP_TIMEOUT_SECONDS": "1800",
        "PIXIE_CAP_WRAPPER_SHA256": "wrapper",
    }
    assert validate(receipt, protocol_path, protocol, require_active_wrapper=True, environment=environment)
    environment["PIXIE_CAP_RAM_MB"] = "6145"
    with pytest.raises(AuthorizationError, match="outside the exact v0.3 wrapper"):
        validate(receipt, protocol_path, protocol, require_active_wrapper=True, environment=environment)
