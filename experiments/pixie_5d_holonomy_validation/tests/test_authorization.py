from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixie_holonomy5d.authorization import AuthorizationError, validate_authorization
from pixie_holonomy5d.protocol import sha256_file


CAPS = {"ram_mb": 6144, "cpu_pct": 50, "io_mb_s": 250, "timeout_seconds": 1800}
WRAPPER_HASH = "a" * 64


def make_protocol(path: Path) -> dict[str, object]:
    protocol: dict[str, object] = {
        "experiment_id": "test-experiment",
        "resources": {"capture_requested_not_authorized": CAPS},
        "bounded_launcher": {"sha256": WRAPPER_HASH},
    }
    path.write_text(json.dumps(protocol), encoding="utf-8")
    return protocol


def make_receipt(path: Path, protocol_path: Path, **changes: object) -> None:
    value: dict[str, object] = {
        "schema": "pixie_5d_capture_authorization_v1",
        "authorized": True,
        "authorization_statement": "I explicitly authorize this run under the exact caps in this receipt.",
        "experiment_id": "test-experiment",
        "protocol_sha256": sha256_file(protocol_path),
        "run_id": "unit-test-01",
        "issued_by": "test operator",
        "issued_at_utc": "2026-07-21T12:00:00Z",
        "caps": CAPS,
    }
    value.update(changes)
    path.write_text(json.dumps(value), encoding="utf-8")


def wrapper_environment() -> dict[str, str]:
    return {
        "PIXIE_RESOURCE_CAP_ACTIVE": "1",
        "PIXIE_RUN_ID": "unit-test-01",
        "PIXIE_CAP_RAM_MB": "6144",
        "PIXIE_CAP_CPU_PCT": "50",
        "PIXIE_CAP_IO_MB_S": "250",
        "PIXIE_CAP_TIMEOUT_SECONDS": "1800",
        "PIXIE_CAP_WRAPPER_SHA256": WRAPPER_HASH,
    }


def test_authorization_requires_exact_protocol_and_active_caps(tmp_path: Path) -> None:
    protocol_path = tmp_path / "protocol.json"
    receipt_path = tmp_path / "authorization.json"
    protocol = make_protocol(protocol_path)
    make_receipt(receipt_path, protocol_path)
    receipt = validate_authorization(
        receipt_path,
        protocol_path,
        protocol,
        require_active_wrapper=True,
        environment=wrapper_environment(),
    )
    assert receipt.run_id == "unit-test-01"
    assert receipt.caps == CAPS


def test_authorization_rejects_cap_drift(tmp_path: Path) -> None:
    protocol_path = tmp_path / "protocol.json"
    receipt_path = tmp_path / "authorization.json"
    protocol = make_protocol(protocol_path)
    make_receipt(receipt_path, protocol_path, caps={**CAPS, "ram_mb": 8192})
    with pytest.raises(AuthorizationError, match="do not exactly match"):
        validate_authorization(receipt_path, protocol_path, protocol, require_active_wrapper=False)


def test_authorization_rejects_uncapped_direct_launch(tmp_path: Path) -> None:
    protocol_path = tmp_path / "protocol.json"
    receipt_path = tmp_path / "authorization.json"
    protocol = make_protocol(protocol_path)
    make_receipt(receipt_path, protocol_path)
    with pytest.raises(AuthorizationError, match="not inside the exact capped wrapper"):
        validate_authorization(
            receipt_path,
            protocol_path,
            protocol,
            require_active_wrapper=True,
            environment={},
        )
