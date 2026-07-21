"""Frozen held-out analysis for the Pixie 5D holonomy experiment."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .geometry import (
    Transport,
    fit_pca,
    loop_receipt,
    polar_transport,
    rank1_support_test,
    reframe_loop,
    spectral_time,
)
from .io import atomic_json, atomic_npz, atomic_text
from .protocol import (
    load_protocol,
    resolve_config_path,
    resolve_repo_config,
    sha256_file,
    verify_frozen_inputs,
)


class AnalysisError(RuntimeError):
    """Frozen capture artifacts cannot support the registered analysis."""


@dataclass(frozen=True)
class ConditionData:
    deltas: list[np.ndarray]
    gains: list[np.ndarray]
    row_ids: np.ndarray
    families: np.ndarray
    splits: np.ndarray
    layers: np.ndarray


@dataclass(frozen=True)
class PredictionReceipt:
    r2: float
    predictions: np.ndarray
    selected_penalties: list[float]


def _r2(observed: np.ndarray, predicted: np.ndarray) -> float:
    residual = float(np.sum((observed - predicted) ** 2))
    total = float(np.sum((observed - observed.mean()) ** 2))
    if total <= 1e-15:
        raise AnalysisError("R2 is undefined for a constant outcome")
    return 1.0 - residual / total


def _ridge_predict(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, penalty: float) -> np.ndarray:
    mean = train_x.mean(axis=0)
    scale = train_x.std(axis=0)
    scale[scale < 1e-12] = 1.0
    standardized = (train_x - mean) / scale
    standardized_test = (test_x - mean) / scale
    design = np.column_stack([np.ones(len(standardized)), standardized])
    test_design = np.column_stack([np.ones(len(standardized_test)), standardized_test])
    regularizer = np.eye(design.shape[1], dtype=np.float64) * float(penalty)
    regularizer[0, 0] = 0.0
    weights = np.linalg.solve(design.T @ design + regularizer, design.T @ train_y)
    return test_design @ weights


def _fold_map(groups: np.ndarray, folds: int, seed: int) -> dict[str, int]:
    unique = np.asarray(sorted(set(str(item) for item in groups)), dtype=np.str_)
    if len(unique) < folds:
        raise AnalysisError(f"{len(unique)} groups cannot support {folds} folds")
    rng = np.random.default_rng(seed)
    shuffled = unique[rng.permutation(len(unique))]
    return {str(group): index % folds for index, group in enumerate(shuffled)}


def grouped_nested_ridge_predictions(
    features: np.ndarray,
    outcome: np.ndarray,
    groups: np.ndarray,
    penalties: Sequence[float],
    *,
    outer_folds: int,
    inner_folds: int,
    seed: int,
) -> PredictionReceipt:
    """Nested group-fold ridge predictions with no prompt crossing a fold."""
    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(outcome, dtype=np.float64)
    group_array = np.asarray(groups, dtype=np.str_)
    if x.ndim != 2 or len(x) != len(y) or len(y) != len(group_array):
        raise AnalysisError("feature, outcome, and group shapes differ")
    outer = _fold_map(group_array, outer_folds, seed)
    predictions = np.empty(len(y), dtype=np.float64)
    selected: list[float] = []
    for outer_fold in range(outer_folds):
        test = np.asarray([outer[str(group)] == outer_fold for group in group_array], dtype=bool)
        train = ~test
        train_groups = group_array[train]
        inner = _fold_map(train_groups, inner_folds, seed + 1009 * (outer_fold + 1))
        losses: dict[float, float] = {}
        for penalty in penalties:
            squared_error = 0.0
            count = 0
            for inner_fold in range(inner_folds):
                validation_local = np.asarray([inner[str(group)] == inner_fold for group in train_groups], dtype=bool)
                fit_local = ~validation_local
                prediction = _ridge_predict(
                    x[train][fit_local], y[train][fit_local], x[train][validation_local], float(penalty)
                )
                squared_error += float(np.sum((y[train][validation_local] - prediction) ** 2))
                count += int(validation_local.sum())
            losses[float(penalty)] = squared_error / count
        best = min(losses, key=lambda penalty: (losses[penalty], penalty))
        selected.append(float(best))
        predictions[test] = _ridge_predict(x[train], y[train], x[test], best)
    return PredictionReceipt(r2=_r2(y, predictions), predictions=predictions, selected_penalties=selected)


def _direction(samples: np.ndarray, labels: np.ndarray) -> np.ndarray | None:
    classes = np.unique(labels)
    vector = samples[labels == classes[1]].mean(axis=0) - samples[labels == classes[0]].mean(axis=0)
    norm = float(np.linalg.norm(vector))
    return None if norm <= 1e-12 else (vector / norm).reshape(-1, 1)


def _root_transports(edges: Sequence[Transport], rank: int) -> list[np.ndarray]:
    roots = [np.eye(rank, dtype=np.float64)]
    for edge in edges[:-1]:
        roots.append(edge.polar @ roots[-1])
    return roots


def _orthogonal_gauge(rng: np.random.Generator, rank: int) -> np.ndarray:
    q, r = np.linalg.qr(rng.normal(size=(rank, rank)))
    signs = np.sign(np.diag(r))
    signs[signs == 0] = 1.0
    return q @ np.diag(signs)


def _gauge_integrity(edges: Sequence[Transport], seed: int, replicates: int = 256) -> dict[str, Any]:
    original = loop_receipt(edges)
    original_sign = -1 if original.determinant < 0 else 1
    original_roots = _root_transports(edges, original.rank)
    rng = np.random.default_rng(seed)
    loop_failures = 0
    rooted_spin_failures = 0
    for _ in range(replicates):
        gauges = [_orthogonal_gauge(rng, original.rank) for _ in edges]
        reframed_edges = reframe_loop(edges, gauges)
        reframed = loop_receipt(reframed_edges)
        sign = -1 if reframed.determinant < 0 else 1
        if sign != original_sign or reframed.category != original.category:
            loop_failures += 1
        reframed_roots = _root_transports(reframed_edges, original.rank)
        for node, (root, reframed_root) in enumerate(zip(original_roots, reframed_roots)):
            expected = gauges[node].T @ root @ gauges[0]
            expected_sign = -1 if np.linalg.det(expected) < 0 else 1
            actual_sign = -1 if np.linalg.det(reframed_root) < 0 else 1
            if expected_sign != actual_sign:
                rooted_spin_failures += 1
    return {
        "passed": loop_failures == 0 and rooted_spin_failures == 0,
        "replicates": replicates,
        "loop_failures": loop_failures,
        "rooted_spin_failures": rooted_spin_failures,
        "determinant_sign": original_sign,
        "category": original.category,
    }


def _read_condition(run_root: Path, condition: str, protocol: Mapping[str, Any]) -> ConditionData:
    deltas: list[np.ndarray] = []
    gains: list[np.ndarray] = []
    reference: dict[str, np.ndarray] = {}
    for context_index in range(len(protocol["contexts"])):
        path = run_root / condition / f"context_{context_index:02d}.npz"
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
    return ConditionData(
        deltas=deltas,
        gains=gains,
        row_ids=reference["row_ids"],
        families=reference["families"],
        splits=reference["splits"],
        layers=reference["layers"],
    )


def _verify_context_artifacts(run_root: Path, protocol_hash: str, protocol: Mapping[str, Any]) -> None:
    for context_index in range(len(protocol["contexts"])):
        marker_path = run_root / f"context_{context_index:02d}.complete.json"
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise AnalysisError(f"invalid context completion marker {marker_path}: {error}") from error
        if marker.get("protocol_sha256") != protocol_hash:
            raise AnalysisError(f"context marker protocol mismatch: {marker_path}")
        for relative, expected_hash in marker.get("artifacts", {}).items():
            artifact = run_root / relative
            if not artifact.is_file() or sha256_file(artifact) != expected_hash:
                raise AnalysisError(f"context artifact hash mismatch: {artifact}")
        if len(marker.get("artifacts", {})) != 3:
            raise AnalysisError(f"context marker does not cover all three conditions: {marker_path}")


def _bootstrap_increment(
    observed: np.ndarray,
    left_prediction: np.ndarray,
    right_prediction: np.ndarray,
    families: np.ndarray,
    contexts: np.ndarray,
    units: np.ndarray,
    *,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    strata: dict[tuple[str, int], list[str]] = {}
    for family, context, unit in zip(families, contexts, units):
        key = (str(family), int(context))
        values = strata.setdefault(key, [])
        if str(unit) not in values:
            values.append(str(unit))
    unit_indices = {str(unit): np.where(units == unit)[0] for unit in np.unique(units)}
    rng = np.random.default_rng(seed)
    values = np.empty(replicates, dtype=np.float64)
    for replicate in range(replicates):
        selected: list[np.ndarray] = []
        for key in sorted(strata):
            pool = np.asarray(strata[key], dtype=np.str_)
            drawn = rng.choice(pool, size=len(pool), replace=True)
            selected.extend(unit_indices[str(unit)] for unit in drawn)
        indices = np.concatenate(selected)
        values[replicate] = _r2(observed[indices], left_prediction[indices]) - _r2(
            observed[indices], right_prediction[indices]
        )
    return {
        "replicates": replicates,
        "ci95": [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))],
        "probability_le_zero": float(np.mean(values <= 0.0)),
    }


def _analyze_condition(
    data: ConditionData,
    condition: str,
    protocol: Mapping[str, Any],
    layer_energy: Mapping[str, float],
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    train = data.splits == "train"
    evaluation = data.splits == "eval"
    if set(data.row_ids[train]) & set(data.row_ids[evaluation]):
        raise AnalysisError("construction and evaluation row IDs overlap")
    rank = int(protocol["spectral_rank"])
    centers: list[list[np.ndarray]] = []
    bases: list[list[np.ndarray]] = []
    singular_values: list[list[np.ndarray]] = []
    directions: list[list[np.ndarray | None]] = []
    support: dict[str, Any] = {}
    for context_index, delta in enumerate(data.deltas):
        context_centers: list[np.ndarray] = []
        context_bases: list[np.ndarray] = []
        context_singular: list[np.ndarray] = []
        context_directions: list[np.ndarray | None] = []
        for layer_index, layer in enumerate(data.layers):
            samples = delta[train, layer_index, :]
            center, basis, singular = fit_pca(samples, rank)
            context_centers.append(center)
            context_bases.append(basis)
            context_singular.append(singular)
            direction = _direction(samples, data.families[train])
            context_directions.append(direction)
            receipt = rank1_support_test(
                samples,
                data.families[train],
                bootstrap_replicates=int(protocol["support"]["bootstrap_replicates"]),
                permutation_replicates=int(protocol["support"]["permutation_replicates"]),
                seed=int(protocol["seeds"]["bootstrap"]) + 101 * context_index + int(layer),
                required_margin=float(protocol["support"]["margin"]),
            )
            support[f"context_{context_index}.layer_{int(layer)}"] = receipt.__dict__
        centers.append(context_centers)
        bases.append(context_bases)
        singular_values.append(context_singular)
        directions.append(context_directions)

    layer_geometry: dict[int, dict[str, Any]] = {}
    h5_passed = True
    for layer_index, layer_value in enumerate(data.layers):
        layer = int(layer_value)
        spatial_edges = [
            polar_transport(bases[context][layer_index], bases[(context + 1) % len(bases)][layer_index])
            for context in range(len(bases))
        ]
        spatial_roots = _root_transports(spatial_edges, rank)
        layer_directions = [directions[context][layer_index] for context in range(len(directions))]
        if any(direction is None for direction in layer_directions):
            behavior_edges = None
            behavior_roots = [np.asarray([[0.0]]) for _ in layer_directions]
            color = "unavailable"
            behavior_gauge = {"passed": True, "replicates": 0, "category": "unavailable"}
        else:
            concrete = [direction for direction in layer_directions if direction is not None]
            behavior_edges = [
                polar_transport(concrete[context], concrete[(context + 1) % len(concrete)])
                for context in range(len(concrete))
            ]
            behavior_roots = _root_transports(behavior_edges, 1)
            color = loop_receipt(behavior_edges).category
            behavior_gauge = _gauge_integrity(
                behavior_edges, int(protocol["seeds"]["gauge"]) + layer, 256
            )
        spatial_gauge = _gauge_integrity(spatial_edges, int(protocol["seeds"]["gauge"]) + 10000 + layer, 256)
        h5_passed = h5_passed and bool(behavior_gauge["passed"]) and bool(spatial_gauge["passed"])
        layer_geometry[layer] = {
            "spatial_edges": spatial_edges,
            "spatial_roots": spatial_roots,
            "behavior_roots": behavior_roots,
            "color": color,
            "behavior_loop": None if behavior_edges is None else loop_receipt(behavior_edges).to_dict(),
            "spatial_loop": loop_receipt(spatial_edges).to_dict(),
            "behavior_gauge": behavior_gauge,
            "spatial_gauge": spatial_gauge,
        }

    supported_layers = []
    for layer_value in data.layers:
        layer = int(layer_value)
        if all(support[f"context_{context}.layer_{layer}"]["passed"] for context in range(len(data.deltas))):
            supported_layers.append(layer)
    h1_passed = len(supported_layers) >= 2

    color_categories = list(protocol["analysis"]["holonomy_categories"])
    feature_rows: dict[str, list[list[float]]] = {
        "baseline": [],
        "xyz": [],
        "xyzt": [],
        "xyzts": [],
        "full": [],
    }
    outcome: list[float] = []
    group_rows: list[str] = []
    family_rows: list[str] = []
    context_rows: list[int] = []
    unit_rows: list[str] = []
    layer_rows: list[int] = []
    mode_rows: list[int] = []
    eval_indices = np.where(evaluation)[0]
    maximum_layer = max(int(value) for value in data.layers)
    for context_index, delta in enumerate(data.deltas):
        for layer_index, layer_value in enumerate(data.layers):
            layer = int(layer_value)
            geometry = layer_geometry[layer]
            spatial_root = geometry["spatial_roots"][context_index]
            behavior_root = geometry["behavior_roots"][context_index]
            spin = 0.0 if float(np.linalg.det(behavior_root)) == 0.0 else (1.0 if np.linalg.det(behavior_root) > 0 else -1.0)
            color_vector = [1.0 if geometry["color"] == category else 0.0 for category in color_categories]
            times = spectral_time(singular_values[context_index][layer_index])
            energy = float(layer_energy.get(str(layer), 0.0))
            for row_index in eval_indices:
                centered = delta[row_index, layer_index, :] - centers[context_index][layer_index]
                local = bases[context_index][layer_index].T @ centered
                rooted = spatial_root.T @ local
                for mode_index, time_value in enumerate(times):
                    active = rooted.copy()
                    active[mode_index + 1 :] = 0.0
                    xyz = np.zeros(3, dtype=np.float64)
                    xyz[: min(3, len(active))] = active[:3]
                    baseline = [layer / maximum_layer, energy]
                    xyz_values = xyz.tolist()
                    xyzt = [*xyz_values, float(time_value)]
                    xyzts = [*xyzt, spin]
                    feature_rows["baseline"].append(baseline)
                    feature_rows["xyz"].append(xyz_values)
                    feature_rows["xyzt"].append(xyzt)
                    feature_rows["xyzts"].append(xyzts)
                    feature_rows["full"].append([*xyzts, *color_vector])
                    outcome.append(float(data.gains[context_index][row_index]))
                    row_id = str(data.row_ids[row_index])
                    group_rows.append(row_id)
                    family_rows.append(str(data.families[row_index]))
                    context_rows.append(context_index)
                    unit_rows.append(f"{row_id}|{context_index}")
                    layer_rows.append(layer)
                    mode_rows.append(mode_index + 1)

    y = np.asarray(outcome, dtype=np.float64)
    groups = np.asarray(group_rows, dtype=np.str_)
    family_array = np.asarray(family_rows, dtype=np.str_)
    context_array = np.asarray(context_rows, dtype=np.int16)
    unit_array = np.asarray(unit_rows, dtype=np.str_)
    prediction_receipts: dict[str, PredictionReceipt] = {}
    for feature_name, values in feature_rows.items():
        prediction_receipts[feature_name] = grouped_nested_ridge_predictions(
            np.asarray(values, dtype=np.float64),
            y,
            groups,
            protocol["statistics"]["ridge_penalties"],
            outer_folds=int(protocol["statistics"]["outer_group_folds"]),
            inner_folds=int(protocol["statistics"]["inner_group_folds"]),
            seed=int(protocol["seeds"]["root"]),
        )
    r2 = {name: receipt.r2 for name, receipt in prediction_receipts.items()}
    increments = {
        "full_minus_baseline": r2["full"] - r2["baseline"],
        "spin": r2["xyzts"] - r2["xyzt"],
        "holonomy_color": r2["full"] - r2["xyzts"],
    }
    bootstrap: dict[str, Any] = {}
    comparisons = {
        "full_minus_baseline": ("full", "baseline"),
        "spin": ("xyzts", "xyzt"),
        "holonomy_color": ("full", "xyzts"),
    }
    for offset, (name, (left, right)) in enumerate(comparisons.items()):
        bootstrap[name] = _bootstrap_increment(
            y,
            prediction_receipts[left].predictions,
            prediction_receipts[right].predictions,
            family_array,
            context_array,
            unit_array,
            replicates=int(protocol["statistics"]["bootstrap_replicates"]),
            seed=int(protocol["seeds"]["bootstrap"]) + offset,
        )
    h2_passed = (
        increments["full_minus_baseline"] >= float(protocol["statistics"]["minimum_full_increment"])
        and bootstrap["full_minus_baseline"]["ci95"][0] > 0.0
    )
    spin_passed = increments["spin"] >= float(protocol["statistics"]["minimum_spin_increment"])
    color_passed = increments["holonomy_color"] >= float(protocol["statistics"]["minimum_holonomy_increment"])
    serializable_geometry = {
        str(layer): {
            key: value
            for key, value in geometry.items()
            if key not in {"spatial_edges", "spatial_roots", "behavior_roots"}
        }
        for layer, geometry in layer_geometry.items()
    }
    result = {
        "condition": condition,
        "construction_rows": int(train.sum()),
        "evaluation_rows": int(evaluation.sum()),
        "expanded_evaluation_points": len(y),
        "supported_layers_all_contexts": supported_layers,
        "support": support,
        "geometry": serializable_geometry,
        "r2": r2,
        "selected_penalties_by_outer_fold": {
            name: receipt.selected_penalties for name, receipt in prediction_receipts.items()
        },
        "increments": increments,
        "bootstrap": bootstrap,
        "gates": {
            "H1_representation": h1_passed,
            "H2_predictive_increment": h2_passed,
            "H3_spin_increment": spin_passed,
            "H3_holonomy_increment": color_passed,
            "H5_gauge_integrity": h5_passed,
        },
        "utility": increments["full_minus_baseline"],
    }
    arrays: dict[str, np.ndarray] = {
        "observed": y,
        "row_ids": groups,
        "families": family_array,
        "contexts": context_array,
        "units": unit_array,
        "layers": np.asarray(layer_rows, dtype=np.int16),
        "spectral_modes": np.asarray(mode_rows, dtype=np.int16),
    }
    for name, receipt in prediction_receipts.items():
        arrays[f"prediction_{name}"] = receipt.predictions
    return result, arrays


def analyze_capture(repo_root: Path, experiment_root: Path, run_id: str) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    protocol_path = experiment_root / "protocol.json"
    protocol_hash = sha256_file(protocol_path)
    frozen = verify_frozen_inputs(repo_root, experiment_root)
    if not frozen["ok"]:
        raise AnalysisError(f"frozen input verification failed: {frozen['checks']}")
    config = resolve_repo_config(repo_root)
    output_root = resolve_config_path(repo_root, config, "pixie_5d_holonomy_output_root")
    run_root = output_root / "capture" / run_id
    try:
        capture_summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError(f"valid completed capture summary is required: {error}") from error
    if capture_summary.get("status") != "COMPLETE" or capture_summary.get("protocol_sha256") != protocol_hash:
        raise AnalysisError("capture is incomplete or belongs to another protocol")
    _verify_context_artifacts(run_root, protocol_hash, protocol)
    layer_energy = capture_summary.get("adapter_layer_effective_update_energy", {})
    if not layer_energy:
        raise AnalysisError("capture summary lacks per-layer adapter update energy")

    conditions: dict[str, Any] = {}
    prediction_hashes: dict[str, str] = {}
    analysis_root = output_root / "analysis" / run_id
    for condition in ("trained", "random_00"):
        result, arrays = _analyze_condition(
            _read_condition(run_root, condition, protocol), condition, protocol, layer_energy
        )
        prediction_path = analysis_root / f"{condition}_oof_predictions.npz"
        atomic_npz(prediction_path, **arrays)
        prediction_hashes[condition] = sha256_file(prediction_path)
        conditions[condition] = result

    trained = conditions["trained"]
    random_control = conditions["random_00"]
    specificity_increment = float(trained["utility"] - random_control["utility"])
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
    elif specificity_increment < 0.05:
        verdict = "RANDOM_CONTROL_NOT_SEPARATED"
    elif finalist:
        verdict = "FINALIST_REQUIRES_19_CONTROLS"
    else:
        verdict = "LINEAGE_ONLY"
    provisional_target = (
        "HOLONOMY_INCREMENTAL" if gates["H3_holonomy_increment"] else "SPIN_INCREMENTAL"
    ) if finalist else None
    report = {
        "schema": "pixie_5d_holonomy_analysis_v1",
        "protocol_sha256": protocol_hash,
        "run_id": run_id,
        "verdict": verdict,
        "provisional_target_if_control_gate_passes": provisional_target,
        "conditions": conditions,
        "specificity": {
            "trained_utility": trained["utility"],
            "random_00_utility": random_control["utility"],
            "trained_minus_random_00": specificity_increment,
            "single_control_is_not_an_empirical_null": True,
        },
        "prediction_artifacts": prediction_hashes,
        "limitations": [
            "One adapter and one base checkpoint cannot establish a universal persona manifold.",
            "Teacher-forced likelihood is a behavioral proxy, not open-ended semantic quality.",
            "A finalist remains provisional until nineteen norm-matched random controls are evaluated.",
            "Rooted spin is gauge-covariant; only the recorded loop class is gauge-invariant.",
        ],
    }
    atomic_json(analysis_root / "analysis.json", report)
    atomic_text(analysis_root / "report.md", _render_markdown(report))
    return report


def _render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Pixie 5D holonomy validation",
        "",
        f"Verdict: **{report['verdict']}**",
        "",
        f"Protocol SHA-256: `{report['protocol_sha256']}`",
        "",
        "## Predictive comparisons",
        "",
        "| Condition | Baseline R2 | XYZT R2 | XYZTS R2 | Full R2 | Utility |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in ("trained", "random_00"):
        condition = report["conditions"][name]
        r2 = condition["r2"]
        lines.append(
            f"| {name} | {r2['baseline']:.4f} | {r2['xyzt']:.4f} | "
            f"{r2['xyzts']:.4f} | {r2['full']:.4f} | {condition['utility']:.4f} |"
        )
    trained = report["conditions"]["trained"]
    lines.extend(
        [
            "",
            "## Registered increments",
            "",
            "| Increment | Estimate | Bootstrap 95% CI |",
            "|---|---:|---:|",
        ]
    )
    for name in ("full_minus_baseline", "spin", "holonomy_color"):
        estimate = trained["increments"][name]
        interval = trained["bootstrap"][name]["ci95"]
        lines.append(f"| {name} | {estimate:.4f} | [{interval[0]:.4f}, {interval[1]:.4f}] |")
    lines.extend(["", "## Gates", ""])
    for gate, passed in trained["gates"].items():
        lines.append(f"- {gate}: **{'PASS' if passed else 'FAIL'}**")
    lines.extend(
        [
            "",
            "## Control boundary",
            "",
            f"Trained minus single random-control utility: `{report['specificity']['trained_minus_random_00']:.4f}`.",
            "The single control is not an empirical random-adapter null distribution.",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines) + "\n"
