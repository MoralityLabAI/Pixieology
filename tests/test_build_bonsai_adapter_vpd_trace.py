from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from safetensors.numpy import save_file

from build_bonsai_adapter_vpd_trace import (
    CHECKPOINT_SCHEMA,
    analyze_adapter,
    build_trace,
    discover_layout,
    layer_axis_values,
    low_rank_singular_values,
)


MODULES = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")


def test_rank_core_svd_matches_materialized_delta() -> None:
    rng = np.random.default_rng(17)
    a = rng.normal(size=(3, 11)).astype(np.float32)
    b = rng.normal(size=(7, 3)).astype(np.float32)
    expected = np.linalg.svd(2.0 * (b @ a), compute_uv=False)
    actual = low_rank_singular_values(a, b, 2.0)
    np.testing.assert_allclose(actual, expected[: a.shape[0]], rtol=2e-5, atol=2e-5)
    assert np.max(expected[a.shape[0] :]) < 1e-5


def test_layout_and_mechanical_axes_cover_all_linear_families() -> None:
    keys = [f"base_model.model.model.layers.{layer}.self_attn.{module}.lora_A.weight"
            for layer in range(2) for module in MODULES]
    layout = discover_layout(keys)
    assert layout.layers == (0, 1)
    assert set(layout.modules) == set(MODULES)
    metrics = {module: {"frobenius": index + 1.0, "singular_values": [index + 1.0]}
               for index, module in enumerate(MODULES)}
    values = layer_axis_values(metrics)
    assert len(values) == 5
    assert values[-1] == pytest.approx(1.0)


def _synthetic_adapter(folder: Path) -> None:
    rng = np.random.default_rng(5)
    tensors: dict[str, np.ndarray] = {}
    for layer in range(3):
        for module in MODULES:
            prefix = f"base_model.model.model.layers.{layer}.self_attn.{module}"
            tensors[f"{prefix}.lora_A.weight"] = rng.normal(size=(2, 5)).astype(np.float32)
            tensors[f"{prefix}.lora_B.weight"] = rng.normal(size=(4, 2)).astype(np.float32)
    save_file(tensors, folder / "adapter_model.safetensors")
    (folder / "adapter_config.json").write_text(json.dumps({
        "base_model_name_or_path": "test/Bonsai",
        "r": 2,
        "lora_alpha": 4,
        "use_rslora": False,
        "rank_pattern": {},
        "alpha_pattern": {},
        "target_modules": list(MODULES),
    }), encoding="utf-8")


def test_capped_analysis_is_checkpointed_deterministic_and_uncalibrated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    _synthetic_adapter(adapter)
    run_dir = tmp_path / "run"
    output = tmp_path / "trace.js"
    monkeypatch.setenv("PIXIE_RESOURCE_CAP_ACTIVE", "1")
    first = analyze_adapter(adapter_dir=adapter, run_dir=run_dir, output_path=output, run_id="test")
    first_bytes = output.read_bytes()
    second = analyze_adapter(adapter_dir=adapter, run_dir=run_dir, output_path=output, run_id="test")
    assert output.read_bytes() == first_bytes
    assert first["steps_completed"] == second["steps_completed"] == 3
    checkpoint = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["schema"] == CHECKPOINT_SCHEMA
    assert checkpoint["completed_layers"] == [0, 1, 2]
    analysis = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    trace = analysis["trace"]
    assert trace["alignment"]["status"] == "uncalibrated"
    assert trace["source"]["base_model_loaded"] is False
    assert trace["source"]["activation_analysis"] is False
    assert len(trace["frames"]) == 3
    assert all(0 <= value <= 1 for frame in trace["frames"] for value in frame["values"])


def test_analysis_refuses_to_run_without_resource_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PIXIE_RESOURCE_CAP_ACTIVE", raising=False)
    with pytest.raises(RuntimeError, match="refusing uncapped run"):
        analyze_adapter(
            adapter_dir=tmp_path,
            run_dir=tmp_path / "run",
            output_path=tmp_path / "trace.js",
            run_id="unsafe",
        )


def test_trace_metadata_names_parameter_evidence_not_vpd_activations() -> None:
    result = {"modules": {module: {} for module in MODULES}, "axes_raw": [1, 2, 3, 4, 0.5]}
    trace = build_trace(
        layer_results={"0": result, "1": result},
        model_id="test/Bonsai",
        adapter_sha256="a" * 64,
        config_sha256="b" * 64,
        rank=8,
        alpha=16,
        target_modules=MODULES,
    )
    assert trace["source"]["evidence_class"] == "actual_bonsai_1p7b_lora_delta_decomposition"
    assert trace["source"]["activation_analysis"] is False
    assert trace["alignment"]["status"] == "uncalibrated"
