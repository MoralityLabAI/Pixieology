"""Configuration and hash primitives for the v0.2 continuation."""

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


def load_repo_config(repo_root: Path) -> dict[str, Any]:
    value = json.loads((repo_root / "pixieology.config.json").read_text(encoding="utf-8"))
    if value.get("schema") != "pixieology_config_v1":
        raise ValueError("invalid Pixieology config schema")
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
            if name not in paths:
                raise KeyError(f"paths.{key} references missing paths.{name}")
            value = value.replace(f"${{{name}}}", str(paths[name]))
    if re.search(r"\$\{[^}]+\}", value):
        raise ValueError(f"paths.{key} contains unresolved substitutions")
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (repo_root / candidate).resolve()


def load_protocol(experiment_root: Path) -> dict[str, Any]:
    value = json.loads((experiment_root / "protocol.json").read_text(encoding="utf-8"))
    if value.get("schema") != "pixie_5d_holonomy_continuation_protocol_v2":
        raise ValueError("invalid v0.2 protocol schema")
    return value
