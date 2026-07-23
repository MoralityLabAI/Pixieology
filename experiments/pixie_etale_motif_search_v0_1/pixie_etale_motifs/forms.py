"""Convert capture checkpoints into normalized trained and random-control forms."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

import numpy as np

from .corpus import build_corpus
from .geometry import (
    GlobalScaler,
    apply_global_scaler,
    compact_update_svd,
    fit_global_scaler,
    normalization_receipt,
    response_coordinates,
)
from .graph import build_form_receipt
from .io import atomic_json, object_sha256, read_jsonl, sha256_file, write_jsonl


CAPTURE_PATTERN = re.compile(r"rows_(\d{3})_(\d{3})\.npz$")


def capture_files(capture_root: Path) -> list[Path]:
    paths = sorted(path for path in capture_root.rglob("rows_*.npz") if CAPTURE_PATTERN.search(path.name))
    if not paths:
        raise FileNotFoundError(f"no capture checkpoints under {capture_root}")
    for path in paths:
        marker = path.with_suffix(".complete.json")
        if not marker.is_file():
            raise ValueError(f"capture artifact lacks completion marker: {path}")
        value = json.loads(marker.read_text(encoding="utf-8"))
        if value.get("artifact_sha256") != sha256_file(path):
            raise ValueError(f"capture artifact hash mismatch: {path}")
    return paths


def fit_scaler_from_capture(paths: Sequence[Path]) -> GlobalScaler:
    discovery: list[np.ndarray] = []
    for path in paths:
        with np.load(path, allow_pickle=False) as archive:
            mask = archive["splits"] == "discovery"
            if np.any(mask):
                discovery.append(np.asarray(archive["raw_coordinates"][mask], dtype=np.float64))
    if not discovery:
        raise ValueError("capture contains no discovery coordinates")
    return fit_global_scaler(np.concatenate(discovery, axis=0))


def _input_lookup(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {str(row["id"]): row for row in rows}
    if len(result) != 192:
        raise ValueError("controlled corpus must contain 192 unique rows")
    return result


def emit_trained_forms(
    paths: Sequence[Path],
    output_path: Path,
    *,
    corpus_rows: Sequence[dict[str, Any]],
    module_ids: Sequence[str],
    scaler: GlobalScaler,
    scaler_sha256: str,
    protocol_sha256: str,
) -> list[dict[str, Any]]:
    lookup = _input_lookup(corpus_rows)
    forms: list[dict[str, Any]] = []
    metric = normalization_receipt(scaler, scaler_sha256)
    for path in paths:
        with np.load(path, allow_pickle=False) as archive:
            row_ids = archive["row_ids"].astype(str)
            raw = np.asarray(archive["raw_coordinates"], dtype=np.float64)
            base_ll = np.asarray(archive["base_mean_log_likelihood"], dtype=np.float64)
            trained_ll = np.asarray(archive["trained_mean_log_likelihood"], dtype=np.float64)
            for index, row_id in enumerate(row_ids):
                normalized = apply_global_scaler(raw[index], scaler)
                receipt = build_form_receipt(
                    input_row=lookup[row_id],
                    coordinates=normalized,
                    module_ids=module_ids,
                    condition="trained_counterfactual_on_base",
                    metric=metric,
                    provenance={
                        "protocol_sha256": protocol_sha256,
                        "capture_artifact": str(path.resolve()),
                        "capture_artifact_sha256": sha256_file(path),
                        "behavior": {
                            "base_mean_log_likelihood": None if math.isnan(base_ll[index]) else float(base_ll[index]),
                            "trained_mean_log_likelihood": None if math.isnan(trained_ll[index]) else float(trained_ll[index]),
                            "adapter_minus_base": (
                                None
                                if math.isnan(base_ll[index]) or math.isnan(trained_ll[index])
                                else float(trained_ll[index] - base_ll[index])
                            ),
                        },
                    },
                )
                forms.append(receipt)
    write_jsonl(output_path, forms)
    return forms


def _product_norm(a: np.ndarray, b: np.ndarray) -> float:
    left_gram = b.T @ b
    right_gram = a @ a.T
    return math.sqrt(max(0.0, float(np.sum(left_gram * right_gram.T))))


def _module_seed(root_seed: int, control_index: int, key: str) -> int:
    digest = hashlib.sha256(f"{root_seed}:{control_index}:{key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _random_update(
    trained_a: np.ndarray,
    trained_b: np.ndarray,
    scale: float,
    *,
    seed: int,
):
    rng = np.random.default_rng(seed)
    random_a = rng.normal(0.0, 1.0 / math.sqrt(max(1, trained_a.shape[1])), size=trained_a.shape)
    random_b = rng.normal(0.0, 1.0 / math.sqrt(max(1, trained_b.shape[1])), size=trained_b.shape)
    target = _product_norm(trained_a, trained_b)
    actual = _product_norm(random_a, random_b)
    if target == 0.0:
        random_b.fill(0.0)
    elif actual <= 0.0:
        raise ValueError("random update has zero product norm")
    else:
        random_b *= target / actual
    return compact_update_svd(random_a, random_b, scale)


def _adapter_arrays(adapter_path: Path) -> tuple[dict[tuple[int, str], tuple[np.ndarray, np.ndarray]], float]:
    from safetensors import safe_open

    config = json.loads((adapter_path / "adapter_config.json").read_text(encoding="utf-8"))
    scale = float(config["lora_alpha"]) / float(config["r"])
    pattern = re.compile(r"layers\.(\d+)\..*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)\.lora_([AB])\.weight$")
    halves: dict[tuple[int, str], dict[str, np.ndarray]] = {}
    with safe_open(adapter_path / "adapter_model.safetensors", framework="np") as archive:
        for name in archive.keys():
            match = pattern.search(name)
            if match is None:
                continue
            key = (int(match.group(1)), str(match.group(2)))
            halves.setdefault(key, {})[match.group(3)] = np.asarray(archive.get_tensor(name), dtype=np.float64)
    result = {key: (value["A"], value["B"]) for key, value in halves.items() if set(value) == {"A", "B"}}
    return result, scale


def emit_random_control_forms(
    paths: Sequence[Path],
    output_root: Path,
    *,
    adapter_path: Path,
    corpus_rows: Sequence[dict[str, Any]],
    module_ids: Sequence[str],
    scaler: GlobalScaler,
    scaler_sha256: str,
    protocol_sha256: str,
    root_seed: int,
    control_count: int = 19,
) -> list[dict[str, Any]]:
    lookup = _input_lookup(corpus_rows)
    trained, scale = _adapter_arrays(adapter_path)
    metric = normalization_receipt(scaler, scaler_sha256)
    summaries: list[dict[str, Any]] = []
    for control_index in range(control_count):
        condition = f"random_{control_index:02d}"
        updates = {
            key: _random_update(
                pair[0],
                pair[1],
                scale,
                seed=_module_seed(root_seed, control_index, f"{key[0]}:{key[1]}"),
            )
            for key, pair in trained.items()
        }
        forms: list[dict[str, Any]] = []
        for path in paths:
            with np.load(path, allow_pickle=False) as archive:
                row_ids = archive["row_ids"].astype(str)
                for row_index, row_id in enumerate(row_ids):
                    raw = np.zeros((28, len(module_ids), 3), dtype=np.float64)
                    for layer in range(28):
                        for module_index, module_id in enumerate(module_ids):
                            key = (layer, module_id)
                            inputs = archive[f"input__{layer:02d}__{module_id}"]
                            base_norms = archive[f"base_norm__{layer:02d}__{module_id}"]
                            raw[layer, module_index] = response_coordinates(
                                np.asarray(inputs[row_index], dtype=np.float64),
                                float(base_norms[row_index]),
                                updates[key],
                            )
                    forms.append(
                        build_form_receipt(
                            input_row=lookup[row_id],
                            coordinates=apply_global_scaler(raw, scaler),
                            module_ids=module_ids,
                            condition=condition,
                            metric=metric,
                            provenance={
                                "protocol_sha256": protocol_sha256,
                                "capture_artifact": str(path.resolve()),
                                "capture_artifact_sha256": sha256_file(path),
                                "random_control": {
                                    "index": control_index,
                                    "seed": root_seed,
                                    "per_module_effective_delta_norm_matched": True,
                                    "live_forward": False,
                                },
                            },
                        )
                    )
        output = output_root / f"{condition}.jsonl"
        write_jsonl(output, forms)
        summaries.append(
            {
                "condition": condition,
                "form_count": len(forms),
                "artifact": str(output),
                "artifact_sha256": sha256_file(output),
            }
        )
    return summaries


def scaler_receipt(scaler: GlobalScaler) -> dict[str, Any]:
    value = scaler.to_dict()
    value["scaler_sha256"] = object_sha256(value)
    return value
