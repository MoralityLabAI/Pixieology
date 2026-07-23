"""Deterministic synthetic forms for pipeline verification, never human evidence."""

from __future__ import annotations

import hashlib
from typing import Any, Sequence

import numpy as np

from .graph import build_form_receipt


def _seed(value: str, root_seed: int) -> int:
    digest = hashlib.sha256(f"{root_seed}:{value}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def synthetic_coordinates(row: dict[str, Any], module_ids: Sequence[str], root_seed: int) -> np.ndarray:
    rng = np.random.default_rng(_seed(str(row["id"]), root_seed))
    layers = np.linspace(0.0, 1.0, 28)
    values = np.zeros((28, len(module_ids), 3), dtype=np.float64)
    for module_index in range(len(module_ids)):
        phase = module_index * 0.7
        values[:, module_index, 0] = 0.12 + module_index * 0.105 + 0.04 * np.sin(5 * layers + phase)
        values[:, module_index, 1] = 0.18 + module_index * 0.08 + 0.03 * np.cos(4 * layers + phase)
        values[:, module_index, 2] = 0.22 + module_index * 0.065 + 0.02 * np.sin(7 * layers + phase)
    variant = str(row["variant"])
    group_number = int(str(row["semantic_group_id"]).rsplit("-", 1)[-1])
    family_index = [
        "pixie_canary",
        "pixie_style",
        "copy_induction",
        "format_following",
        "binary_fact",
        "one_step_arithmetic",
    ].index(str(row["family"]))
    pattern = (group_number + family_index) % 3
    if variant == "lexical_negative":
        pattern = (pattern + 1) % 3
    elif variant == "token_order_null":
        pattern = 3
    if pattern == 0:
        first, second = module_ids.index("q_proj"), module_ids.index("k_proj")
        values[5:17, second] = values[5:17, first] + rng.normal(0.0, 0.006, size=(12, 3))
    elif pattern == 1:
        gate, up, down = (module_ids.index(name) for name in ("gate_proj", "up_proj", "down_proj"))
        values[9:23, up] = values[9:23, gate] + 0.045
        values[9:23, down] = values[9:23, up] + 0.045
    elif pattern == 2:
        value, output, query = (module_ids.index(name) for name in ("v_proj", "o_proj", "q_proj"))
        values[3:14, output] = values[3:14, value] + 0.012
        values[14:25, output] = values[14:25, query] + 0.012
    else:
        values += rng.normal(0.0, 0.12, size=values.shape)
    values += rng.normal(0.0, 0.004, size=values.shape)
    return np.clip(values, 0.0, 1.0)


def build_synthetic_forms(
    rows: Sequence[dict[str, Any]],
    module_ids: Sequence[str],
    *,
    root_seed: int = 2026072399,
) -> list[dict[str, Any]]:
    return [
        build_form_receipt(
            input_row=row,
            coordinates=synthetic_coordinates(row, module_ids, root_seed),
            module_ids=module_ids,
            condition="synthetic_pipeline_fixture",
            metric={
                "id": "synthetic_globally_normalized_xyz_fixture_v1",
                "window_dependent_normalization": False,
                "epsilon_is_confidence_interval": False,
            },
            provenance={
                "evidence_class": "synthetic_pipeline_fixture",
                "human_evidence": False,
                "real_model_evidence": False,
                "root_seed": root_seed,
            },
        )
        for row in rows
    ]
