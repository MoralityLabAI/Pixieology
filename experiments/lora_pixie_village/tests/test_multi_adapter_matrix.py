from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import multi_adapter_matrix as matrix_module  # noqa: E402


MATRIX_PATH = APP_ROOT / "config" / "multi_adapter_matrix_v1.json"


def test_frozen_matrix_has_exact_phase_one_factorial() -> None:
    matrix = matrix_module.load_matrix(MATRIX_PATH)
    assert [row["condition_id"] for row in matrix["conditions"]] == [
        "base",
        "companion",
        "storyworld",
        "stacked",
    ]
    assert [list(row["scales"].values()) for row in matrix["conditions"]] == [
        [0.0, 0.0],
        [1.0, 0.0],
        [0.0, 1.0],
        [1.0, 1.0],
    ]


def test_route_builder_attests_singletons_and_additive_stack(tmp_path: Path) -> None:
    matrix = matrix_module.load_matrix(MATRIX_PATH)
    routes = matrix_module.build_routes(
        matrix,
        [tmp_path / "companion.gguf", tmp_path / "storyworld.gguf"],
        ["a" * 64, "b" * 64],
    )
    assert routes["base-local"]["lora_scales"] == [
        {"id": 0, "scale": 0.0},
        {"id": 1, "scale": 0.0},
    ]
    assert routes["companion-local"]["adapter_sha256"] == "a" * 64
    assert routes["storyworld-local"]["adapter_sha256"] == "b" * 64
    assert routes["stacked-local"]["lora_scales"] == [
        {"id": 0, "scale": 1.0},
        {"id": 1, "scale": 1.0},
    ]
    assert len(routes["stacked-local"]["combination_sha256"]) == 64


def test_matrix_rejects_unregistered_scale_sweep() -> None:
    matrix = matrix_module.load_matrix(MATRIX_PATH)
    changed = copy.deepcopy(matrix)
    changed["conditions"][-1]["scales"]["companion"] = 0.5
    with pytest.raises(matrix_module.MatrixError, match="forbids scale sweeps"):
        matrix_module.validate_matrix(changed)
