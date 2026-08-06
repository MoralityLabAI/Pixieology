"""Protocol and implementation-lock verification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io_utils import file_sha256


PROTOCOL_SCHEMA = "pixieology_mechanism_distillation_protocol_v1"
LOCK_SCHEMA = "pixieology_mechanism_distillation_lock_v1"


def load_protocol(root: Path) -> dict[str, Any]:
    value = json.loads((root / "protocol.json").read_text(encoding="utf-8-sig"))
    if value.get("schema") != PROTOCOL_SCHEMA:
        raise ValueError("invalid mechanism protocol schema")
    if value.get("status") != "STAGED_NOT_AUTHORIZED":
        raise ValueError("protocol must remain staged before an explicit receipt")
    if value.get("authorization", {}).get("automatic_authorization") is not False:
        raise ValueError("automatic authorization must be false")
    return value


def implementation_files(root: Path) -> list[Path]:
    patterns = [
        "*.md", "*.json", "*.jsonl", "*.yaml", "run.py",
        "pixie_mechanism_distillation/*.py", "schemas/*.json", "tests/*.py",
    ]
    paths = set()
    for pattern in patterns:
        paths.update(path for path in root.glob(pattern) if path.is_file())
    return sorted(
        path for path in paths
        if path.name not in {"protocol.lock.json"}
        and not path.name.startswith("PREFLIGHT_")
    )


def build_lock(root: Path) -> dict[str, Any]:
    protocol = load_protocol(root)
    return {
        "schema": LOCK_SCHEMA,
        "experiment_id": protocol["experiment_id"],
        "protocol_sha256": file_sha256(root / "protocol.json"),
        "files": {
            path.relative_to(root).as_posix(): file_sha256(path)
            for path in implementation_files(root)
        },
    }


def verify_lock(root: Path) -> dict[str, Any]:
    expected = build_lock(root)
    lock_path = root / "protocol.lock.json"
    if not lock_path.is_file():
        return {"ok": False, "reason": "protocol.lock.json is missing", "expected": expected}
    observed = json.loads(lock_path.read_text(encoding="utf-8-sig"))
    return {
        "ok": observed == expected,
        "reason": None if observed == expected else "implementation lock differs",
        "expected": expected,
        "observed": observed,
    }


def verify_staged_job(root: Path) -> dict[str, Any]:
    job = json.loads((root / "proposed_capture_job.json").read_text(encoding="utf-8-sig"))
    checks = {
        "schema": job.get("schema") == "pixieology_mechanism_capture_job_v1",
        "status": job.get("status") == "STAGED_NOT_AUTHORIZED",
        "authorization_required": job.get("authorization", {}).get("required") is True,
        "not_authorized": job.get("authorization", {}).get("status") == "NOT_AUTHORIZED",
        "no_automatic_authorization": job.get("authorization", {}).get("automatic") is False,
        "sequential_conditions": job.get("conditions") == ["base_qwen_derived_1p7b", "pixie_rank8"],
    }
    return {"ok": all(checks.values()), "checks": checks}
