from __future__ import annotations

import json
from pathlib import Path

from run_grounding_compare import build_scorecard


FIXTURE = Path(__file__).parent / "fixtures" / "chronicle_grounding_cases.jsonl"


def test_scorecard_separates_style_x_grounding_quadrants() -> None:
    rows = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [row for row in rows if row["condition"] != "plain_unsupported"]
    scorecard = build_scorecard(rows, label="fixture-adapter")
    by_condition = {row["condition"]: row for row in scorecard["records"]}

    assert by_condition["style_grounded"]["style"]["fae_score_lexical"] > by_condition["plain_grounded"]["style"]["fae_score_lexical"]
    assert by_condition["style_contradictory"]["style"]["fae_score_lexical"] > by_condition["plain_contradictory"]["style"]["fae_score_lexical"]
    assert by_condition["style_grounded"]["grounding"]["fact_recall"] == 1.0
    assert by_condition["plain_grounded"]["grounding"]["fact_recall"] == 1.0
    assert by_condition["style_contradictory"]["grounding"]["contradiction_rate"] > 0.0
    assert by_condition["plain_contradictory"]["grounding"]["contradiction_rate"] > 0.0
    assert by_condition["style_grounded"]["passed"] is True
    assert by_condition["plain_grounded"]["passed"] is True
    assert by_condition["style_contradictory"]["passed"] is False
    assert by_condition["plain_contradictory"]["passed"] is False

    assert len(scorecard["episodes"]) == 4
    assert scorecard["certification"]["passed"] is False
    assert scorecard["metric_versions"]["grounding_rules"] == "fae_grounding_rules_v1"
