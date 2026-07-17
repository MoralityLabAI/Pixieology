from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_godel_vpd_trace import TRACE_SCHEMA, VpdTraceError, build_trace, render_javascript


def _write_fixture(root: Path) -> Path:
    chunks = []
    for index in range(2):
        refined = root / f"refined_{index}.json"
        refined.write_text(
            json.dumps(
                {
                    "entries": [
                        {"feature_name": "residual_mix_dampen/down_proj/sv0", "notes": f"sv={1 + index}; ratio=1"},
                        {"feature_name": "value_path_boost/up_proj/sv0", "notes": f"sv={2 + index}; ratio=1"},
                        {"feature_name": "routing_stabilizer/gate_proj/sv0", "notes": f"sv={3 + index}; ratio=1"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        chunks.append(
            {
                "chunk_index": index,
                "start_layer": index,
                "summary": {
                    "refined_feature_map": refined.name,
                    "mean_abs_logit_delta": 0.1 + index * 0.1,
                    "max_abs_logit_delta": 0.3 + index * 0.1,
                },
            }
        )
    source = root / "summary.json"
    source.write_text(json.dumps({"generated_at_utc": "2026-01-01T00:00:00Z", "chunks": chunks}), encoding="utf-8")
    return source


def test_converter_emits_a_deterministic_five_channel_mechanistic_trace(tmp_path: Path) -> None:
    source = _write_fixture(tmp_path)
    trace = build_trace(source, "fixture-small-model")

    assert trace["schema"] == TRACE_SCHEMA
    assert trace["semantics"] == "mechanistic_normalized"
    assert trace["alignment"]["status"] == "uncalibrated"
    assert len(trace["axes"]) == 5
    assert len(trace["frames"]) == 2
    assert trace["frames"][0]["values"] == [0.0] * 5
    assert trace["frames"][1]["values"] == [1.0] * 5
    assert str(tmp_path) not in json.dumps(trace)
    assert render_javascript(trace) == render_javascript(build_trace(source, "fixture-small-model"))


def test_converter_refuses_incomplete_batches(tmp_path: Path) -> None:
    source = tmp_path / "summary.json"
    source.write_text(json.dumps({"chunks": []}), encoding="utf-8")
    with pytest.raises(VpdTraceError, match="at least two chunks"):
        build_trace(source, "fixture-small-model")
