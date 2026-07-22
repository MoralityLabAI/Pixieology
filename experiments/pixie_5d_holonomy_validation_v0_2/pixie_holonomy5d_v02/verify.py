"""Frozen-source and v0.1 lineage verification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .protocol import load_protocol, load_repo_config, resolve_config_path, sha256_file


def cap_evidence_valid(cap_evidence: dict[str, Any], protocol: dict[str, Any]) -> bool:
    """Validate the destructive self-test and its exact launcher lineage."""
    readback = cap_evidence.get("job_object_readback", {})
    configured_bytes = int(cap_evidence.get("test", {}).get("configured_memory_mb", -1)) * 1024 * 1024
    required_flags = 0x100 | 0x200 | 0x2000
    return bool(
        cap_evidence.get("status") == "PASS"
        and cap_evidence.get("test", {}).get("abort_reason") == "os_memory_cap_termination"
        and cap_evidence.get("test", {}).get("unexpected_completion_marker") is False
        and int(readback.get("limit_flags", 0)) & required_flags == required_flags
        and int(readback.get("process_memory_limit_bytes", -1)) == configured_bytes
        and int(readback.get("job_memory_limit_bytes", -1)) == configured_bytes
        and cap_evidence.get("implementation_sha256", {}).get(protocol["bounded_launcher"]["path"])
        == protocol["bounded_launcher"]["sha256"]
        and cap_evidence.get("implementation_sha256", {}).get(protocol["bounded_launcher"]["owned_process_gate_path"])
        == protocol["bounded_launcher"]["owned_process_gate_sha256"]
    )


def protocol_lock_checks(experiment_root: Path) -> dict[str, bool]:
    """Return fail-closed checks for the post-implementation protocol lock."""
    lock_path = experiment_root / "protocol.lock.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"protocol_lock_present": False}
    checks = {
        "protocol_lock_present": lock.get("schema") == "pixie_5d_holonomy_protocol_lock_v2",
        "protocol_lock_protocol": lock.get("protocol_sha256") == sha256_file(experiment_root / "protocol.json"),
        "protocol_lock_base_commit": isinstance(lock.get("implementation_git_commit"), str)
        and len(lock["implementation_git_commit"]) == 40,
    }
    files = lock.get("files", {})
    if not isinstance(files, dict) or not files:
        checks["protocol_lock_files"] = False
        return checks
    for relative, expected in files.items():
        path = experiment_root / relative
        checks[f"protocol_lock:{relative}"] = path.is_file() and sha256_file(path) == expected
    return checks


def verify(repo_root: Path, experiment_root: Path) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    config = load_repo_config(repo_root)
    v01_experiment = resolve_config_path(repo_root, config, "pixie_5d_holonomy_experiment_root")
    v01_output = resolve_config_path(repo_root, config, "pixie_5d_holonomy_output_root")
    model = resolve_config_path(repo_root, config, "godel_globes_bonsai_unpacked_hf")
    adapter = resolve_config_path(repo_root, config, "godel_globes_bonsai_adapter")
    source_run = v01_output / "capture" / protocol["continuation"]["source_run_id"]
    checks: dict[str, bool] = {
        "source_protocol": sha256_file(v01_experiment / "protocol.json") == protocol["continuation"]["source_protocol_sha256"],
        "model_config": sha256_file(model / "config.json") == protocol["model"]["config_sha256"],
        "adapter_config": sha256_file(adapter / "adapter_config.json") == protocol["adapter"]["config_sha256"],
        "adapter_weights": sha256_file(adapter / "adapter_model.safetensors") == protocol["adapter"]["weights_sha256"],
        "train_data": sha256_file(repo_root / protocol["data"]["train_path"]) == protocol["data"]["train_sha256"],
        "eval_data": sha256_file(repo_root / protocol["data"]["eval_path"]) == protocol["data"]["eval_sha256"],
    }
    checks.update(protocol_lock_checks(experiment_root))
    for label, receipt in protocol["continuation"]["source_receipts"].items():
        checks[f"receipt:{label}"] = sha256_file(repo_root / receipt["path"]) == receipt["sha256"]
    for relative, expected in protocol["continuation"]["reused_artifacts"].items():
        checks[f"artifact:{relative}"] = sha256_file(source_run / relative) == expected
    for relative, expected in protocol["source_modules"].items():
        checks[f"module:{relative}"] = sha256_file(repo_root / relative) == expected
    launcher = experiment_root / protocol["bounded_launcher"]["path"]
    invoker = experiment_root / protocol["bounded_launcher"]["owned_process_gate_path"]
    cap_receipt = experiment_root / protocol["bounded_launcher"]["cap_self_test_receipt_path"]
    checks["v02_launcher"] = sha256_file(launcher) == protocol["bounded_launcher"]["sha256"]
    checks["v02_invoker"] = sha256_file(invoker) == protocol["bounded_launcher"]["owned_process_gate_sha256"]
    checks["cap_self_test"] = sha256_file(cap_receipt) == protocol["bounded_launcher"]["cap_self_test_receipt_sha256"]
    try:
        cap_evidence = json.loads(cap_receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cap_evidence = {}
    checks["cap_self_test_semantics"] = cap_evidence_valid(cap_evidence, protocol)
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "source_run": str(source_run),
        "model": str(model),
        "adapter": str(adapter),
        "launcher": str(launcher),
    }
