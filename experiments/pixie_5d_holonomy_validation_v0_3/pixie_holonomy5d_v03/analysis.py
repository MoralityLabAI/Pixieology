"""Analyze the verified v0.1 contexts plus v0.3 sharded-loader context 3."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from .protocol import load_protocol, load_repo_config, resolve_config_path, sha256_file
from .verify import verify


class AnalysisError(RuntimeError):
    pass


def _helpers(repo_root: Path):
    root = repo_root / "experiments" / "pixie_5d_holonomy_validation_v0_2"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from pixie_holonomy5d_v02.analysis import (
        _condition_data,
        _legacy_analysis,
        _read_json,
        _verdict,
        _verify_marker,
    )

    return _condition_data, _legacy_analysis, _read_json, _verdict, _verify_marker


def analyze_continuation(repo_root: Path, experiment_root: Path) -> dict[str, Any]:
    verification = verify(repo_root, experiment_root)
    if not verification["ok"]:
        raise AnalysisError(f"frozen v0.3 verification failed: {verification['checks']}")
    protocol = load_protocol(experiment_root)
    protocol_hash = sha256_file(experiment_root / "protocol.json")
    config = load_repo_config(repo_root)
    v01_output = resolve_config_path(repo_root, config, "pixie_5d_holonomy_output_root")
    v03_output = resolve_config_path(repo_root, config, "pixie_5d_holonomy_v03_output_root")
    continuation_id = protocol["continuation"]["continuation_id"]
    source_root = v01_output / "capture" / protocol["continuation"]["source_run_id"]
    continuation_root = v03_output / "continuation" / continuation_id
    condition_data, legacy_analysis, read_json, verdict_fn, verify_marker = _helpers(repo_root)
    summary = read_json(continuation_root / "summary.json")
    if summary.get("status") != "COMPLETE" or summary.get("protocol_sha256") != protocol_hash:
        raise AnalysisError("v0.3 context-3 continuation is incomplete or belongs to another protocol")
    for context_index in range(3):
        verify_marker(
            source_root / f"context_{context_index:02d}.complete.json",
            source_root,
            protocol["continuation"]["source_protocol_sha256"],
            "pixie_5d_capture_context_v1",
        )
    verify_marker(
        continuation_root / "context_03.complete.json",
        continuation_root,
        protocol_hash,
        "pixie_5d_context3_complete_v2",
    )
    layer_energy = summary.get("adapter_layer_effective_update_energy", {})
    if not layer_energy:
        raise AnalysisError("v0.3 continuation summary lacks adapter update energy")
    condition_type, analyze, render, atomic_json, atomic_npz, atomic_text = legacy_analysis(repo_root)
    conditions: dict[str, Any] = {}
    prediction_hashes: dict[str, str] = {}
    analysis_root = v03_output / "analysis" / continuation_id
    for condition in ("trained", "random_00"):
        result, arrays = analyze(
            condition_data(condition_type, source_root, continuation_root, condition),
            condition,
            protocol,
            layer_energy,
        )
        prediction_path = analysis_root / f"{condition}_oof_predictions.npz"
        atomic_npz(prediction_path, **arrays)
        prediction_hashes[condition] = sha256_file(prediction_path)
        conditions[condition] = result
    verdict, target, specificity = verdict_fn(conditions)
    report = {
        "schema": "pixie_5d_holonomy_analysis_v3",
        "protocol_sha256": protocol_hash,
        "source_protocol_sha256": protocol["continuation"]["source_protocol_sha256"],
        "run_id": continuation_id,
        "verdict": verdict,
        "provisional_target_if_control_gate_passes": target,
        "conditions": conditions,
        "specificity": {
            "trained_utility": conditions["trained"]["utility"],
            "random_00_utility": conditions["random_00"]["utility"],
            "trained_minus_random_00": specificity,
            "single_control_is_not_an_empirical_null": True,
        },
        "prediction_artifacts": prediction_hashes,
        "lineage": {
            "reused_contexts": [0, 1, 2],
            "captured_context": 3,
            "source_run": str(source_root),
            "continuation": str(continuation_root),
            "loader": protocol["loader"],
            "sharding": protocol["sharding"],
        },
        "limitations": [
            "One adapter and one base checkpoint cannot establish a universal persona manifold.",
            "Teacher-forced likelihood is a behavioral proxy, not open-ended semantic quality.",
            "A finalist remains provisional until nineteen norm-matched random controls are evaluated.",
            "Rooted spin is gauge-covariant; only the recorded loop class is gauge-invariant.",
            "Context 3 uses a byte-equivalent sharded checkpoint while contexts 0-2 used the original single file.",
        ],
    }
    atomic_json(analysis_root / "analysis.json", report)
    atomic_text(analysis_root / "report.md", render(report))
    return report
