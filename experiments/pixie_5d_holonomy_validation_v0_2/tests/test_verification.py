from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pixie_holonomy5d_v02.verify import cap_evidence_valid, protocol_lock_checks


def _protocol() -> dict:
    return {
        "bounded_launcher": {
            "path": "scripts/run_capped_v2.ps1",
            "sha256": "launcher",
            "owned_process_gate_path": "scripts/invoke_owned_v2.ps1",
            "owned_process_gate_sha256": "invoker",
        }
    }


def _evidence() -> dict:
    return {
        "status": "PASS",
        "test": {
            "configured_memory_mb": 128,
            "abort_reason": "os_memory_cap_termination",
            "unexpected_completion_marker": False,
        },
        "job_object_readback": {
            "limit_flags": 0x100 | 0x200 | 0x2000,
            "process_memory_limit_bytes": 128 * 1024 * 1024,
            "job_memory_limit_bytes": 128 * 1024 * 1024,
        },
        "implementation_sha256": {
            "scripts/run_capped_v2.ps1": "launcher",
            "scripts/invoke_owned_v2.ps1": "invoker",
        },
    }


def test_cap_evidence_requires_readback_and_termination() -> None:
    evidence = _evidence()
    assert cap_evidence_valid(evidence, _protocol())
    evidence["job_object_readback"]["limit_flags"] = 0
    assert not cap_evidence_valid(evidence, _protocol())


def test_cap_evidence_rejects_unexpected_probe_completion() -> None:
    evidence = _evidence()
    evidence["test"]["unexpected_completion_marker"] = True
    assert not cap_evidence_valid(evidence, _protocol())


def test_protocol_lock_is_fail_closed_and_detects_drift(tmp_path: Path) -> None:
    protocol = tmp_path / "protocol.json"
    frozen = tmp_path / "run.py"
    protocol.write_text("{}", encoding="utf-8")
    frozen.write_text("print('frozen')\n", encoding="utf-8")
    assert protocol_lock_checks(tmp_path) == {"protocol_lock_present": False}
    lock = {
        "schema": "pixie_5d_holonomy_protocol_lock_v2",
        "implementation_git_commit": "a" * 40,
        "protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
        "files": {"run.py": hashlib.sha256(frozen.read_bytes()).hexdigest()},
    }
    (tmp_path / "protocol.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    assert all(protocol_lock_checks(tmp_path).values())
    frozen.write_text("print('drift')\n", encoding="utf-8")
    assert not protocol_lock_checks(tmp_path)["protocol_lock:run.py"]
