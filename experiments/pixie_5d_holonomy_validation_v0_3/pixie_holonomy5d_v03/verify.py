"""Fail-closed lineage, implementation, model, and cap verification for v0.3."""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
from typing import Any

from .protocol import load_protocol, load_repo_config, resolve_config_path, sha256_file


def _hash_matches(path: Path, expected: str) -> bool:
    return path.is_file() and sha256_file(path) == expected


def protocol_lock_checks(experiment_root: Path) -> dict[str, bool]:
    lock_path = experiment_root / "protocol.lock.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"protocol_lock_present": False}
    checks = {
        "protocol_lock_present": lock.get("schema") == "pixie_5d_holonomy_protocol_lock_v3",
        "protocol_lock_protocol": lock.get("protocol_sha256") == sha256_file(experiment_root / "protocol.json"),
        "protocol_lock_base_commit": isinstance(lock.get("implementation_git_commit"), str)
        and len(lock["implementation_git_commit"]) == 40,
    }
    files = lock.get("files", {})
    if not isinstance(files, dict) or not files:
        checks["protocol_lock_files"] = False
        return checks
    for relative, expected in files.items():
        checks[f"protocol_lock:{relative}"] = _hash_matches(experiment_root / relative, expected)
    return checks


def _cap_semantics(receipt: dict[str, Any], protocol: dict[str, Any]) -> bool:
    readback = receipt.get("job_object_readback", {})
    configured = int(receipt.get("test", {}).get("configured_memory_mb", -1)) * 1024 * 1024
    required_flags = 0x100 | 0x200 | 0x2000
    return bool(
        receipt.get("status") == "PASS"
        and receipt.get("test", {}).get("abort_reason") == "os_memory_cap_termination"
        and receipt.get("test", {}).get("unexpected_completion_marker") is False
        and int(readback.get("limit_flags", 0)) & required_flags == required_flags
        and int(readback.get("process_memory_limit_bytes", -1)) == configured
        and int(readback.get("job_memory_limit_bytes", -1)) == configured
        and receipt.get("implementation_sha256", {}).get("scripts/run_capped_v2.ps1")
        == protocol["bounded_launcher"]["sha256"]
        and receipt.get("implementation_sha256", {}).get("scripts/invoke_owned_v2.ps1")
        == protocol["bounded_launcher"]["owned_process_gate_sha256"]
    )


def verify(repo_root: Path, experiment_root: Path) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    config = load_repo_config(repo_root)
    v01_experiment = resolve_config_path(repo_root, config, "pixie_5d_holonomy_experiment_root")
    v01_output = resolve_config_path(repo_root, config, "pixie_5d_holonomy_output_root")
    model = resolve_config_path(repo_root, config, "godel_globes_bonsai_unpacked_hf")
    adapter = resolve_config_path(repo_root, config, "godel_globes_bonsai_adapter")
    source_run = v01_output / "capture" / protocol["continuation"]["source_run_id"]
    checks: dict[str, bool] = {
        "source_protocol": _hash_matches(v01_experiment / "protocol.json", protocol["continuation"]["source_protocol_sha256"]),
        "model_weights": _hash_matches(model / protocol["model"]["weights_file"], protocol["model"]["weights_sha256"]),
        "adapter_config": _hash_matches(adapter / "adapter_config.json", protocol["adapter"]["config_sha256"]),
        "adapter_weights": _hash_matches(adapter / "adapter_model.safetensors", protocol["adapter"]["weights_sha256"]),
        "train_data": _hash_matches(repo_root / protocol["data"]["train_path"], protocol["data"]["train_sha256"]),
        "eval_data": _hash_matches(repo_root / protocol["data"]["eval_path"], protocol["data"]["eval_sha256"]),
    }
    for name, expected in protocol["model"]["support_files"].items():
        checks[f"model_support:{name}"] = _hash_matches(model / name, expected)
    for label, receipt in protocol["continuation"]["source_receipts"].items():
        checks[f"source_receipt:{label}"] = _hash_matches(repo_root / receipt["path"], receipt["sha256"])
    for relative, expected in protocol["continuation"]["reused_artifacts"].items():
        checks[f"source_artifact:{relative}"] = _hash_matches(source_run / relative, expected)
    for relative, expected in protocol["source_modules"].items():
        checks[f"source_module:{relative}"] = _hash_matches(repo_root / relative, expected)
    source_v02 = protocol["source_v02"]
    for label in ("protocol", "lock", "abort_receipt"):
        checks[f"source_v02:{label}"] = _hash_matches(repo_root / source_v02[f"{label}_path"], source_v02[f"{label}_sha256"])
    launcher = (experiment_root / protocol["bounded_launcher"]["path"]).resolve()
    invoker = (experiment_root / protocol["bounded_launcher"]["owned_process_gate_path"]).resolve()
    cleanup = (experiment_root / protocol["bounded_launcher"]["cleanup_path"]).resolve()
    cap_receipt_path = (experiment_root / protocol["bounded_launcher"]["cap_self_test_receipt_path"]).resolve()
    checks["launcher"] = _hash_matches(launcher, protocol["bounded_launcher"]["sha256"])
    checks["invoker"] = _hash_matches(invoker, protocol["bounded_launcher"]["owned_process_gate_sha256"])
    checks["cleanup"] = _hash_matches(cleanup, protocol["bounded_launcher"]["cleanup_sha256"])
    checks["cap_receipt"] = _hash_matches(cap_receipt_path, protocol["bounded_launcher"]["cap_self_test_receipt_sha256"])
    try:
        cap_receipt = json.loads(cap_receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cap_receipt = {}
    checks["cap_semantics"] = _cap_semantics(cap_receipt, protocol)
    for package, expected in protocol["software"].items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        checks[f"software:{package}"] = actual == expected
    checks.update(protocol_lock_checks(experiment_root))
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "model": str(model),
        "adapter": str(adapter),
        "source_run": str(source_run),
        "sharded_model": str(resolve_config_path(repo_root, config, protocol["sharding"]["output_config_key"])),
        "launcher": str(launcher),
    }
