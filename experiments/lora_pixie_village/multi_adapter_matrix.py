"""Frozen additive-LoRA composition matrix validation and route construction."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "pixie_multi_adapter_matrix_v1"
REQUIRED_CONDITIONS = {"base", "companion", "storyworld", "stacked"}


class MatrixError(ValueError):
    """The composition matrix is ambiguous or unsafe to execute."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_matrix(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MatrixError(f"cannot read composition matrix {path}: {exc}") from exc
    return validate_matrix(value)


def validate_matrix(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise MatrixError(f"matrix must use {SCHEMA_VERSION}")
    if not isinstance(value.get("matrix_id"), str) or not value["matrix_id"].strip():
        raise MatrixError("matrix_id must be a non-empty string")
    adapters = value.get("adapters")
    if not isinstance(adapters, list) or len(adapters) != 2:
        raise MatrixError("phase-1 matrix requires exactly two adapters")
    labels = [str(row.get("label") or "") for row in adapters if isinstance(row, dict)]
    ids = [row.get("adapter_id") for row in adapters if isinstance(row, dict)]
    if len(labels) != 2 or len(set(labels)) != 2 or any(not label for label in labels):
        raise MatrixError("adapter labels must be two distinct non-empty strings")
    if ids != [0, 1]:
        raise MatrixError("adapter IDs must be ordered [0, 1] to match llama.cpp load order")

    conditions = value.get("conditions")
    if not isinstance(conditions, list) or len(conditions) != 4:
        raise MatrixError("phase-1 matrix requires exactly four conditions")
    condition_ids: list[str] = []
    aliases: list[str] = []
    for row in conditions:
        if not isinstance(row, dict):
            raise MatrixError("every condition must be an object")
        condition_id = str(row.get("condition_id") or "")
        alias = str(row.get("model_alias") or "")
        scales = row.get("scales")
        if not condition_id or not alias.endswith("-local"):
            raise MatrixError("each condition needs an ID and a *-local model alias")
        if not isinstance(scales, dict) or set(scales) != set(labels):
            raise MatrixError(f"condition {condition_id} must assign every adapter scale exactly once")
        for label, scale in scales.items():
            if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(float(scale)):
                raise MatrixError(f"condition {condition_id} has invalid scale for {label}")
            if float(scale) not in {0.0, 1.0}:
                raise MatrixError("phase-1 forbids scale sweeps; scales must be exactly 0 or 1")
        condition_ids.append(condition_id)
        aliases.append(alias)
    if set(condition_ids) != REQUIRED_CONDITIONS or len(set(aliases)) != len(aliases):
        raise MatrixError(f"conditions must be exactly {sorted(REQUIRED_CONDITIONS)} with unique aliases")

    expected = {
        "base": [0.0, 0.0],
        "companion": [1.0, 0.0],
        "storyworld": [0.0, 1.0],
        "stacked": [1.0, 1.0],
    }
    for row in conditions:
        observed = [float(row["scales"][label]) for label in labels]
        if observed != expected[row["condition_id"]]:
            raise MatrixError(f"condition {row['condition_id']} does not match its frozen phase-1 scales")

    prompts = value.get("prompts")
    if not isinstance(prompts, list) or len(prompts) < 2:
        raise MatrixError("matrix requires at least two frozen evaluation prompts")
    prompt_ids: set[str] = set()
    for prompt in prompts:
        if not isinstance(prompt, dict):
            raise MatrixError("every prompt must be an object")
        prompt_id = str(prompt.get("prompt_id") or "")
        if not prompt_id or prompt_id in prompt_ids:
            raise MatrixError("prompt IDs must be unique and non-empty")
        prompt_ids.add(prompt_id)
        if not all(isinstance(prompt.get(key), str) and prompt[key] for key in ("system", "user")):
            raise MatrixError(f"prompt {prompt_id} needs non-empty system and user text")
        if not isinstance(prompt.get("max_tokens"), int) or not 1 <= prompt["max_tokens"] <= 256:
            raise MatrixError(f"prompt {prompt_id} has invalid max_tokens")
        required = prompt.get("proposal_required_for")
        if not isinstance(required, list) or not set(required).issubset(REQUIRED_CONDITIONS):
            raise MatrixError(f"prompt {prompt_id} has invalid proposal_required_for")
    return value


def build_routes(
    matrix: dict[str, Any], adapter_paths: list[Path], adapter_hashes: list[str]
) -> dict[str, dict[str, Any]]:
    validate_matrix(matrix)
    if len(adapter_paths) != 2 or len(adapter_hashes) != 2:
        raise MatrixError("two adapter paths and hashes are required")
    adapter_rows = matrix["adapters"]
    routes: dict[str, dict[str, Any]] = {}
    for condition in matrix["conditions"]:
        components = [
            {
                "adapter_id": int(adapter["adapter_id"]),
                "label": adapter["label"],
                "path": str(adapter_paths[index]),
                "sha256": adapter_hashes[index],
                "scale": float(condition["scales"][adapter["label"]]),
            }
            for index, adapter in enumerate(adapter_rows)
        ]
        active = [component for component in components if component["scale"] != 0.0]
        attestation = {
            "matrix_id": matrix["matrix_id"],
            "condition_id": condition["condition_id"],
            "components": [
                {key: component[key] for key in ("adapter_id", "label", "sha256", "scale")}
                for component in components
            ],
        }
        routes[condition["model_alias"]] = {
            "label": condition["condition_id"],
            "condition_id": condition["condition_id"],
            "model_alias": condition["model_alias"],
            "adapter_id": active[0]["adapter_id"] if len(active) == 1 else None,
            "adapter_sha256": active[0]["sha256"] if len(active) == 1 else sha256_value(attestation),
            "components": components,
            "lora_scales": [
                {"id": component["adapter_id"], "scale": component["scale"]} for component in components
            ],
            "combination_sha256": sha256_value(attestation),
        }
    return routes
