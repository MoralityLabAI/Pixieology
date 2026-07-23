"""Protocol loading, configuration expansion, and frozen-input verification."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .io import object_sha256, sha256_file


PROTOCOL_SCHEMA = "pixie_etale_motif_search_protocol_v1"


def load_protocol(experiment_root: Path) -> dict[str, Any]:
    value = json.loads((experiment_root / "protocol.json").read_text(encoding="utf-8"))
    if value.get("schema") != PROTOCOL_SCHEMA:
        raise ValueError(f"protocol schema must be {PROTOCOL_SCHEMA}")
    return value


def protocol_hash(experiment_root: Path) -> str:
    return sha256_file(experiment_root / "protocol.json")


def load_repo_config(repo_root: Path) -> dict[str, Any]:
    value = json.loads((repo_root / "pixieology.config.json").read_text(encoding="utf-8"))
    if value.get("schema") != "pixieology_config_v1":
        raise ValueError("invalid Pixieology config")
    return value


def resolve_config_path(repo_root: Path, config: dict[str, Any], key: str) -> Path:
    paths = config.get("paths", {})
    if key not in paths:
        raise KeyError(f"missing paths.{key}")
    value = str(paths[key])
    for _ in range(16):
        names = re.findall(r"\$\{([^}]+)\}", value)
        if not names:
            break
        for name in names:
            if name not in paths:
                raise KeyError(f"missing paths.{name}")
            value = value.replace(f"${{{name}}}", str(paths[name]))
    else:
        raise ValueError(f"cyclic path expansion for paths.{key}")
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (repo_root / candidate).resolve()


def verify_protocol_shape(protocol: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if protocol.get("status") != "STAGED_NOT_AUTHORIZED":
        errors.append("protocol status must remain STAGED_NOT_AUTHORIZED")
    if protocol.get("layers") != list(range(28)):
        errors.append("layers must be exactly 0..27")
    if set(protocol.get("module_ids", [])) != {
        "q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"
    }:
        errors.append("module_ids must be the seven frozen LoRA targets")
    if protocol.get("chart", {}).get("radii") != [1, 2, 4]:
        errors.append("chart radii must be [1,2,4]")
    if protocol.get("capture", {}).get("checkpoint_rows") != 8:
        errors.append("capture must checkpoint every eight rows")
    evaluation = protocol.get("evaluation", {})
    if evaluation.get("bootstrap_replicates") != 2000:
        errors.append("evaluation must use 2000 grouped bootstrap replicates")
    if evaluation.get("craft", {}).get("minimum_paired_participants") != 12:
        errors.append("craft study minimum must remain 12 paired participants")
    if evaluation.get("learning", {}).get("minimum_participants") != 32:
        errors.append("learning study minimum must remain 32 participants")
    resources = protocol.get("resources", {})
    expected = {"ram_mb": 6144, "cpu_pct": 50, "io_mb_s": 250, "timeout_seconds": 1800}
    if resources.get("capture_requested_not_authorized") != expected:
        errors.append("capture resource caps differ from the frozen plan")
    return errors


def verify_frozen_inputs(repo_root: Path, experiment_root: Path, *, require_weights: bool = False) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    errors = verify_protocol_shape(protocol)
    config = load_repo_config(repo_root)
    model = resolve_config_path(repo_root, config, "godel_globes_bonsai_unpacked_hf")
    adapter = resolve_config_path(repo_root, config, "godel_globes_bonsai_adapter")
    checks: dict[str, Any] = {
        "protocol_shape": not errors,
        "protocol_shape_errors": errors,
        "model_config": (model / "config.json").is_file(),
        "adapter_config": (adapter / "adapter_config.json").is_file(),
        "adapter_weights": (adapter / "adapter_model.safetensors").is_file(),
    }
    if checks["model_config"]:
        checks["model_config_hash"] = sha256_file(model / "config.json") == protocol["model"]["config_sha256"]
    if checks["adapter_config"]:
        checks["adapter_config_hash"] = sha256_file(adapter / "adapter_config.json") == protocol["adapter"]["config_sha256"]
    if checks["adapter_weights"]:
        checks["adapter_weights_hash"] = sha256_file(adapter / "adapter_model.safetensors") == protocol["adapter"]["weights_sha256"]
    if require_weights:
        weights = model / protocol["model"]["weights_file"]
        checks["model_weights"] = weights.is_file()
        if weights.is_file():
            checks["model_weights_hash"] = sha256_file(weights) == protocol["model"]["weights_sha256"]
    corpus = build_corpus_from_protocol(protocol)
    checks["corpus_rows"] = len(corpus) == int(protocol["corpus"]["rows"])
    checks["corpus_hash"] = object_sha256(corpus) == protocol["corpus"]["generated_sha256"]
    boolean_checks = [value for value in checks.values() if isinstance(value, bool)]
    return {
        "ok": all(boolean_checks),
        "checks": checks,
        "model": str(model),
        "adapter": str(adapter),
        "corpus_sha256": object_sha256(corpus),
    }


def build_corpus_from_protocol(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    from .corpus import build_corpus

    return build_corpus(
        root_seed=int(protocol["seeds"]["corpus"]),
        family_names=list(protocol["corpus"]["families"]),
    )
