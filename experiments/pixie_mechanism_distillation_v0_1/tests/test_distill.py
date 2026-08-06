from __future__ import annotations

import json
from pathlib import Path

from pixie_mechanism_distillation.compare import align_programs, score_interventions
from pixie_mechanism_distillation.distill import distill_program, evaluate_program
from pixie_mechanism_distillation.synthetic import run_synthetic_smoke, synthetic_traces
from pixie_mechanism_distillation.report import aggregate_comparisons


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))


def _program(candidate: str):
    traces = [row for row in synthetic_traces(candidate=candidate, family_count=1) if row["task_family_id"] == "fsm-00"]
    discovery = [row for row in traces if row["split"] == "discovery"]
    held_out = [row for row in traces if row["split"] == "held_out"]
    program = distill_program(discovery)
    return program, evaluate_program(program, held_out)


def test_distilled_program_predicts_heldout_synthetic_transitions() -> None:
    program, evaluation = _program("base_qwen_derived_1p7b")
    assert program["schema"] == "pixieology_distilled_mechanism_v1"
    assert evaluation["heldout_program_fidelity"] == 1.0
    assert evaluation["task_accuracy"] == 1.0
    assert evaluation["sparse_invariant_agreement"] == 1.0


def test_state_alignment_recovers_permuted_isomorphism() -> None:
    base, _ = _program("base_qwen_derived_1p7b")
    pixie, _ = _program("pixie_rank8")
    alignment = align_programs(base, pixie)
    assert alignment["available"] is True
    assert alignment["bijective"] is True
    assert alignment["fidelity"] == 1.0


def test_missing_interventions_never_pass() -> None:
    assert score_interventions([])["status"] == "NOT_RUN"


def test_synthetic_smoke_is_explicitly_non_evidentiary() -> None:
    receipt = run_synthetic_smoke(PROTOCOL, family_count=2)
    assert receipt["status"] == "PASS"
    assert receipt["human_or_model_evidence"] is False
    assert all(item["isomorphism_verdict"] == "USABLE_ISOMORPHISM" for item in receipt["comparisons"])
    report = aggregate_comparisons(
        receipt["comparisons"], expected_families=2, minimum_win_rate=0.6
    )
    assert report["claim_support"]["status"] == "NOT_RUN"
    assert report["operational_decision"]["action"] == "IMPLEMENTATION_ONLY"
