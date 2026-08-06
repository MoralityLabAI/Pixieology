"""Synthetic implementation fixtures; never model evidence."""

from __future__ import annotations

import random
from typing import Any

from .compare import compare_family
from .distill import TRACE_SCHEMA, distill_program, evaluate_program
from .tasks import build_task_cases, generate_families


def _centers(state_count: int, candidate: str) -> dict[str, list[float]]:
    permutation = list(range(state_count))
    if candidate == "pixie_rank8":
        permutation = permutation[1:] + permutation[:1]
    centers = {}
    for state_index in range(state_count):
        vector = [0.0] * 8
        vector[permutation[state_index]] = 2.0
        vector[6] = state_index / max(1, state_count - 1)
        vector[7] = (state_index % 2) * 0.5
        centers[f"S{state_index}"] = vector
    return centers


def _noisy(vector: list[float], rng: random.Random, noise: float) -> list[float]:
    return [value + rng.uniform(-noise, noise) for value in vector]


def synthetic_traces(
    *,
    candidate: str,
    family_count: int = 8,
    seed: int = 2026080604,
) -> list[dict[str, Any]]:
    families = {family["task_family_id"]: family for family in generate_families(count=family_count)}
    cases = build_task_cases(family_count=family_count)
    rows = []
    for case in cases:
        if case["split"] == "intervention":
            continue
        family = families[case["task_family_id"]]
        centers = _centers(len(family["states"]), candidate)
        rng = random.Random(seed + int(case["task_family_id"].split("-")[-1]) * 1009 + sum(map(ord, case["case_id"])))
        steps = []
        for oracle in case["oracle_trajectory"]:
            observed = oracle["oracle_output_symbol"]
            steps.append({
                "step": oracle["step"],
                "input_symbol": oracle["input_symbol"],
                "output_symbol": observed,
                "oracle_output_symbol": oracle["oracle_output_symbol"],
                "activation": _noisy(centers[oracle["state_before"]], rng, 0.0),
                "next_activation": _noisy(centers[oracle["next_state"]], rng, 0.0),
            })
        rows.append({
            "schema": TRACE_SCHEMA,
            "trace_id": f"{candidate}-{case['case_id']}",
            "case_id": case["case_id"],
            "task_family_id": case["task_family_id"],
            "candidate": candidate,
            "split": case["split"],
            "coordinate_source": "synthetic_implementation_fixture",
            "steps": steps,
        })
    return rows


def _synthetic_interventions(program: dict[str, Any], count: int = 8) -> list[dict[str, Any]]:
    rows = []
    table = program["transition_table"]
    for transition in table:
        baseline = next(
            (candidate["output_symbol"] for candidate in table if candidate["output_symbol"] != transition["output_symbol"]),
            None,
        )
        if baseline is None:
            continue
        index = len(rows)
        rows.append({
            "schema": "pixieology_mechanism_intervention_observation_v1",
            "observation_id": f"{program['candidate']}-{program['task_family_id']}-{index}",
            "task_family_id": program["task_family_id"],
            "candidate": program["candidate"],
            "predicted_output_symbol": transition["output_symbol"],
            "observed_output_symbol": transition["output_symbol"],
            "baseline_output_symbol": baseline,
            "matched_random_output_symbol": baseline,
            "guardrail_delta": 0.0,
            "evidence_class": "synthetic_implementation_fixture",
        })
        if len(rows) >= count:
            break
    return rows


def run_synthetic_smoke(protocol: dict[str, Any], family_count: int = 8) -> dict[str, Any]:
    thresholds = protocol["thresholds"]
    all_traces = {
        candidate: synthetic_traces(candidate=candidate, family_count=family_count)
        for candidate in ("base_qwen_derived_1p7b", "pixie_rank8")
    }
    family_ids = sorted({row["task_family_id"] for row in all_traces["base_qwen_derived_1p7b"]})
    comparisons = []
    programs = []
    evaluations = []
    interventions = []
    for family_id in family_ids:
        values = {}
        for candidate in all_traces:
            rows = [row for row in all_traces[candidate] if row["task_family_id"] == family_id]
            discovery = [row for row in rows if row["split"] == "discovery"]
            held_out = [row for row in rows if row["split"] == "held_out"]
            program = distill_program(
                discovery,
                state_counts=protocol["distillation"]["candidate_state_counts"],
                discovery_fidelity_floor=protocol["distillation"]["discovery_fidelity_floor"],
                maximum_sparse_dimensions=protocol["distillation"]["maximum_sparse_dimensions"],
            )
            evaluation = evaluate_program(program, held_out)
            causal = _synthetic_interventions(program)
            programs.append(program)
            evaluations.append(evaluation)
            interventions.extend(causal)
            values[candidate] = (program, evaluation, causal)
        comparisons.append(compare_family(
            base_program=values["base_qwen_derived_1p7b"][0],
            base_evaluation=values["base_qwen_derived_1p7b"][1],
            base_interventions=values["base_qwen_derived_1p7b"][2],
            pixie_program=values["pixie_rank8"][0],
            pixie_evaluation=values["pixie_rank8"][1],
            pixie_interventions=values["pixie_rank8"][2],
            thresholds=thresholds,
        ))
    return {
        "schema": "pixieology_mechanism_synthetic_smoke_v1",
        "status": "PASS" if all(
            item["alignment"]["available"] and item["alignment"]["fidelity"] == 1.0
            for item in comparisons
        ) else "FAIL",
        "evidence_class": "synthetic_implementation_fixture",
        "human_or_model_evidence": False,
        "family_count": family_count,
        "traces": [row for rows in all_traces.values() for row in rows],
        "programs": programs,
        "evaluations": evaluations,
        "interventions": interventions,
        "comparisons": comparisons,
        "claim_boundary": "This receipt validates code paths only and cannot support a Qwen, Pixie, causal, or human-interpretability claim.",
    }
