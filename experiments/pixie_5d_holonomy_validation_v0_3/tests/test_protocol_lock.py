from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pixie_holonomy5d_v03.verify import protocol_lock_checks


def test_v03_lock_is_fail_closed_and_detects_drift(tmp_path: Path) -> None:
    protocol = tmp_path / "protocol.json"
    source = tmp_path / "run.py"
    protocol.write_text("{}", encoding="utf-8")
    source.write_text("frozen\n", encoding="utf-8")
    assert protocol_lock_checks(tmp_path) == {"protocol_lock_present": False}
    lock = {
        "schema": "pixie_5d_holonomy_protocol_lock_v3",
        "implementation_git_commit": "a" * 40,
        "protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
        "files": {"run.py": hashlib.sha256(source.read_bytes()).hexdigest()},
    }
    (tmp_path / "protocol.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    assert all(protocol_lock_checks(tmp_path).values())
    source.write_text("drift\n", encoding="utf-8")
    assert not protocol_lock_checks(tmp_path)["protocol_lock:run.py"]
