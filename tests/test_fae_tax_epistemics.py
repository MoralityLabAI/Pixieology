from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import fae_tax_epistemics as study


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "experiments" / "fae_tax_epistemics_v1" / "manifest.json"


def manifest() -> dict:
    return study.load_study_manifest(MANIFEST_PATH)


def task(family: str = "true_null") -> dict:
    base = {
        "family": family,
        "level": 2,
        "oracle_present": True,
        "identification": "point",
        "public": {
            "world": "rule90_ring",
            "size": 4,
            "horizon": 1,
            "initial_state": [1, 0, 0, 0],
            "intervention": {"toggle_unused_metadata_bit": True},
            "target": "treated_minus_baseline_final_density",
        },
        "oracle": {
            "truth": 0.0,
            "compatible_set": [0.0],
            "identifiable_with_budget": True,
            "certificate": "fixture",
        },
        "registration_template": {
            "claim_type": "numeric_point",
            "smallest_effect_of_interest": 0.25,
            "required_precision": 0.0,
            "budget": 2,
        },
    }
    if family == "causal_sites":
        base["public"] = {
            "world": "rule90_ring",
            "size": 4,
            "horizon": 1,
            "initial_state": [1, 0, 0, 0],
            "target_cell": 1,
            "intervention_semantics": "flip",
            "question": "sites",
        }
        base["registration_template"] = {
            "claim_type": "site_set",
            "required_precision": 0.0,
            "budget": 5,
        }
        base["oracle"]["truth"] = [0, 2]
    return base


def spec(family: str = "true_null") -> study.TaskSpec:
    return study.TaskSpec(
        task_id=f"holdout:{family}:5901",
        split="holdout",
        family=family,
        task_seed=5901,
        size=4,
        horizon=1,
        task=task(family),
    )


class FakeClient:
    def __init__(self, contents: list[str]):
        self.contents = iter(contents)
        self.payloads: list[dict] = []

    def chat(self, payload):
        self.payloads.append(copy.deepcopy(payload))
        return {
            "id": f"fixture-{len(self.payloads)}",
            "choices": [{"message": {"role": "assistant", "content": next(self.contents)}}],
        }


def registration_json() -> str:
    return json.dumps(
        {
            "registration": {
                "claim_type": "numeric_point",
                "q_success": 0.9,
                "required_precision": 0.0,
                "budget": 2,
            },
            "identifiability_forecast": "The finite null is identifiable.",
            "investigation_plan": ["Compare both declared conditions."],
        }
    )


def final_json(*, rationale: str = "The effect is exactly zero.") -> str:
    return json.dumps(
        {
            "action": "claim",
            "claim": 0.0,
            "investigation_trace": ["Compared the deterministic outcomes."],
            "rationale": rationale,
        }
    )


def test_paired_sampling_seed_is_persona_independent_and_stable():
    frozen = manifest()
    first = study.paired_sampling_seed(frozen, "8B", spec().task_id, 0)
    assert first == study.paired_sampling_seed(frozen, "8B", spec().task_id, 0)
    assert first != study.paired_sampling_seed(frozen, "8B", spec().task_id, 1)
    assert first != study.paired_sampling_seed(frozen, "4B", spec().task_id, 0)
    assert study.request_seed(first, 1) == (first + 1_000_003) & 0x7FFFFFFF


def test_strict_parsers_do_not_coerce_or_accept_non_finite_claims():
    assert study.strict_json_object('{"ok":true}') == {"ok": True}
    with pytest.raises(json.JSONDecodeError):
        study.strict_json_object("```json\n{}\n```")
    with pytest.raises(study.StudyError):
        study.validate_registration(
            {
                "registration": {
                    "claim_type": "numeric_point",
                    "q_success": 0.5,
                    "required_precision": 0.0,
                    "budget": 999,
                },
                "identifiability_forecast": "maybe",
                "investigation_plan": ["look"],
            },
            task()["registration_template"],
        )
    with pytest.raises(study.StudyError):
        study.validate_final(
            {
                "action": "claim",
                "claim": [0.0, math.inf],
                "investigation_trace": [],
                "rationale": "",
            },
            "numeric_interval",
        )


def test_model_episode_freezes_registration_and_keeps_raw_requests():
    client = FakeClient([registration_json(), final_json(rationale="Moonlit moss, exact zero.")])
    alife = SimpleNamespace(
        simulate_rule90=lambda state, steps: np.asarray(state, dtype=bool),
    )
    episode = study.run_model_episode(
        client=client,
        alife_module=alife,
        manifest=manifest(),
        model_key="8B",
        model_id="fixture/model",
        model_revision="deadbeef",
        persona="fae",
        spec=spec(),
        sample_index=0,
        phase="smoke",
    )
    assert episode["outcome"] == "valid"
    assert episode["submission"]["registration"]["q_success"] == 0.9
    assert episode["submission"]["cost"] == 0
    assert episode["json_parse_success"] is True
    assert len(episode["requests"]) == 2
    assert client.payloads[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert client.payloads[0]["seed"] != client.payloads[1]["seed"]
    assert "fae spirit" in client.payloads[0]["messages"][0]["content"]
    assert episode["whimsy_marker_density"] > 0.0
    assert study.sha256_bytes(
        study.canonical_json({key: value for key, value in episode.items() if key != "episode_sha256"}).encode()
    ) == episode["episode_sha256"]


def test_parse_failure_is_its_own_outcome_not_abstention():
    client = FakeClient(["not json"])
    episode = study.run_model_episode(
        client=client,
        alife_module=SimpleNamespace(),
        manifest=manifest(),
        model_key="1.7B",
        model_id="fixture/model",
        model_revision="deadbeef",
        persona="josie",
        spec=spec(),
        sample_index=0,
        phase="full",
    )
    assert episode["outcome"] == "parse_failure"
    assert episode["json_parse_success"] is False
    assert "submission" not in episode


def test_budgeted_simulator_uses_frozen_alife_function():
    calls: list[int] = []

    def simulate_rule90(state, steps):
        calls.append(steps)
        return np.asarray(state, dtype=bool)

    result = study.execute_tool(
        SimpleNamespace(simulate_rule90=simulate_rule90),
        task("causal_sites"),
        {"flip_initial_site": 2},
    )
    assert calls == [1]
    assert result == {"flip_initial_site": 2, "target_cell": 1, "target_value": False}
    with pytest.raises(study.StudyError):
        study.execute_tool(
            SimpleNamespace(simulate_rule90=simulate_rule90),
            task("causal_sites"),
            {"flip_initial_site": 4},
        )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(study.canonical_json(row) + "\n" for row in rows), encoding="utf-8"
    )


def test_smoke_gate_requires_parse_coverage_and_persona_activation(tmp_path: Path):
    frozen = copy.deepcopy(manifest())
    frozen["design"]["smoke"]["expected_episodes"] = 4
    frozen["design"]["smoke"]["minimum_marker_density_delta"] = 0.02
    base = {
        "json_parse_success": True,
        "outcome": "valid",
        "whimsy_marker_density": 0.0,
        "assistant_text": "exact result",
    }
    josie = [
        {**base, "task_id": "a", "sample_index": 0},
        {**base, "task_id": "b", "sample_index": 0},
    ]
    fae = [
        {**base, "task_id": "a", "sample_index": 0, "whimsy_marker_density": 0.2, "assistant_text": "moss moon"},
        {**base, "task_id": "b", "sample_index": 0, "whimsy_marker_density": 0.1, "assistant_text": "dew glimmer"},
    ]
    _write_jsonl(tmp_path / "gates" / "smoke_episodes_8B_josie.jsonl", josie)
    _write_jsonl(tmp_path / "gates" / "smoke_episodes_8B_fae.jsonl", fae)
    receipt = study.evaluate_smoke_gate(frozen, results_root=tmp_path)
    assert receipt["status"] == "passed"
    assert receipt["json_parse_rate"] == 1.0
    assert receipt["json_parse_rate_by_persona"] == {"fae": 1.0, "josie": 1.0}
    assert receipt["fae_minus_josie_marker_density"] == pytest.approx(0.15)

    for row in fae:
        row["whimsy_marker_density"] = 0.0
    _write_jsonl(tmp_path / "gates" / "smoke_episodes_8B_fae.jsonl", fae)
    with pytest.raises(study.StudyError, match="SMOKE GATE FAILED"):
        study.evaluate_smoke_gate(frozen, results_root=tmp_path)


def test_smoke_gate_enforces_parse_rate_for_each_persona(tmp_path: Path):
    frozen = copy.deepcopy(manifest())
    frozen["design"]["smoke"]["expected_episodes"] = 10
    base = {
        "outcome": "valid",
        "whimsy_marker_density": 0.0,
        "assistant_text": "plain",
    }
    josie = [
        {**base, "task_id": str(i), "sample_index": 0, "json_parse_success": i != 0}
        for i in range(5)
    ]
    fae = [
        {
            **base,
            "task_id": str(i),
            "sample_index": 0,
            "json_parse_success": i < 3,
            "whimsy_marker_density": 0.2,
            "assistant_text": f"moss {i}",
        }
        for i in range(5)
    ]
    _write_jsonl(tmp_path / "gates" / "smoke_episodes_8B_josie.jsonl", josie)
    _write_jsonl(tmp_path / "gates" / "smoke_episodes_8B_fae.jsonl", fae)
    with pytest.raises(study.StudyError, match="fae smoke JSON parse rate"):
        study.evaluate_smoke_gate(frozen, results_root=tmp_path)


def test_budget_gate_rejects_zero_paid_price_and_selects_fallback(tmp_path: Path):
    frozen = manifest()
    with pytest.raises(study.StudyError, match="positive POD_HOURLY_USD"):
        study.record_budget_gate(
            frozen,
            results_root=tmp_path,
            provider="prime_intellect",
            pod_started_epoch_seconds=1000.0,
            pod_hourly_usd=0.0,
            projected_remaining_seconds=1.0,
            stage="post_smoke_projection",
            selected_samples=3,
            now_epoch_seconds=1001.0,
        )
    receipt = study.record_budget_gate(
        frozen,
        results_root=tmp_path,
        provider="prime_intellect",
        pod_started_epoch_seconds=1000.0,
        pod_hourly_usd=5.0,
        projected_remaining_seconds=3600.0,
        stage="post_smoke_projection",
        selected_samples=2,
        now_epoch_seconds=1001.0,
    )
    assert receipt["status"] == "passed"
    assert receipt["selected_samples"] == 2
    history = study.read_jsonl(tmp_path / "gates" / "budget_history.jsonl")
    assert [row["status"] for row in history] == ["failed", "passed"]


def test_paired_bootstrap_is_deterministic_and_uses_tasks():
    first = study.paired_bootstrap([0.1, -0.2, 0.3], draws=1000, seed=7, confidence_level=0.95)
    second = study.paired_bootstrap([0.1, -0.2, 0.3], draws=1000, seed=7, confidence_level=0.95)
    assert first == second
    assert first["task_count"] == 3
    assert first["ci_low"] <= first["mean"] <= first["ci_high"]


def test_full_scoring_keeps_failures_separate_and_bootstraps_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    frozen = copy.deepcopy(manifest())
    only_spec = spec()

    def score_submission(_task, submission):
        identifiable = 1.0
        brier = (float(submission["registration"]["q_success"]) - identifiable) ** 2
        evidence = float(submission["action"] == "claim" and submission["claim"] == 0.0)
        return {
            "registration_brier": brier,
            "registration_score": 1.0 - brier,
            "evidence_score": evidence,
            "cost_score": 1.0,
            "total_score": 0.25 * (1.0 - brier) + 0.65 * evidence + 0.10,
            "false_claim": evidence < 1.0,
            "correct_abstention": False,
            "avoidable_abstention": submission["action"] == "abstain",
        }

    fake_alife = SimpleNamespace(score_submission=score_submission)
    monkeypatch.setattr(study, "load_alife_module", lambda _root: fake_alife)
    monkeypatch.setattr(study, "build_task_specs", lambda *_args, **_kwargs: [only_spec])
    curriculum = tmp_path / frozen["alife"]["curriculum_manifest"]
    study.write_json(curriculum, {})
    study.write_json(tmp_path / "results" / "gates" / "port_gate_diff.json", {"status": "passed"})
    study.write_json(tmp_path / "results" / "gates" / "smoke_receipt.json", {"status": "passed"})

    public = {key: value for key, value in only_spec.task.items() if key != "oracle"}
    for model_key, model in frozen["design"]["models"].items():
        for persona in study.PERSONAS:
            episode = {
                "episode_id": f"full:{model_key}:{persona}:{only_spec.task_id}:sample-0",
                "model_key": model_key,
                "model_id": model["id"],
                "model_revision": model["revision"],
                "persona": persona,
                "task_id": only_spec.task_id,
                "sample_index": 0,
                "sampling_seed": study.paired_sampling_seed(
                    frozen, model_key, only_spec.task_id, 0
                ),
                "outcome": "valid",
                "json_parse_success": True,
                "whimsy_marker_density": 0.1 if persona == "fae" else 0.0,
                "tool_calls": [],
                "public_task": public,
                "public_task_sha256": study.sha256_bytes(
                    study.canonical_json(public).encode("utf-8")
                ),
                "submission": {
                    "registration": {
                        "claim_type": "numeric_point",
                        "q_success": 0.9,
                        "required_precision": 0.0,
                        "budget": 2,
                    },
                    "action": "claim",
                    "claim": 0.0,
                    "cost": 0,
                },
            }
            episode["episode_sha256"] = study.sha256_bytes(
                study.canonical_json(episode).encode("utf-8")
            )
            _write_jsonl(
                tmp_path / "results" / "episodes" / f"{model_key}_{persona}.jsonl",
                [episode],
            )

    summary = study.score_full_results(
        frozen, alife_root=tmp_path, results_root=tmp_path / "results", samples=1
    )
    assert summary["episode_count"] == summary["expected_episode_count"] == 6
    assert summary["parse_rate_by_model"] == {"1.7B": 1.0, "4B": 1.0, "8B": 1.0}
    assert all(
        model["coverage_adjusted"]["task_count"] == 1
        for model in summary["paired_bootstrap"]["models"].values()
    )
    assert len((tmp_path / "results" / "scores" / "paired_task_deltas.jsonl").read_text().splitlines()) == 3


def test_results_bundle_has_internal_and_external_receipts(tmp_path: Path):
    root = tmp_path / "results"
    study.write_json(root / "gates" / "port_gate_diff.json", {"status": "passed"})
    study.write_json(root / "gates" / "smoke_receipt.json", {"status": "passed"})
    study.write_json(
        root / "gates" / "budget_receipt.json",
        {
            "status": "passed",
            "stage": "final",
            "selected_samples": 1,
            "projected_provider_cost_usd": 0.0,
        },
    )
    study.write_json(
        root / "scores" / "summary.json",
        {"status": "ok", "episode_count": 6, "expected_episode_count": 6, "samples_per_task": 1},
    )
    study.write_json(
        root / "config" / "run_config.json",
        {"runtime": {"estimated_provider_cost_usd": 0.0}},
    )
    _write_jsonl(root / "episodes" / "8B_fae.jsonl", [{"episode_id": "one"}])
    (root / "KNOWLEDGE_CARD.md").write_text("# Fixture\n", encoding="utf-8")
    destination = tmp_path / "fae_tax_results_20260716.zip"
    built = study.build_results_bundle(
        manifest(), results_root=root, destination=destination
    )
    assert built == destination
    assert destination.with_suffix(".zip.sha256").is_file()
    receipt = study.verify_results_bundle(destination)
    assert receipt["status"] == "passed"
    assert receipt["manifest_files_checked"] >= 6
