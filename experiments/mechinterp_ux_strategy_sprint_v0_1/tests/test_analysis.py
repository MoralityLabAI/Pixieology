from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from analysis import analyze, agent_decision, load_json, score_sessions  # noqa: E402


SCORER = load_json(EXPERIMENT_ROOT / "scorer_manifest.json")
MANIFEST = load_json(EXPERIMENT_ROOT / "sprint_manifest.json")
CORRECT = SCORER["answers"]
CASES = {
    "band": "ux-band-a",
    "relation": "ux-chain-a",
    "robustness": "ux-robust-a",
    "job": "ux-null-a",
}
WRONG = {
    "band": 0,
    "relation": "none",
    "robustness": "isolated",
    "job": "tinylora",
}


def response(
    task_id: str,
    task_type: str,
    condition: str,
    *,
    correct: bool = True,
    elapsed_ms: float = 1000,
    design_question: str = "workflow",
    variant: str | None = None,
) -> dict:
    case_id = CASES[task_type]
    answer = CORRECT[f"{case_id}:{task_type}"] if correct else WRONG[task_type]
    return {
        "schema": "pixieology_mechinterp_ux_task_response_v1",
        "task_id": task_id,
        "lane": "workflow" if design_question == "workflow" else "components",
        "condition": condition,
        "design_question": design_question,
        "variant": variant or condition,
        "task_type": task_type,
        "case_id": case_id,
        "answer": answer,
        "claim_scope": "descriptive_only",
        "confidence": 4,
        "elapsed_ms": elapsed_ms,
        "analysis": {
            "schema": "pixieology_etale_analysis_v3",
            "coordinate_source": "synthetic_ux_fixture",
            "state": {"case_id": case_id},
            "spin": {"available": False},
        },
    }


def session(
    participant_id: str,
    cohort: str,
    lane: str,
    responses: list[dict],
    *,
    agent_contract: dict | None = None,
) -> dict:
    value = {
        "schema": "pixieology_mechinterp_ux_session_v1",
        "study_id": "mechinterp_ux_strategy_sprint_v0_1",
        "session_id": f"{participant_id}-{lane}",
        "participant_id": participant_id,
        "cohort": cohort,
        "lane": lane,
        "baseline_commit": MANIFEST["baseline"]["commit"],
        "started_utc": "2026-07-26T00:00:00Z",
        "ended_utc": "2026-07-26T00:10:00Z",
        "completed": True,
        "task_order": [item["task_id"] for item in responses],
        "responses": responses,
        "privacy": {"anonymous_code_only": True, "network_telemetry": False},
        "claim_boundary": MANIFEST["claim_boundary"],
    }
    if agent_contract is not None:
        value["agent_contract"] = agent_contract
    return value


def workflow_responses() -> list[dict]:
    values = []
    for index, task_type in enumerate(CASES):
        values.append(
            response(
                f"baseline-{task_type}",
                task_type,
                "baseline",
                correct=index != 0,
                elapsed_ms=1000,
            )
        )
        values.append(
            response(
                f"triage-{task_type}",
                task_type,
                "triage_progressive",
                elapsed_ms=800,
            )
        )
    return values


def test_six_paired_researchers_promote_progressive_triage() -> None:
    sessions = [
        session(f"R0{index}", "researcher", "workflow", workflow_responses())
        for index in range(1, 7)
    ]
    result = analyze(sessions, MANIFEST, SCORER)
    assert result["status"] == "FORMATIVE_DECISION_READY"
    assert result["workflow"]["verdict"] == "PROMOTE_TRIAGE_DEFAULT"
    assert result["workflow"]["accuracy_increment"] == pytest.approx(0.25)
    assert result["workflow"]["median_time_ratio"] == pytest.approx(0.8)
    assert result["confirmatory_gate"]["status"] == "DEFERRED_UNTIL_CONFIRMED_ACTIVATION_CATALOG"


def test_learner_gate_uses_manifest_minimum() -> None:
    sessions = [
        session(
            f"L0{index}",
            "learner_gamer",
            "workflow",
            [
                response(
                    f"learner-{index}-{task_type}",
                    task_type,
                    "triage_progressive",
                )
                for task_type in CASES
            ],
        )
        for index in range(1, 7)
    ]
    result = analyze(sessions, MANIFEST, SCORER)
    assert result["learner"]["participants"] == 6
    assert result["learner"]["verdict"] == "PROMOTE_GUIDED_MODE"


def test_agent_contract_must_be_explicit() -> None:
    scored = score_sessions(
        [
            session(
                "A01",
                "agent",
                "workflow",
                [response("agent-band", "band", "triage_progressive")],
            )
        ],
        SCORER,
    )
    assert agent_decision(scored)["verdict"] == "NOT_RUN_OR_FAIL"

    scored[0]["agent_contract"] = {
        "structured_analysis_used": True,
        "svg_parsing_used": False,
        "browser_authorization_method_used": False,
    }
    assert agent_decision(scored)["verdict"] == "PASS"


def test_component_ties_keep_conservative_defaults() -> None:
    variants = MANIFEST["component_questions"]
    sessions = []
    task_type_by_question = {
        "orientation": "band",
        "threshold": "relation",
        "language": "robustness",
        "jobs": "job",
    }
    for index in range(1, 7):
        responses = []
        for question, question_variants in variants.items():
            for variant in question_variants:
                task_type = task_type_by_question[question]
                responses.append(
                    response(
                        f"{question}-{variant}-{index}",
                        task_type,
                        "component_lab",
                        design_question=question,
                        variant=variant,
                    )
                )
        sessions.append(session(f"C0{index}", "researcher", "components", responses))
    result = analyze(sessions, MANIFEST, SCORER)
    assert result["components"]["orientation"]["winner"] == "heatmap"
    assert result["components"]["threshold"]["winner"] == "dendrogram_births"
    assert result["components"]["language"]["winner"] == "dual"
    assert result["components"]["jobs"]["winner"] == "gated"
    assert all(
        item["verdict"] == "USE_CONSERVATIVE_DEFAULT"
        for item in result["components"].values()
    )


def test_fixture_spin_availability_is_fail_closed() -> None:
    value = session("R99", "researcher", "workflow", workflow_responses())
    value["responses"][0]["analysis"]["spin"]["available"] = True
    with pytest.raises(ValueError, match="S unavailable"):
        score_sessions([value], SCORER)
