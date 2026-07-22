"""Assemble the frozen v0.1/v0.2 capture and run the registered CPU analysis."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np

from .protocol import load_protocol, load_repo_config, resolve_config_path, sha256_file
from .verify import verify


class AnalysisError(RuntimeError):
    """The versioned continuation cannot support the frozen analysis."""


def _legacy_analysis(repo_root: Path):
    legacy_root = repo_root / "experiments" / "pixie_5d_holonomy_validation"
    if str(legacy_root) not in sys.path:
        sys.path.insert(0, str(legacy_root))
    from pixie_holonomy5d.analysis import ConditionData, _analyze_condition, _render_markdown
    from pixie_holonomy5d.io import atomic_json, atomic_npz, atomic_text

    return ConditionData, _analyze_condition, _render_markdown, atomic_json, atomic_npz, atomic_text


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError(f"invalid required JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise AnalysisError(f"required JSON is not an object: {path}")
    return value


def _verify_marker(marker_path: Path, run_root: Path, protocol_hash: str, expected_schema: str) -> None:
    marker = _read_json(marker_path)
    if marker.get("schema") != expected_schema or marker.get("protocol_sha256") != protocol_hash:
        raise AnalysisError(f"completion marker differs from frozen lineage: {marker_path}")
    artifacts = marker.get("artifacts")
    if not isinstance(artifacts, dict) or len(artifacts) != 3:
        raise AnalysisError(f"completion marker must cover three conditions: {marker_path}")
    for relative, expected in artifacts.items():
        path = run_root / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise AnalysisError(f"completion marker artifact mismatch: {path}")


def _condition_data(
    condition_type: Any,
    source_root: Path,
    continuation_root: Path,
    condition: str,
) -> Any:
    deltas: list[np.ndarray] = []
    gains: list[np.ndarray] = []
    reference: dict[str, np.ndarray] = {}
    for context_index in range(4):
        root = source_root if context_index < 3 else continuation_root
        path = root / condition / f"context_{context_index:02d}.npz"
        if not path.is_file():
            raise AnalysisError(f"capture artifact is missing: {path}")
        with np.load(path, allow_pickle=False) as archive:
            current = {
                "row_ids": archive["row_ids"].copy(),
                "families": archive["families"].copy(),
                "splits": archive["splits"].copy(),
                "layers": archive["layers"].copy(),
            }
            if not reference:
                reference = current
            elif any(not np.array_equal(reference[name], current[name]) for name in reference):
                raise AnalysisError(f"row or layer metadata drifted in {path}")
            deltas.append(archive["delta"].astype(np.float64))
            gains.append(archive["log_likelihood_gain"].astype(np.float64))
    return condition_type(
        deltas=deltas,
        gains=gains,
        row_ids=reference["row_ids"],
        families=reference["families"],
        splits=reference["splits"],
        layers=reference["layers"],
    )


def _verdict(conditions: Mapping[str, Any]) -> tuple[str, str | None, float]:
    trained = conditions["trained"]
    control = conditions["random_00"]
    specificity = float(trained["utility"] - control["utility"])
    gates = trained["gates"]
    finalist = bool(
        gates["H1_representation"]
        and gates["H2_predictive_increment"]
        and gates["H3_spin_increment"]
        and gates["H5_gauge_integrity"]
    )
    if not gates["H5_gauge_integrity"]:
        verdict = "INTEGRITY_FAIL"
    elif not gates["H1_representation"]:
        verdict = "NO_SUPPORTED_OBJECT"
    elif not gates["H2_predictive_increment"]:
        verdict = "GEOMETRY_NONPREDICTIVE"
    elif not gates["H3_spin_increment"]:
        verdict = "XYZT_ONLY"
    elif specificity < 0.05:
        verdict = "RANDOM_CONTROL_NOT_SEPARATED"
    elif finalist:
        verdict = "FINALIST_REQUIRES_19_CONTROLS"
    else:
        verdict = "LINEAGE_ONLY"
    target = ("HOLONOMY_INCREMENTAL" if gates["H3_holonomy_increment"] else "SPIN_INCREMENTAL") if finalist else None
    return verdict, target, specificity


def analyze_continuation(repo_root: Path, experiment_root: Path) -> dict[str, Any]:
    """Run the frozen v0.1 estimator on verified v0.1+v0.2 context artifacts."""
    verification = verify(repo_root, experiment_root)
    if not verification["ok"]:
        raise AnalysisError(f"frozen-lineage verification failed: {verification['checks']}")
    protocol = load_protocol(experiment_root)
    protocol_hash = sha256_file(experiment_root / "protocol.json")
    config = load_repo_config(repo_root)
    v01_output = resolve_config_path(repo_root, config, "pixie_5d_holonomy_output_root")
    v02_output = resolve_config_path(repo_root, config, "pixie_5d_holonomy_v02_output_root")
    continuation_id = protocol["continuation"]["continuation_id"]
    source_root = v01_output / "capture" / protocol["continuation"]["source_run_id"]
    continuation_root = v02_output / "continuation" / continuation_id
    summary = _read_json(continuation_root / "summary.json")
    if summary.get("status") != "COMPLETE" or summary.get("protocol_sha256") != protocol_hash:
        raise AnalysisError("context-3 continuation is incomplete or belongs to another protocol")
    for context_index in range(3):
        _verify_marker(
            source_root / f"context_{context_index:02d}.complete.json",
            source_root,
            protocol["continuation"]["source_protocol_sha256"],
            "pixie_5d_capture_context_v1",
        )
    _verify_marker(
        continuation_root / "context_03.complete.json",
        continuation_root,
        protocol_hash,
        "pixie_5d_context3_complete_v2",
    )
    layer_energy = summary.get("adapter_layer_effective_update_energy", {})
    if not layer_energy:
        raise AnalysisError("continuation summary lacks per-layer adapter update energy")

    condition_type, analyze, render, atomic_json, atomic_npz, atomic_text = _legacy_analysis(repo_root)
    conditions: dict[str, Any] = {}
    prediction_hashes: dict[str, str] = {}
    analysis_root = v02_output / "analysis" / continuation_id
    for condition in ("trained", "random_00"):
        result, arrays = analyze(
            _condition_data(condition_type, source_root, continuation_root, condition),
            condition,
            protocol,
            layer_energy,
        )
        prediction_path = analysis_root / f"{condition}_oof_predictions.npz"
        atomic_npz(prediction_path, **arrays)
        prediction_hashes[condition] = sha256_file(prediction_path)
        conditions[condition] = result
    verdict, target, specificity = _verdict(conditions)
    report = {
        "schema": "pixie_5d_holonomy_analysis_v2",
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
        },
        "limitations": [
            "One adapter and one base checkpoint cannot establish a universal persona manifold.",
            "Teacher-forced likelihood is a behavioral proxy, not open-ended semantic quality.",
            "A finalist remains provisional until nineteen norm-matched random controls are evaluated.",
            "Rooted spin is gauge-covariant; only the recorded loop class is gauge-invariant.",
            "Contexts 0-2 and context 3 were captured in separate bounded processes; hashes and identical metadata establish lineage, not simultaneous execution.",
        ],
    }
    atomic_json(analysis_root / "analysis.json", report)
    atomic_text(analysis_root / "report.md", render(report))
    return report
