"""Receipt scoring and formative strategy decisions for the UX sprint."""

from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
import re
from statistics import mean, median
from typing import Any, Iterable


SESSION_SCHEMA = "pixieology_mechinterp_ux_session_v1"
DECISION_SCHEMA = "pixieology_mechinterp_ux_strategy_decision_v1"
ANONYMOUS_CODE = re.compile(r"^[A-Z][A-Z0-9_-]{1,15}$")
DEFAULT_COMPONENTS = {
    "orientation": "heatmap",
    "threshold": "dendrogram_births",
    "language": "dual",
    "jobs": "gated",
}
COMPONENT_VARIANTS = {
    "orientation": {"heatmap", "globe", "case_first"},
    "threshold": {"slider", "dendrogram_births"},
    "language": {"technical", "dual"},
    "jobs": {"inline", "gated"},
}
CLAIM_SCOPES = {
    "descriptive_only",
    "causal_mechanism",
    "literal_branching",
    "human_utility",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_sessions(root: Path) -> list[dict[str, Any]]:
    paths = [root] if root.is_file() else sorted(root.rglob("*.json"))
    sessions = []
    for path in paths:
        try:
            value = load_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if value.get("schema") == SESSION_SCHEMA:
            value["_source_path"] = str(path)
            sessions.append(value)
    return sessions


def validate_session(session: dict[str, Any]) -> None:
    if session.get("schema") != SESSION_SCHEMA:
        raise ValueError("invalid UX session schema")
    participant = str(session.get("participant_id", ""))
    if not ANONYMOUS_CODE.fullmatch(participant):
        raise ValueError("participant ID is not an anonymous study code")
    if session.get("cohort") not in {"researcher", "learner_gamer", "agent"}:
        raise ValueError("unknown UX study cohort")
    if session.get("lane") not in {"workflow", "components"}:
        raise ValueError("unknown UX study lane")
    if session.get("privacy") != {
        "anonymous_code_only": True,
        "network_telemetry": False,
    }:
        raise ValueError("UX session privacy contract differs from the sealed study")
    if session.get("completed") is not True or not session.get("ended_utc"):
        raise ValueError("incomplete UX session")
    order = list(session.get("task_order", []))
    responses = list(session.get("responses", []))
    if len(order) != len(responses) or len(order) == 0:
        raise ValueError("session task and response counts differ")
    response_ids = [response.get("task_id") for response in responses]
    if response_ids != order or len(set(response_ids)) != len(response_ids):
        raise ValueError("session responses do not match the sealed task order")
    for response in responses:
        if response.get("schema") != "pixieology_mechinterp_ux_task_response_v1":
            raise ValueError("invalid UX task response schema")
        if float(response.get("elapsed_ms", -1)) < 0:
            raise ValueError("negative UX task duration")
        if int(response.get("confidence", 0)) not in range(1, 6):
            raise ValueError("UX task confidence must be in 1..5")
        if response.get("claim_scope") not in CLAIM_SCOPES:
            raise ValueError("unknown UX evidence boundary")
        analysis = response.get("analysis", {})
        if analysis.get("schema") != "pixieology_etale_analysis_v3":
            raise ValueError("UX task is missing the structured explorer analysis")
        if analysis.get("coordinate_source") != "synthetic_ux_fixture":
            raise ValueError("UX sprint responses must use sealed synthetic fixtures")
        if analysis.get("spin", {}).get("available") is not False:
            raise ValueError("fixture responses must report S unavailable")


def score_sessions(
    sessions: Iterable[dict[str, Any]],
    scorer: dict[str, Any],
) -> list[dict[str, Any]]:
    unsupported_values = set(scorer["unsupported_claim_values"])
    answers = scorer["answers"]
    scored = []
    for session in sessions:
        validate_session(session)
        value = {key: item for key, item in session.items() if not key.startswith("_")}
        value["responses"] = []
        for response in session["responses"]:
            expected_key = f"{response['case_id']}:{response['task_type']}"
            if expected_key not in answers:
                raise ValueError(f"no sealed answer for {expected_key}")
            expected = answers[expected_key]
            observed = response.get("answer")
            if isinstance(expected, (int, float)) and not isinstance(expected, bool):
                correct = math.isclose(float(observed), float(expected), abs_tol=1e-9)
            else:
                correct = observed == expected
            scored_response = dict(response)
            scored_response["correct"] = bool(correct)
            scored_response["unsupported_claim"] = (
                response.get("claim_scope") in unsupported_values
            )
            scored_response["job_choice_correct"] = (
                bool(correct) if response.get("task_type") == scorer["job_task_type"] else None
            )
            value["responses"].append(scored_response)
        scored.append(value)
    return scored


def _condition_metrics(responses: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "tasks": len(responses),
        "accuracy": mean(response["correct"] for response in responses) if responses else None,
        "median_elapsed_ms": median(response["elapsed_ms"] for response in responses) if responses else None,
        "unsupported_claim_rate": (
            mean(response["unsupported_claim"] for response in responses)
            if responses else None
        ),
        "job_choice_accuracy": (
            mean(
                response["job_choice_correct"]
                for response in responses
                if response["job_choice_correct"] is not None
            )
            if any(response["job_choice_correct"] is not None for response in responses)
            else None
        ),
    }


def workflow_decision(
    sessions: list[dict[str, Any]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    researcher = [
        session for session in sessions
        if session["cohort"] == "researcher" and session["lane"] == "workflow"
    ]
    paired = []
    for session in researcher:
        by_condition = defaultdict(list)
        for response in session["responses"]:
            by_condition[response["condition"]].append(response)
        if {"baseline", "triage_progressive"} <= set(by_condition):
            baseline = _condition_metrics(by_condition["baseline"])
            triage = _condition_metrics(by_condition["triage_progressive"])
            paired.append(
                {
                    "participant_id": session["participant_id"],
                    "baseline": baseline,
                    "triage_progressive": triage,
                    "accuracy_increment": triage["accuracy"] - baseline["accuracy"],
                    "time_ratio": triage["median_elapsed_ms"] / max(1.0, baseline["median_elapsed_ms"]),
                    "unsupported_claim_increment": (
                        triage["unsupported_claim_rate"] - baseline["unsupported_claim_rate"]
                    ),
                }
            )
    result = {
        "paired_researchers": len(paired),
        "accuracy_increment": mean(item["accuracy_increment"] for item in paired) if paired else None,
        "median_time_ratio": median(item["time_ratio"] for item in paired) if paired else None,
        "unsupported_claim_increment": (
            mean(item["unsupported_claim_increment"] for item in paired) if paired else None
        ),
        "triage_job_choice_accuracy": (
            mean(item["triage_progressive"]["job_choice_accuracy"] for item in paired)
            if paired and all(item["triage_progressive"]["job_choice_accuracy"] is not None for item in paired)
            else None
        ),
        "participant_metrics": paired,
        "thresholds": thresholds,
    }
    enough = len(paired) >= int(thresholds["minimum_paired_researchers"])
    accuracy_pass = enough and result["accuracy_increment"] >= float(
        thresholds["minimum_correctness_increment"]
    )
    time_pass = enough and result["median_time_ratio"] <= float(
        thresholds["maximum_median_time_ratio"]
    )
    claim_pass = enough and result["unsupported_claim_increment"] <= float(
        thresholds["maximum_unsupported_claim_increment"]
    )
    job_pass = enough and result["triage_job_choice_accuracy"] >= float(
        thresholds["minimum_job_choice_accuracy"]
    )
    result["gates"] = {
        "minimum_sample": enough,
        "correctness": accuracy_pass,
        "time": time_pass,
        "unsupported_claims": claim_pass,
        "job_choice": job_pass,
    }
    if not enough:
        result["verdict"] = "NOT_RUN"
    elif all(result["gates"].values()):
        result["verdict"] = "PROMOTE_TRIAGE_DEFAULT"
    elif accuracy_pass and claim_pass and job_pass:
        result["verdict"] = "TRIAGE_OPTIONAL_GUIDED"
    else:
        result["verdict"] = "RETAIN_BASELINE"
    return result


def learner_decision(
    sessions: list[dict[str, Any]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    values = [
        session for session in sessions
        if session["cohort"] == "learner_gamer" and session["lane"] == "workflow"
    ]
    participants = {session["participant_id"] for session in values}
    triage = [
        response
        for session in values
        for response in session["responses"]
        if response["condition"] == "triage_progressive"
    ]
    unsupported_participants = {
        session["participant_id"]
        for session in values
        if any(response["unsupported_claim"] for response in session["responses"])
    }
    accuracy = mean(response["correct"] for response in triage) if triage else None
    enough = len(participants) >= int(thresholds["minimum_participants"])
    result = {
        "participants": len(participants),
        "triage_transfer_accuracy": accuracy,
        "participants_with_unsupported_claim": len(unsupported_participants),
        "thresholds": thresholds,
    }
    if not enough:
        result["verdict"] = "NOT_RUN"
    elif (
        accuracy >= float(thresholds["minimum_transfer_accuracy"])
        and len(unsupported_participants)
        <= int(thresholds["maximum_participants_with_unsupported_claim"])
    ):
        result["verdict"] = "PROMOTE_GUIDED_MODE"
    else:
        result["verdict"] = "DO_NOT_PROMOTE"
    return result


def component_decisions(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    component = [
        session for session in sessions
        if session["cohort"] == "researcher" and session["lane"] == "components"
    ]
    grouped: dict[str, dict[str, list[tuple[str, dict[str, Any]]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for session in component:
        for response in session["responses"]:
            grouped[response["design_question"]][response["variant"]].append(
                (session["participant_id"], response)
            )
    decisions: dict[str, Any] = {}
    for question, expected_variants in COMPONENT_VARIANTS.items():
        variants = grouped.get(question, {})
        participant_sets = [
            {participant for participant, _ in variants.get(variant, [])}
            for variant in expected_variants
        ]
        complete_participants = (
            set.intersection(*participant_sets)
            if participant_sets and all(participant_sets)
            else set()
        )
        metrics = {
            variant: _condition_metrics(
                [
                    response
                    for participant, response in variants.get(variant, [])
                    if participant in complete_participants
                ]
            )
            for variant in expected_variants
        }
        default = DEFAULT_COMPONENTS[question]
        participant_count = len(complete_participants)
        if participant_count < 6:
            winner = None
            verdict = "NOT_RUN"
        else:
            ordered = sorted(
                metrics,
                key=lambda variant: (
                    -metrics[variant]["accuracy"],
                    metrics[variant]["unsupported_claim_rate"],
                    metrics[variant]["median_elapsed_ms"],
                    variant != default,
                ),
            )
            best = ordered[0]
            runner = ordered[1] if len(ordered) > 1 else best
            accuracy_advantage = metrics[best]["accuracy"] - metrics[runner]["accuracy"]
            time_ratio = metrics[best]["median_elapsed_ms"] / max(
                1.0, metrics[runner]["median_elapsed_ms"]
            )
            safe = metrics[best]["unsupported_claim_rate"] <= metrics[runner]["unsupported_claim_rate"]
            decisive = safe and (
                (accuracy_advantage >= 0.15 and time_ratio <= 1.0)
                or (accuracy_advantage >= 0 and time_ratio <= 0.90)
            )
            winner = best if decisive else default
            verdict = "SELECT_VARIANT" if decisive else "USE_CONSERVATIVE_DEFAULT"
        decisions[question] = {
            "participants": participant_count,
            "variants": metrics,
            "winner": winner,
            "default_on_tie": default,
            "verdict": verdict,
        }
    return decisions


def agent_decision(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    agents = [session for session in sessions if session["cohort"] == "agent"]
    responses = [response for session in agents for response in session["responses"]]
    contract_complete = bool(agents) and all(
        isinstance(session.get("agent_contract"), dict)
        and session["agent_contract"].get("structured_analysis_used") is True
        and session["agent_contract"].get("svg_parsing_used") is False
        and session["agent_contract"].get("browser_authorization_method_used") is False
        for session in agents
    )
    result = {
        "sessions": len(agents),
        "tasks": len(responses),
        "task_completion": mean(response["correct"] for response in responses) if responses else None,
        "unsupported_claims": sum(response["unsupported_claim"] for response in responses),
        "svg_parsing_used": any(
            bool(session.get("agent_contract", {}).get("svg_parsing_used"))
            for session in agents
        ),
        "browser_authorization_method_used": any(
            bool(session.get("agent_contract", {}).get("browser_authorization_method_used"))
            for session in agents
        ),
        "contract_complete": contract_complete,
        "structured_analysis_used": bool(agents) and all(
            session.get("agent_contract", {}).get("structured_analysis_used") is True
            for session in agents
        ),
    }
    result["verdict"] = (
        "PASS"
        if responses
        and result["task_completion"] == 1.0
        and result["unsupported_claims"] == 0
        and result["contract_complete"]
        and result["svg_parsing_used"] is False
        and result["browser_authorization_method_used"] is False
        else "NOT_RUN_OR_FAIL"
    )
    return result


def analyze(
    sessions: list[dict[str, Any]],
    manifest: dict[str, Any],
    scorer: dict[str, Any],
) -> dict[str, Any]:
    scored = score_sessions(sessions, scorer)
    workflow = workflow_decision(scored, manifest["workflow_thresholds"])
    learner = learner_decision(scored, manifest["learner_thresholds"])
    components = component_decisions(scored)
    agent = agent_decision(scored)
    return {
        "schema": DECISION_SCHEMA,
        "experiment_id": manifest["experiment_id"],
        "status": (
            "FORMATIVE_DECISION_READY"
            if workflow["verdict"] != "NOT_RUN"
            else "NOT_RUN"
        ),
        "workflow": workflow,
        "components": components,
        "learner": learner,
        "agent": agent,
        "session_count": len(scored),
        "claim_boundary": manifest["claim_boundary"],
        "confirmatory_gate": {
            "craft_minimum_paired_participants": 12,
            "learning_minimum_participants": 32,
            "status": "DEFERRED_UNTIL_CONFIRMED_ACTIVATION_CATALOG",
        },
    }
