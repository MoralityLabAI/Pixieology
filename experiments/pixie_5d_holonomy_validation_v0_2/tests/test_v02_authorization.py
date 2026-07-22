from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixie_holonomy5d_v02.authorization import AuthorizationError, STATEMENT, template, validate


def _protocol() -> dict:
    return {
        "experiment_id": "exp",
        "continuation": {"continuation_id": "continuation"},
        "resources": {
            "capture_requested_not_authorized": {
                "ram_mb": 6144,
                "cpu_pct": 50,
                "io_mb_s": 250,
                "timeout_seconds": 1800,
            }
        },
        "bounded_launcher": {"sha256": "wrapper-hash"},
    }


def _write_receipt(tmp_path: Path, protocol_path: Path, protocol: dict) -> Path:
    value = template(protocol_path, protocol)
    value.update(
        authorized=True,
        attempt_id="attempt-01",
        issued_by="test",
        issued_at_utc="2026-07-22T12:00:00Z",
    )
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_authorization_requires_exact_wrapper_environment(tmp_path: Path) -> None:
    protocol = _protocol()
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    receipt = _write_receipt(tmp_path, protocol_path, protocol)
    expected = {
        "PIXIE_RESOURCE_CAP_ACTIVE": "1",
        "PIXIE_RUN_ID": "continuation",
        "PIXIE_ATTEMPT_ID": "attempt-01",
        "PIXIE_CAP_RAM_MB": "6144",
        "PIXIE_CAP_CPU_PCT": "50",
        "PIXIE_CAP_IO_MB_S": "250",
        "PIXIE_CAP_TIMEOUT_SECONDS": "1800",
        "PIXIE_CAP_WRAPPER_SHA256": "wrapper-hash",
    }
    assert validate(receipt, protocol_path, protocol, require_active_wrapper=True, environment=expected)["authorized"]
    expected["PIXIE_CAP_RAM_MB"] = "6145"
    with pytest.raises(AuthorizationError, match="outside the exact v0.2 wrapper"):
        validate(receipt, protocol_path, protocol, require_active_wrapper=True, environment=expected)


def test_authorization_rejects_stale_protocol(tmp_path: Path) -> None:
    protocol = _protocol()
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    receipt = _write_receipt(tmp_path, protocol_path, protocol)
    protocol_path.write_text(json.dumps({**protocol, "changed": True}), encoding="utf-8")
    with pytest.raises(AuthorizationError, match="stale"):
        validate(receipt, protocol_path, protocol, require_active_wrapper=False)


def test_template_is_not_authorization(tmp_path: Path) -> None:
    protocol = _protocol()
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    value = template(protocol_path, protocol)
    assert value["authorized"] is False
    assert value["authorization_statement"] == STATEMENT
