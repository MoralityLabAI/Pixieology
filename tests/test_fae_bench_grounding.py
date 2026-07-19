from __future__ import annotations

import json
from pathlib import Path

from fae_bench import (
    contradiction_rate,
    fact_recall,
    score_grounding,
    summarize_grounding,
    unsupported_claim_rate,
)
from fae_bench.grounding_rules import default_grounding_rules
from fae_bench.judge import (
    GROUNDING_RUBRIC,
    GROUNDING_RUBRIC_VERSION,
    JudgeResult,
    llm_grounding_judge,
)


FIXTURE = Path(__file__).parent / "fixtures" / "chronicle_grounding_cases.jsonl"


def _records() -> dict[str, dict]:
    rows = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["condition"]: row for row in rows}


def test_grounding_rules_are_versioned() -> None:
    assert default_grounding_rules().version == "fae_grounding_rules_v1"


def test_fully_grounded_narration_recalls_all_facts_without_conflicts() -> None:
    record = _records()["style_grounded"]
    score = score_grounding(record)
    assert score.fact_recall == 1.0
    assert score.contradiction_rate == 0.0
    assert score.unsupported_claim_rate == 0.0
    assert score.entailed_fact_count == 3
    assert score.statement_count == 3


def test_numeric_and_negation_conflicts_are_detected() -> None:
    record = _records()["style_contradictory"]
    assert fact_recall(record) == 0.0
    assert contradiction_rate(record) == 1.0
    assert unsupported_claim_rate(record) == 0.0


def test_unsupported_entity_and_event_assertion_is_detected() -> None:
    record = _records()["plain_unsupported"]
    assert unsupported_claim_rate(record) == 1.0


def _life_cycle_record(narration: str) -> dict:
    return {
        "window": [
            {"sequence": 1, "tick": 2, "event_type": "birth", "entities": [{"id": "ember-1"}]},
            {"sequence": 2, "tick": 5, "event_type": "death", "entities": [{"id": "ember-1"}]},
        ],
        "fact_list": [
            {
                "fact_id": "birth",
                "predicate": "born_at_tick",
                "subject": "ember-1",
                "value": 2,
                "evidence_event_sequences": [1],
            },
            {
                "fact_id": "death",
                "predicate": "died_at_tick",
                "subject": "ember-1",
                "value": 5,
                "evidence_event_sequences": [2],
            },
            {
                "fact_id": "cause",
                "predicate": "death_cause_chain",
                "subject": "ember-1",
                "value": [{"type": "survival_or_energy_rule", "entity_ids": []}],
                "evidence_event_sequences": [2],
            },
        ],
        "narration": narration,
    }


def test_entity_substitution_is_a_contradiction() -> None:
    record = dict(_records()["plain_grounded"])
    record["narration"] = "Ember-2 crossed the gate."
    score = score_grounding(record)
    assert score.contradiction_rate == 1.0
    assert score.unsupported_claim_rate == 1.0


def test_ordering_conflict_is_detected_independently() -> None:
    score = score_grounding(_life_cycle_record("Ember One died before it was born."))
    assert score.contradiction_rate == 1.0
    assert score.unsupported_claim_rate == 0.0


def test_cause_substitution_is_detected_independently() -> None:
    score = score_grounding(
        _life_cycle_record("Ember One died at tick five because of a storm.")
    )
    assert score.contradiction_rate == 1.0
    assert score.unsupported_claim_rate == 1.0


def test_grounding_summary_is_micro_averaged() -> None:
    records = _records()
    summary = summarize_grounding([records["style_grounded"], records["plain_grounded"]])
    assert summary["record_count"] == 2
    assert summary["fact_count"] == 6
    assert summary["fact_recall"] == 1.0
    assert summary["contradiction_rate"] == 0.0


def test_grounding_llm_judge_uses_the_stronger_injected_rubric() -> None:
    class FakeProvider:
        def judge(self, request):
            assert request.rubric_version == GROUNDING_RUBRIC_VERSION
            assert request.rubric == GROUNDING_RUBRIC
            return JudgeResult(
                overall_score=1.0,
                dimension_scores={dimension: 1.0 for dimension in GROUNDING_RUBRIC},
                rationale="Fixture grounding judge.",
                provider="fake",
                model="fake-v2",
                rubric_version=GROUNDING_RUBRIC_VERSION,
            )

    result = llm_grounding_judge(_records()["style_grounded"], FakeProvider())
    assert result.overall_score == 1.0
