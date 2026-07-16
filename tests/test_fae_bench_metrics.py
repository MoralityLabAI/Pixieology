from __future__ import annotations

import json
from pathlib import Path

import pytest

from fae_bench import echo_rate, fae_score_lexical, plain_drift, summarize_records, toggle_adherence
from fae_bench.judge import JudgeResult, RUBRIC, llm_judge
from fae_bench.markers import default_marker_set


FIXTURE = Path(__file__).parent / "fixtures" / "fae_bench_tiny.jsonl"


@pytest.fixture(scope="module")
def records() -> dict[str, dict[str, str]]:
    rows = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["condition"]: row for row in rows}


def test_fae_score_lexical_uses_versioned_yaml(records: dict[str, dict[str, str]]) -> None:
    assert default_marker_set().version == "fae_markers_v1"
    assert fae_score_lexical(records["clear_fae"]) > 0.70
    assert fae_score_lexical(records["clear_plain"]) == 0.0


def test_echo_rate_detects_prompt_parroting(records: dict[str, dict[str, str]]) -> None:
    assert echo_rate(records["echo_heavy"]) == 1.0
    assert echo_rate(records["clear_plain"]) < echo_rate(records["echo_heavy"])


def test_plain_drift_penalizes_only_plain_fae_leakage(records: dict[str, dict[str, str]]) -> None:
    leaking = dict(records["clear_fae"], mode="plain")
    assert plain_drift(leaking) > 0.70
    assert plain_drift(records["clear_plain"]) == 0.0
    assert plain_drift(records["clear_fae"]) == 0.0


def test_toggle_adherence_detects_violation(records: dict[str, dict[str, str]]) -> None:
    assert toggle_adherence(records["clear_fae"]) == 1.0
    assert toggle_adherence(records["clear_plain"]) == 1.0
    assert toggle_adherence(records["toggle_violation"]) == 0.0


def test_fixture_jsonl_summarizes_all_four_metrics(records: dict[str, dict[str, str]]) -> None:
    summary = summarize_records(records.values())
    assert summary["record_count"] == 4
    assert summary["fae_record_count"] == 1
    assert summary["plain_record_count"] == 3
    assert set(summary) >= {"fae_score_lexical", "echo_rate", "plain_drift", "toggle_adherence"}


def test_llm_judge_requires_injected_provider(records: dict[str, dict[str, str]]) -> None:
    with pytest.raises(NotImplementedError, match="Inject a JudgeProvider"):
        llm_judge(records["clear_fae"])

    class FakeProvider:
        def judge(self, request):
            return JudgeResult(
                overall_score=0.75,
                dimension_scores={dimension: 0.75 for dimension in RUBRIC},
                rationale="Fixture-only structured judge result.",
                provider="fake",
                model="fake-v1",
            )

    assert llm_judge(records["clear_fae"], FakeProvider()).overall_score == 0.75
