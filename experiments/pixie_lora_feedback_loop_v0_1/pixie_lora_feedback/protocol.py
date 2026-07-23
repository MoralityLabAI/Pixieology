"""Protocol, configuration, and frozen-source verification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pixie_etale_motifs.io import sha256_file
from pixie_etale_motifs.protocol import load_repo_config, resolve_config_path


PROTOCOL_SCHEMA = "pixieology_lora_feedback_protocol_v1"
LOCK_SCHEMA = "pixieology_lora_feedback_protocol_lock_v1"


def load_protocol(experiment_root: Path) -> dict[str, Any]:
    value = json.loads((experiment_root / "protocol.json").read_text(encoding="utf-8"))
    if value.get("schema") != PROTOCOL_SCHEMA:
        raise ValueError("invalid LoRA feedback protocol schema")
    return value


def protocol_lock_checks(experiment_root: Path) -> dict[str, bool]:
    path = experiment_root / "protocol.lock.json"
    if not path.is_file():
        return {"protocol_lock_present": False}
    value = json.loads(path.read_text(encoding="utf-8"))
    checks = {
        "protocol_lock_present": True,
        "protocol_lock_schema": value.get("schema") == LOCK_SCHEMA,
        "protocol_lock_protocol": value.get("protocol_sha256") == sha256_file(experiment_root / "protocol.json"),
    }
    for relative, expected in value.get("files", {}).items():
        source = experiment_root / str(relative)
        checks[f"protocol_lock:{relative}"] = source.is_file() and sha256_file(source) == expected
    checks["protocol_lock_has_files"] = bool(value.get("files"))
    return checks


def verify(
    repo_root: Path,
    experiment_root: Path,
    *,
    require_model_weights: bool = False,
) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    config = load_repo_config(repo_root)
    motif_root = (experiment_root / protocol["source_experiment"]["path"]).resolve()
    model_root = resolve_config_path(repo_root, config, "godel_globes_bonsai_unpacked_hf")
    adapter_root = resolve_config_path(repo_root, config, "godel_globes_bonsai_adapter")
    lock_checks = protocol_lock_checks(experiment_root)
    checks: dict[str, Any] = {
        "status_staged": protocol.get("status") == "STAGED_NOT_AUTHORIZED",
        "default_caps": protocol.get("resources", {}).get("training_requested_not_authorized") == {
            "ram_mb": 2048,
            "cpu_pct": 50,
            "io_mb_s": 50,
            "timeout_seconds": 1800,
        },
        "feedback_implementation_lock": all(lock_checks.values()),
        "feedback_implementation_lock_checks": lock_checks,
        "source_protocol": (motif_root / "protocol.json").is_file()
        and sha256_file(motif_root / "protocol.json") == protocol["source_experiment"]["protocol_sha256"],
        "source_lock": (motif_root / "protocol.lock.json").is_file()
        and sha256_file(motif_root / "protocol.lock.json") == protocol["source_experiment"]["implementation_lock_sha256"],
        "model_config": (model_root / "config.json").is_file()
        and sha256_file(model_root / "config.json") == protocol["base_model"]["config_sha256"],
        "pixie_config": (adapter_root / "adapter_config.json").is_file()
        and sha256_file(adapter_root / "adapter_config.json") == protocol["pixie_adapter"]["config_sha256"],
        "pixie_weights": (adapter_root / "adapter_model.safetensors").is_file()
        and sha256_file(adapter_root / "adapter_model.safetensors") == protocol["pixie_adapter"]["weights_sha256"],
    }
    if require_model_weights:
        weights = model_root / "model.safetensors"
        checks["model_weights"] = weights.is_file() and sha256_file(weights) == protocol["base_model"]["weights_sha256"]
    boolean_checks = [value for value in checks.values() if isinstance(value, bool)]
    return {
        "schema": "pixieology_lora_feedback_verification_v1",
        "ok": all(boolean_checks),
        "checks": checks,
        "model_root": str(model_root),
        "adapter_root": str(adapter_root),
        "motif_root": str(motif_root),
    }
