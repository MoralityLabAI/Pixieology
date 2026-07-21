from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_bonsai_mechinterp_atlas import (
    MODULE_ORDER,
    SCHEMA,
    SOURCE_SCHEMA,
    build_atlas,
    effective_rank,
    main,
)


def _module(scale: float, singular: list[float] | None = None) -> dict[str, object]:
    values = singular or [scale / (index + 1) for index in range(8)]
    energy = sum(value * value for value in values) ** 0.5
    return {
        "frobenius": energy,
        "singular_values": values,
        "spectral_focus": (values[0] * values[0]) / sum(value * value for value in values),
        "a_shape": [8, 32],
        "b_shape": [32, 8],
    }


def _analysis() -> dict[str, object]:
    layers = {}
    for layer in range(2):
        layers[str(layer)] = {
            "layer": layer,
            "modules": {
                name: _module((module_index + 1) * (layer + 1))
                for module_index, name in enumerate(MODULE_ORDER)
            },
        }
    return {
        "schema": SOURCE_SCHEMA,
        "source": {
            "adapter_sha256": "a" * 64,
            "adapter_config_sha256": "b" * 64,
        },
        "trace": {"source": {"model_id": "example/pixie-1.7b"}},
        "layer_results": layers,
    }


def test_effective_rank_has_expected_limits() -> None:
    assert effective_rank([1.0] + [0.0] * 7) == pytest.approx(1.0)
    assert effective_rank([1.0] * 8) == pytest.approx(8.0)
    assert effective_rank([0.0] * 8) == 0.0


def test_atlas_preserves_modules_and_normalizes_energy() -> None:
    atlas = build_atlas(_analysis(), "c" * 64)
    assert atlas["schema"] == SCHEMA
    assert atlas["source"]["activation_vpd"] is False
    assert len(atlas["layers"]) == 2
    for layer in atlas["layers"]:
        assert [module["id"] for module in layer["modules"]] == list(MODULE_ORDER)
        assert sum(module["layer_energy_share"] for module in layer["modules"]) == pytest.approx(1.0)
        for module in layer["modules"]:
            assert sum(module["singular_energy_share"]) == pytest.approx(1.0)
            assert 1.0 <= module["effective_rank"] <= 8.0


def test_atlas_rejects_target_module_drift() -> None:
    analysis = _analysis()
    del analysis["layer_results"]["1"]["modules"]["q_proj"]
    with pytest.raises(ValueError, match="seven frozen target modules"):
        build_atlas(analysis, "c" * 64)


def test_cli_resolves_source_and_output_through_config(tmp_path: Path) -> None:
    source = tmp_path / "analysis.json"
    output = tmp_path / "web" / "atlas.js"
    source.write_text(json.dumps(_analysis()), encoding="utf-8")
    config = tmp_path / "pixieology.config.json"
    config.write_text(
        json.dumps(
            {
                "schema": "pixieology_config_v1",
                "paths": {
                    "analysis": "analysis.json",
                    "godel_globes_bonsai_vpd_analysis": "${analysis}",
                    "godel_globes_bonsai_mechinterp_atlas": "web/atlas.js",
                },
            }
        ),
        encoding="utf-8",
    )
    assert main(["--config", str(config)]) == 0
    assert output.exists()
    assert "PixieMechinterpAtlasData" in output.read_text(encoding="utf-8")
