"""Aggregate deterministic comparison receipts without upgrading missing evidence."""

from __future__ import annotations

from typing import Any

from .compare import wilson_lower_bound


def aggregate_comparisons(
    comparisons: list[dict[str, Any]],
    *,
    expected_families: int,
    minimum_win_rate: float,
) -> dict[str, Any]:
    identifiers = [item.get("task_family_id") for item in comparisons]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("comparison set contains duplicate task families")
    pixie_wins = sum(item.get("winner") == "pixie_rank8" for item in comparisons)
    base_wins = sum(item.get("winner") == "base_qwen_derived_1p7b" for item in comparisons)
    ties = sum(item.get("winner") == "TIE" for item in comparisons)
    undetermined = sum(item.get("winner") == "UNDETERMINED" for item in comparisons)
    coverage = len(comparisons) / expected_families
    registered = bool(comparisons) and all(
        item.get("evidence_class") == "registered_activation_and_intervention"
        for item in comparisons
    )
    win_rate = pixie_wins / expected_families
    lower = wilson_lower_bound(pixie_wins, expected_families)
    complete = len(comparisons) == expected_families and undetermined == 0
    if not registered:
        claim_status = "NOT_RUN"
        operation = "IMPLEMENTATION_ONLY"
        reason = "Registered activation and intervention evidence is absent."
    elif not complete:
        claim_status = "UNDETERMINED"
        operation = "TARGETED_RERUN"
        reason = "Family coverage is incomplete or contains undetermined hard-gate failures."
    elif win_rate >= minimum_win_rate and lower > 0.5:
        claim_status = "SUPPORTED"
        operation = "ACCEPT_LOCAL_CLAIM"
        reason = "Pixie cleared the frozen win-rate and confidence-bound rules."
    else:
        claim_status = "NOT_SUPPORTED"
        operation = "RETAIN_BASELINE_OR_REDESIGN"
        reason = "Pixie did not clear the frozen family-level decision rule."
    return {
        "schema": "pixieology_mechanism_distillation_report_v1",
        "experiment_id": "pixie_mechanism_distillation_v0_1",
        "metric_robustness": {
            "status": "DEVELOPMENT_FIXTURE_PASS_CONFIRMATION_REQUIRED",
            "artifact": "review/robustness/robustness.json",
        },
        "task_result": {
            "expected_families": expected_families,
            "observed_families": len(comparisons),
            "pixie_wins": pixie_wins,
            "base_wins": base_wins,
            "ties": ties,
            "undetermined": undetermined,
            "pixie_win_rate": win_rate,
            "wilson_lower_95": lower,
        },
        "measurement_reliability": {
            "family_coverage": coverage,
            "registered_evidence_only": registered,
            "independent_unit": "task_family_id",
        },
        "claim_support": {"status": claim_status, "reason": reason},
        "operational_decision": {"action": operation, "reason": reason},
        "comparisons": comparisons,
        "claim_boundary": "Program compression without held-out registered interventions cannot support the mechanism claim.",
    }
