"""Protocol and path verification."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_protocol(experiment_root: Path) -> dict[str, Any]:
    value = json.loads((experiment_root / "protocol.json").read_text(encoding="utf-8"))
    if value.get("schema") != "pixie_5d_holonomy_protocol_v1":
        raise ValueError("invalid protocol schema")
    return value


def resolve_repo_config(repo_root: Path) -> dict[str, Any]:
    value = json.loads((repo_root / "pixieology.config.json").read_text(encoding="utf-8"))
    if value.get("schema") != "pixieology_config_v1":
        raise ValueError("invalid Pixieology config")
    return value


def resolve_config_path(repo_root: Path, config: dict[str, Any], key: str) -> Path:
    paths = config["paths"]
    if key not in paths:
        raise KeyError(f"missing paths.{key}")
    value = str(paths[key])
    for _ in range(16):
        names = re.findall(r"\$\{([^}]+)\}", value)
        if not names:
            break
        for name in names:
            value = value.replace(f"${{{name}}}", str(paths[name]))
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (repo_root / candidate).resolve()


def verify_frozen_inputs(repo_root: Path, experiment_root: Path) -> dict[str, object]:
    protocol = load_protocol(experiment_root)
    data = protocol["data"]
    train = (experiment_root / data["train_path"]).resolve()
    evaluation = (experiment_root / data["eval_path"]).resolve()
    config = resolve_repo_config(repo_root)
    model = resolve_config_path(repo_root, config, "godel_globes_bonsai_unpacked_hf")
    adapter = resolve_config_path(repo_root, config, "godel_globes_bonsai_adapter")
    launcher = (experiment_root / protocol["bounded_launcher"]["path"]).resolve()
    owned_gate = (experiment_root / protocol["bounded_launcher"]["owned_process_gate_path"]).resolve()
    checks = {
        "train": sha256_file(train) == data["train_sha256"],
        "eval": sha256_file(evaluation) == data["eval_sha256"],
        "model_config": sha256_file(model / "config.json") == protocol["model"]["config_sha256"],
        "adapter_config": sha256_file(adapter / "adapter_config.json") == protocol["adapter"]["config_sha256"],
        "adapter_weights": sha256_file(adapter / "adapter_model.safetensors") == protocol["adapter"]["weights_sha256"],
        "bounded_launcher": sha256_file(launcher) == protocol["bounded_launcher"]["sha256"],
        "owned_process_gate": sha256_file(owned_gate) == protocol["bounded_launcher"]["owned_process_gate_sha256"],
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "model": str(model),
        "adapter": str(adapter),
        "bounded_launcher": str(launcher),
        "owned_process_gate": str(owned_gate),
    }
