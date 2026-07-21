#!/usr/bin/env python3
"""Build a browser atlas from the exact Bonsai 1.7B LoRA delta analysis.

The source is an invariant SVD summary of each effective LoRA delta matrix.
This is parameter-space evidence: it shows where adapter update energy and
low-rank concentration live, but it is not an activation VPD, causal circuit
map, or semantic feature interpretation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "pixieology_mechinterp_atlas_v1"
SOURCE_SCHEMA = "pixieology_bonsai_adapter_vpd_run_v1"
MODULE_ORDER = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")
MODULE_LABELS = {
    "q_proj": "Query",
    "k_proj": "Key",
    "v_proj": "Value",
    "o_proj": "Attention output",
    "gate_proj": "MLP gate",
    "up_proj": "MLP expansion",
    "down_proj": "MLP contraction",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def load_config(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "pixieology_config_v1" or not isinstance(value.get("paths"), dict):
        raise ValueError(f"invalid Pixieology config: {path}")
    return value


def resolve_config_path(config_path: Path, config: Mapping[str, Any], key: str) -> Path:
    paths = config["paths"]
    if key not in paths:
        raise KeyError(f"missing config path: paths.{key}")
    value = str(paths[key])
    for _ in range(16):
        names = re.findall(r"\$\{([^}]+)\}", value)
        if not names:
            break
        for name in names:
            if name not in paths:
                raise KeyError(f"paths.{key} references missing paths.{name}")
            value = value.replace(f"${{{name}}}", str(paths[name]))
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (config_path.parent / candidate).resolve()


def effective_rank(singular_values: list[float]) -> float:
    energies = [value * value for value in singular_values]
    total = sum(energies)
    squared_total = sum(value * value for value in energies)
    return (total * total / squared_total) if squared_total > 0 else 0.0


def normalize(value: float, lower: float, upper: float) -> float:
    return 0.5 if math.isclose(lower, upper) else (value - lower) / (upper - lower)


def build_atlas(analysis: Mapping[str, Any], source_sha256: str) -> dict[str, Any]:
    if analysis.get("schema") != SOURCE_SCHEMA:
        raise ValueError(f"analysis schema must be {SOURCE_SCHEMA}")
    raw_layers = analysis.get("layer_results")
    if not isinstance(raw_layers, dict) or not raw_layers:
        raise ValueError("analysis requires layer_results")
    ordered = sorted(raw_layers.values(), key=lambda row: int(row["layer"]))
    if [int(row["layer"]) for row in ordered] != list(range(len(ordered))):
        raise ValueError("layers must be contiguous and zero-indexed")

    for row in ordered:
        module_rows = row.get("modules")
        if not isinstance(module_rows, dict) or set(module_rows) != set(MODULE_ORDER):
            raise ValueError(f"layer {row.get('layer')} must contain the seven frozen target modules")

    energy_ranges: dict[str, tuple[float, float]] = {}
    for module_id in MODULE_ORDER:
        values = [float(row["modules"][module_id]["frobenius"]) for row in ordered]
        energy_ranges[module_id] = (min(values), max(values))

    layers: list[dict[str, Any]] = []
    for row in ordered:
        module_rows = row["modules"]
        total_energy_squared = sum(float(module_rows[name]["frobenius"]) ** 2 for name in MODULE_ORDER)
        modules = []
        for module_id in MODULE_ORDER:
            source = module_rows[module_id]
            singular = [float(value) for value in source["singular_values"]]
            if len(singular) != 8 or any(value < 0 for value in singular):
                raise ValueError(f"{module_id} requires eight non-negative singular values")
            singular_energy = [value * value for value in singular]
            singular_total = sum(singular_energy)
            lower, upper = energy_ranges[module_id]
            energy = float(source["frobenius"])
            modules.append(
                {
                    "id": module_id,
                    "label": MODULE_LABELS[module_id],
                    "family": "attention" if module_id in MODULE_ORDER[:4] else "mlp",
                    "energy": energy,
                    "depth_normalized_energy": normalize(energy, lower, upper),
                    "layer_energy_share": (energy * energy / total_energy_squared) if total_energy_squared else 0.0,
                    "spectral_focus": float(source["spectral_focus"]),
                    "effective_rank": effective_rank(singular),
                    "singular_values": singular,
                    "singular_energy_share": (
                        [value / singular_total for value in singular_energy]
                        if singular_total
                        else [0.0] * len(singular_energy)
                    ),
                    "shape": {"a": source["a_shape"], "b": source["b_shape"]},
                }
            )
        attention_energy = math.sqrt(sum(item["energy"] ** 2 for item in modules[:4]))
        mlp_energy = math.sqrt(sum(item["energy"] ** 2 for item in modules[4:]))
        layers.append(
            {
                "layer": int(row["layer"]),
                "depth": int(row["layer"]) / max(1, len(ordered) - 1),
                "total_energy": math.sqrt(total_energy_squared),
                "attention_energy": attention_energy,
                "mlp_energy": mlp_energy,
                "mlp_attention_ratio": mlp_energy / attention_energy if attention_energy else None,
                "modules": modules,
            }
        )

    peaks = {}
    for module_index, module_id in enumerate(MODULE_ORDER):
        peak = max(layers, key=lambda layer: layer["modules"][module_index]["energy"])
        peaks[module_id] = {
            "layer": peak["layer"],
            "energy": peak["modules"][module_index]["energy"],
        }
    return {
        "schema": SCHEMA,
        "title": "Pixie 1.7B adapter delta atlas",
        "source": {
            "analysis_sha256": source_sha256,
            "adapter_sha256": analysis["source"]["adapter_sha256"],
            "adapter_config_sha256": analysis["source"]["adapter_config_sha256"],
            "model_id": analysis["trace"]["source"]["model_id"],
            "evidence_class": "exact_effective_lora_delta_svd",
            "activation_vpd": False,
            "base_model_loaded": False,
        },
        "claim_boundary": (
            "Exact SVD geometry of the trained rank-8 LoRA update. It locates parameter update energy and "
            "mode concentration; it does not identify semantic features, activations, or causal circuits."
        ),
        "modules": [{"id": name, "label": MODULE_LABELS[name]} for name in MODULE_ORDER],
        "energy_ranges": {name: list(values) for name, values in energy_ranges.items()},
        "peaks": peaks,
        "layers": layers,
    }


def render_javascript(atlas: Mapping[str, Any]) -> str:
    payload = json.dumps(atlas, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    return (
        "(function (root, factory) {\n"
        "  const value = factory();\n"
        "  if (typeof module === \"object\" && module.exports) module.exports = value;\n"
        "  root.PixieMechinterpAtlasData = value;\n"
        "})(typeof globalThis !== \"undefined\" ? globalThis : this, function () {\n"
        f"  return Object.freeze({payload});\n"
        "});\n"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("pixieology.config.json"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = args.config.resolve()
    config = load_config(config_path)
    source = resolve_config_path(config_path, config, "godel_globes_bonsai_vpd_analysis")
    output = resolve_config_path(config_path, config, "godel_globes_bonsai_mechinterp_atlas")
    atlas = build_atlas(json.loads(source.read_text(encoding="utf-8")), sha256_file(source))
    atomic_text(output, render_javascript(atlas))
    print(json.dumps({"output": str(output), "layers": len(atlas["layers"]), "sha256": sha256_file(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
