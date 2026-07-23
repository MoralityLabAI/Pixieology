"""Predictive, random-null, intervention, and human-utility gates."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Sequence

import numpy as np

from .graph import form_descriptor
from .mining import assign_motifs


def _outcome(receipt: dict[str, Any]) -> float | None:
    value = receipt.get("provenance", {}).get("behavior", {}).get("adapter_minus_base")
    return None if value is None else float(value)


def _baseline(receipt: dict[str, Any]) -> np.ndarray:
    coordinates = np.asarray(receipt["coordinates"], dtype=np.float64)
    depth = np.linspace(0.0, 1.0, coordinates.shape[0])[:, None, None]
    return np.concatenate(
        [
            np.mean(coordinates, axis=(0, 1)),
            np.std(coordinates, axis=(0, 1)),
            np.max(coordinates, axis=(0, 1)),
            np.mean(coordinates * depth, axis=(0, 1)),
        ]
    )


def _eligible(receipts: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], np.ndarray]:
    rows, outcome = [], []
    for receipt in receipts:
        value = _outcome(receipt)
        if value is not None and np.isfinite(value):
            rows.append(receipt)
            outcome.append(value)
    return rows, np.asarray(outcome, dtype=np.float64)


def _ridge_fit(x: np.ndarray, y: np.ndarray, penalty: float) -> np.ndarray:
    design = np.column_stack([np.ones(len(x)), x])
    regularizer = np.eye(design.shape[1])
    regularizer[0, 0] = 0.0
    return np.linalg.solve(design.T @ design + penalty * regularizer, design.T @ y)


def _ridge_predict(x: np.ndarray, coefficients: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(len(x)), x]) @ coefficients


def _r2(observed: np.ndarray, predicted: np.ndarray) -> float:
    denominator = float(np.sum((observed - np.mean(observed)) ** 2))
    return 0.0 if denominator <= 1e-12 else 1.0 - float(np.sum((observed - predicted) ** 2)) / denominator


def _select_penalty(x: np.ndarray, y: np.ndarray, groups: Sequence[str], penalties: Sequence[float]) -> float:
    unique = sorted(set(groups))
    folds = [set(unique[index::4]) for index in range(4)]
    scores: dict[float, list[float]] = {float(penalty): [] for penalty in penalties}
    group_array = np.asarray(groups)
    for held_out in folds:
        test = np.asarray([group in held_out for group in group_array], dtype=bool)
        if not np.any(test) or not np.any(~test):
            continue
        mean = np.mean(x[~test], axis=0)
        scale = np.std(x[~test], axis=0)
        scale = np.where(scale < 1e-12, 1.0, scale)
        for penalty in penalties:
            coefficients = _ridge_fit((x[~test] - mean) / scale, y[~test], float(penalty))
            scores[float(penalty)].append(_r2(y[test], _ridge_predict((x[test] - mean) / scale, coefficients)))
    return max(scores, key=lambda penalty: (np.mean(scores[penalty]) if scores[penalty] else -np.inf, -penalty))


def predictive_gate(
    discovery: Sequence[dict[str, Any]],
    confirmation: Sequence[dict[str, Any]],
    *,
    minimum_increment: float = 0.05,
    penalties: Sequence[float] = (0.01, 0.1, 1.0, 10.0),
    bootstrap_replicates: int = 2000,
    seed: int = 2026072305,
) -> dict[str, Any]:
    discovery_rows, discovery_y = _eligible(discovery)
    confirmation_rows, confirmation_y = _eligible(confirmation)
    if len(discovery_rows) < 8 or len(confirmation_rows) < 4:
        return {"status": "UNAVAILABLE", "reason": "insufficient outcome-eligible rows"}
    baseline_discovery = np.stack([_baseline(row) for row in discovery_rows])
    baseline_confirmation = np.stack([_baseline(row) for row in confirmation_rows])
    descriptor_discovery = np.stack([form_descriptor(row)[1] for row in discovery_rows])
    descriptor_confirmation = np.stack([form_descriptor(row)[1] for row in confirmation_rows])
    groups = [str(row["input"]["semantic_group_id"]) for row in discovery_rows]

    results = {}
    predictions = {}
    for name, x_train, x_test in (
        ("baseline", baseline_discovery, baseline_confirmation),
        ("topology", descriptor_discovery, descriptor_confirmation),
    ):
        mean = np.mean(x_train, axis=0)
        scale = np.std(x_train, axis=0)
        scale = np.where(scale < 1e-12, 1.0, scale)
        penalty = _select_penalty(x_train, discovery_y, groups, penalties)
        coefficients = _ridge_fit((x_train - mean) / scale, discovery_y, penalty)
        prediction = _ridge_predict((x_test - mean) / scale, coefficients)
        predictions[name] = prediction
        results[name] = {"r2": _r2(confirmation_y, prediction), "penalty": penalty}
    increment = results["topology"]["r2"] - results["baseline"]["r2"]
    confirmation_groups = np.asarray([row["input"]["semantic_group_id"] for row in confirmation_rows])
    unique = sorted(set(confirmation_groups.tolist()))
    rng = np.random.default_rng(seed)
    bootstrap = np.zeros(bootstrap_replicates, dtype=np.float64)
    indices = {group: np.where(confirmation_groups == group)[0] for group in unique}
    for replicate in range(bootstrap_replicates):
        drawn = rng.choice(unique, size=len(unique), replace=True)
        sample = np.concatenate([indices[str(group)] for group in drawn])
        bootstrap[replicate] = _r2(confirmation_y[sample], predictions["topology"][sample]) - _r2(
            confirmation_y[sample], predictions["baseline"][sample]
        )
    interval = [float(np.quantile(bootstrap, 0.025)), float(np.quantile(bootstrap, 0.975))]
    return {
        "status": "PASS" if increment >= minimum_increment and interval[0] > 0.0 else "FAIL",
        "models": results,
        "increment": increment,
        "bootstrap_ci95": interval,
        "minimum_increment": minimum_increment,
        "fit_split": "discovery",
        "evaluation_split": "confirmation",
    }


def random_adapter_max_stat_gate(
    trained_confirmation: Sequence[dict[str, Any]],
    random_confirmation_sets: Iterable[Sequence[dict[str, Any]]],
    model: dict[str, Any],
) -> dict[str, Any]:
    trained = assign_motifs(trained_confirmation, model)
    motif_ids = [motif["motif_id"] for motif in model.get("motifs", [])]

    def prevalences(assignments: Sequence[dict[str, Any]]) -> dict[str, float]:
        denominator = max(1, len(assignments))
        return {
            motif_id: sum(item["motif_id"] == motif_id for item in assignments) / denominator
            for motif_id in motif_ids
        }

    trained_prevalence = prevalences(trained)
    null_maxima = []
    for receipts in random_confirmation_sets:
        null = prevalences(assign_motifs(receipts, model))
        null_maxima.append(max(null.values(), default=0.0))
    motifs = []
    for motif_id in motif_ids:
        observed = trained_prevalence[motif_id]
        p_value = (1 + sum(value >= observed for value in null_maxima)) / (1 + len(null_maxima))
        motifs.append(
            {
                "motif_id": motif_id,
                "trained_prevalence": observed,
                "max_stat_empirical_p": p_value,
                "status": "PASS" if len(null_maxima) == 19 and p_value <= 0.05 else "FAIL",
            }
        )
    return {
        "schema": "pixieology_etale_random_max_stat_v1",
        "control_count": len(null_maxima),
        "selection_correction": "per_control_max_motif_prevalence",
        "motifs": motifs,
        "status": "PASS" if any(item["status"] == "PASS" for item in motifs) else "NULL_DOMINATED",
    }


def intervention_gate(
    rows: Sequence[dict[str, Any]],
    *,
    effect_floor: float = 0.30,
    bootstrap_replicates: int = 2000,
    seed: int = 2026072305,
) -> dict[str, Any]:
    by_unit: dict[str, dict[str, float]] = defaultdict(dict)
    groups: dict[str, str] = {}
    for row in rows:
        if row.get("schema") != "pixieology_etale_intervention_observation_v1":
            raise ValueError("invalid intervention observation schema")
        if not {
            "task_id", "plan_sha256", "unit_id", "semantic_group_id",
            "motif_id", "condition", "outcome",
        } <= set(row):
            raise ValueError("incomplete intervention observation")
        by_unit[str(row["unit_id"])][str(row["condition"])] = float(row["outcome"])
        groups[str(row["unit_id"])] = str(row["semantic_group_id"])
    effects = []
    effect_groups = []
    for unit_id, values in by_unit.items():
        if {"full_adapter", "targeted_mask", "energy_matched_mask"} <= set(values):
            targeted = values["full_adapter"] - values["targeted_mask"]
            matched = values["full_adapter"] - values["energy_matched_mask"]
            effects.append(targeted - matched)
            effect_groups.append(groups[unit_id])
    if len(effects) < 4:
        return {"status": "UNAVAILABLE", "reason": "fewer than four complete intervention units"}
    effect = np.asarray(effects, dtype=np.float64)
    standardized = float(np.mean(effect) / max(np.std(effect, ddof=1), 1e-12))
    rng = np.random.default_rng(seed)
    unique = sorted(set(effect_groups))
    indices = {group: np.where(np.asarray(effect_groups) == group)[0] for group in unique}
    bootstrap = []
    for _ in range(bootstrap_replicates):
        drawn = rng.choice(unique, size=len(unique), replace=True)
        sample = np.concatenate([indices[str(group)] for group in drawn])
        bootstrap.append(float(np.mean(effect[sample])))
    interval = [float(np.quantile(bootstrap, 0.025)), float(np.quantile(bootstrap, 0.975))]
    return {
        "status": "PASS" if standardized >= effect_floor and interval[0] > 0.0 else "FAIL",
        "units": len(effect),
        "targeted_minus_matched_mean": float(np.mean(effect)),
        "standardized_effect": standardized,
        "bootstrap_ci95": interval,
        "effect_floor": effect_floor,
    }


def analyze_human_study(
    rows: Sequence[dict[str, Any]],
    *,
    craft_minimum_participants: int = 12,
    craft_correctness_increment: float = 0.15,
    craft_maximum_time_ratio: float = 0.90,
    craft_maximum_unsupported_increment: float = 0.0,
    learning_minimum_participants: int = 32,
    learning_transfer_increment: float = 0.15,
    learning_retention_fraction: float = 0.80,
) -> dict[str, Any]:
    for row in rows:
        if row.get("schema") != "pixieology_etale_human_study_row_v1":
            raise ValueError("invalid human study row schema")
        if row.get("study") == "craft":
            required = {"participant_id", "condition", "correct", "elapsed_ms", "unsupported_causal_claim"}
            if row.get("condition") not in {"raw", "motif"} or not required <= set(row):
                raise ValueError("incomplete craft study row")
        elif row.get("study") == "learning":
            required = {
                "participant_id", "condition", "pretest_accuracy",
                "immediate_accuracy", "transfer_accuracy",
            }
            if row.get("condition") not in {"conventional", "motif"} or not required <= set(row):
                raise ValueError("incomplete learning study row")
        else:
            raise ValueError("unknown human study")
    craft = [row for row in rows if row.get("study") == "craft"]
    learning = [row for row in rows if row.get("study") == "learning"]
    craft_by_participant: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in craft:
        craft_by_participant[str(row["participant_id"])][str(row["condition"])].append(row)
    paired = []
    time_ratios = []
    unsupported_delta = []
    for conditions in craft_by_participant.values():
        if {"raw", "motif"} <= set(conditions):
            raw, motif = conditions["raw"], conditions["motif"]
            paired.append(np.mean([item["correct"] for item in motif]) - np.mean([item["correct"] for item in raw]))
            time_ratios.append(
                np.median([item["elapsed_ms"] for item in motif]) / max(1.0, np.median([item["elapsed_ms"] for item in raw]))
            )
            unsupported_delta.append(
                np.mean([item["unsupported_causal_claim"] for item in motif]) -
                np.mean([item["unsupported_causal_claim"] for item in raw])
            )
    craft_result = {
        "participants": len(paired),
        "correctness_increment": float(np.mean(paired)) if paired else None,
        "median_time_ratio": float(np.median(time_ratios)) if time_ratios else None,
        "unsupported_claim_increment": float(np.mean(unsupported_delta)) if unsupported_delta else None,
    }
    craft_result["status"] = (
        "PASS"
        if len(paired) >= craft_minimum_participants
        and craft_result["correctness_increment"] >= craft_correctness_increment
        and craft_result["median_time_ratio"] <= craft_maximum_time_ratio
        and craft_result["unsupported_claim_increment"] <= craft_maximum_unsupported_increment
        else "NOT_RUN_OR_FAIL"
    )
    learning_by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in learning:
        learning_by_condition[str(row["condition"])].append(row)
    if {"conventional", "motif"} <= set(learning_by_condition):
        conventional = learning_by_condition["conventional"]
        motif = learning_by_condition["motif"]
        transfer_increment = np.mean([row["transfer_accuracy"] for row in motif]) - np.mean(
            [row["transfer_accuracy"] for row in conventional]
        )
        immediate_gain = np.mean([row["immediate_accuracy"] - row["pretest_accuracy"] for row in motif])
        retained_gain = np.mean([row["transfer_accuracy"] - row["pretest_accuracy"] for row in motif])
        retention = retained_gain / max(immediate_gain, 1e-12)
    else:
        transfer_increment, retention = None, None
    learning_participants = len({str(row["participant_id"]) for row in learning})
    learning_result = {
        "participants": learning_participants,
        "transfer_accuracy_increment": None if transfer_increment is None else float(transfer_increment),
        "retention_fraction": None if retention is None else float(retention),
    }
    learning_result["status"] = (
        "PASS"
        if learning_participants >= learning_minimum_participants
        and transfer_increment is not None
        and transfer_increment >= learning_transfer_increment
        and retention >= learning_retention_fraction
        else "NOT_RUN_OR_FAIL"
    )
    return {
        "schema": "pixieology_etale_human_study_analysis_v1",
        "craft": craft_result,
        "learning": learning_result,
        "registered_thresholds": {
            "craft_minimum_paired_participants": craft_minimum_participants,
            "craft_correctness_increment": craft_correctness_increment,
            "craft_maximum_median_time_ratio": craft_maximum_time_ratio,
            "craft_maximum_unsupported_claim_increment": craft_maximum_unsupported_increment,
            "learning_minimum_participants": learning_minimum_participants,
            "learning_transfer_accuracy_increment": learning_transfer_increment,
            "learning_retention_fraction": learning_retention_fraction,
        },
        "synthetic_agent_smoke_is_human_evidence": False,
        "status": "PASS" if craft_result["status"] == learning_result["status"] == "PASS" else "NOT_RUN_OR_FAIL",
    }
