"""State-label alignment, causal checks, and family-level verdicts."""

from __future__ import annotations

import itertools
import math
from statistics import mean
from typing import Any


def _transition_lookup(program: dict[str, Any]) -> dict[tuple[int, str], tuple[int, str]]:
    return {
        (row["state"], row["input_symbol"]): (row["next_state"], row["output_symbol"])
        for row in program["transition_table"]
    }


def align_programs(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    base_count = int(base["codebook"]["state_count"])
    candidate_count = int(candidate["codebook"]["state_count"])
    if base_count != candidate_count or base_count > 8:
        return {
            "available": False,
            "bijective": False,
            "reason": "state counts differ or exceed exhaustive alignment limit",
            "fidelity": None,
            "mapping": None,
        }
    base_lookup = _transition_lookup(base)
    candidate_lookup = _transition_lookup(candidate)
    best_score = -1.0
    best_mapping = None
    best_matches = 0
    for permutation in itertools.permutations(range(base_count)):
        mapping = {candidate_state: permutation[candidate_state] for candidate_state in range(candidate_count)}
        mapped_candidate = {}
        for (state, symbol), (next_state, output) in candidate_lookup.items():
            mapped_candidate[(mapping[state], symbol)] = (mapping[next_state], output)
        keys = set(base_lookup) | set(mapped_candidate)
        matches = sum(base_lookup.get(key) == mapped_candidate.get(key) for key in keys)
        denominator = max(1, len(keys))
        score = matches / denominator
        if score > best_score or (score == best_score and tuple(permutation) < tuple(best_mapping or permutation)):
            best_score = score
            best_mapping = mapping
            best_matches = matches
    return {
        "available": True,
        "bijective": True,
        "fidelity": best_score,
        "matched_transitions": best_matches,
        "transition_union_count": denominator,
        "mapping": {str(key): value for key, value in best_mapping.items()},
    }


def score_interventions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "status": "NOT_RUN",
            "observation_count": 0,
            "causal_prediction_accuracy": None,
            "matched_control_margin": None,
            "mean_absolute_guardrail_delta": None,
        }
    required = {
        "predicted_output_symbol", "observed_output_symbol", "baseline_output_symbol",
        "matched_random_output_symbol", "guardrail_delta",
    }
    for row in rows:
        if not required <= set(row):
            raise ValueError("intervention observation is incomplete")
    accuracy = mean(
        row["predicted_output_symbol"] == row["observed_output_symbol"]
        for row in rows
    )
    target_change_rate = mean(
        row["observed_output_symbol"] != row["baseline_output_symbol"]
        for row in rows
    )
    random_change_rate = mean(
        row["matched_random_output_symbol"] != row["baseline_output_symbol"]
        for row in rows
    )
    return {
        "status": "COMPLETE",
        "observation_count": len(rows),
        "causal_prediction_accuracy": accuracy,
        "target_change_rate": target_change_rate,
        "matched_random_change_rate": random_change_rate,
        "matched_control_margin": target_change_rate - random_change_rate,
        "mean_absolute_guardrail_delta": mean(abs(float(row["guardrail_delta"])) for row in rows),
    }


def _hard_gates(evaluation: dict[str, Any], causal: dict[str, Any], thresholds: dict[str, float]) -> dict[str, bool]:
    return {
        "task_accuracy": evaluation["task_accuracy"] >= thresholds["minimum_task_accuracy"],
        "program_fidelity": evaluation["heldout_program_fidelity"] >= thresholds["minimum_heldout_program_fidelity"],
        "sparse_invariant": evaluation["sparse_invariant_agreement"] >= thresholds["minimum_sparse_invariant_agreement"],
        "causal_prediction": causal["status"] == "COMPLETE" and causal["causal_prediction_accuracy"] >= thresholds["minimum_causal_prediction_accuracy"],
        "matched_control": causal["status"] == "COMPLETE" and causal["matched_control_margin"] >= thresholds["minimum_matched_control_margin"],
        "guardrail": causal["status"] == "COMPLETE" and causal["mean_absolute_guardrail_delta"] <= thresholds["maximum_mean_absolute_guardrail_delta"],
    }


def mechanism_evidence_score(
    evaluation: dict[str, Any],
    causal: dict[str, Any],
    thresholds: dict[str, float],
) -> float:
    gates = _hard_gates(evaluation, causal, thresholds)
    if not all(gates.values()):
        return 0.0
    return mean([
        evaluation["task_accuracy"],
        evaluation["heldout_program_fidelity"],
        evaluation["sparse_invariant_agreement"],
        causal["causal_prediction_accuracy"],
        min(1.0, max(0.0, causal["matched_control_margin"])),
        1.0 - min(1.0, causal["mean_absolute_guardrail_delta"]),
    ])


def compare_family(
    *,
    base_program: dict[str, Any],
    base_evaluation: dict[str, Any],
    base_interventions: list[dict[str, Any]],
    pixie_program: dict[str, Any],
    pixie_evaluation: dict[str, Any],
    pixie_interventions: list[dict[str, Any]],
    thresholds: dict[str, float],
) -> dict[str, Any]:
    evidence_classes = {
        str(base_program.get("evidence_class", "unknown")),
        str(pixie_program.get("evidence_class", "unknown")),
        *(str(row.get("evidence_class", "unknown")) for row in base_interventions),
        *(str(row.get("evidence_class", "unknown")) for row in pixie_interventions),
    }
    evidence_class = (
        "registered_activation_and_intervention"
        if evidence_classes <= {"registered_activation_capture", "registered_activation_intervention"}
        else "synthetic_or_incomplete"
    )
    base_causal = score_interventions(base_interventions)
    pixie_causal = score_interventions(pixie_interventions)
    base_gates = _hard_gates(base_evaluation, base_causal, thresholds)
    pixie_gates = _hard_gates(pixie_evaluation, pixie_causal, thresholds)
    base_bits = float(base_program["description_length_bits"])
    pixie_bits = float(pixie_program["description_length_bits"])
    reduction = (base_bits - pixie_bits) / max(1.0, base_bits)
    if not all(base_gates.values()) or not all(pixie_gates.values()):
        winner = "UNDETERMINED"
    elif reduction >= thresholds["minimum_description_length_reduction"]:
        winner = "pixie_rank8"
    elif reduction <= -thresholds["minimum_description_length_reduction"]:
        winner = "base_qwen_derived_1p7b"
    else:
        winner = "TIE"
    alignment = align_programs(base_program, pixie_program)
    if not alignment["available"]:
        isomorphism = "POSSIBLE_ALGORITHM_CHANGE"
    elif alignment["fidelity"] >= thresholds["minimum_isomorphism_fidelity"]:
        isomorphism = "USABLE_ISOMORPHISM"
    else:
        isomorphism = "POSSIBLE_ALGORITHM_CHANGE"
    return {
        "schema": "pixieology_mechanism_family_comparison_v1",
        "task_family_id": base_program["task_family_id"],
        "evidence_class": evidence_class,
        "winner": winner,
        "description_length_reduction": reduction,
        "base": {
            "gates": base_gates,
            "evaluation": base_evaluation,
            "causal": base_causal,
            "description_length_bits": base_bits,
            "mechanism_evidence_score": mechanism_evidence_score(base_evaluation, base_causal, thresholds),
        },
        "pixie": {
            "gates": pixie_gates,
            "evaluation": pixie_evaluation,
            "causal": pixie_causal,
            "description_length_bits": pixie_bits,
            "mechanism_evidence_score": mechanism_evidence_score(pixie_evaluation, pixie_causal, thresholds),
        },
        "alignment": alignment,
        "isomorphism_verdict": isomorphism,
    }


def wilson_lower_bound(successes: int, total: int, z: float = 1.959963984540054) -> float:
    if total <= 0:
        return 0.0
    proportion = successes / total
    denominator = 1 + (z * z / total)
    center = proportion + (z * z / (2 * total))
    margin = z * math.sqrt((proportion * (1 - proportion) / total) + (z * z / (4 * total * total)))
    return (center - margin) / denominator
