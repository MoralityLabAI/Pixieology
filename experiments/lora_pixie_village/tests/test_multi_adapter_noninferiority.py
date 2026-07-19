from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import multi_adapter_noninferiority as study  # noqa: E402


PROTOCOL_PATH = APP_ROOT / "config" / "multi_adapter_noninferiority_v1.json"


def test_protocol_is_frozen_and_generation_plan_is_complete() -> None:
    protocol = study.load_protocol(PROTOCOL_PATH)
    plan = study.generation_plan(protocol)
    assert len(plan) == 44
    assert sum(row["suite"] == "companion" for row in plan) == 16
    assert sum(row["suite"] == "action" for row in plan) == 16
    assert sum(row["suite"] == "joint" for row in plan) == 12
    assert len({(row["suite"], row["probe"]["probe_id"], row["condition_id"]) for row in plan}) == 44


def test_protocol_rejects_posthoc_margin_or_duplicate_prompt() -> None:
    protocol = study.load_protocol(PROTOCOL_PATH)
    changed = copy.deepcopy(protocol)
    changed["noninferiority_margin"] = 0.1
    with pytest.raises(study.NoninferiorityError, match="exactly 0.05"):
        study.validate_protocol(changed)
    changed = copy.deepcopy(protocol)
    changed["companion_probes"][1]["prompt"] = changed["companion_probes"][0]["prompt"]
    with pytest.raises(study.NoninferiorityError, match="disjoint"):
        study.validate_protocol(changed)
    changed = copy.deepcopy(protocol)
    changed["decoding"]["temperature"] = 0.2
    with pytest.raises(study.NoninferiorityError, match="decoding"):
        study.validate_protocol(changed)


def test_action_and_companion_parts_are_scored_separately() -> None:
    action = "(buy Lyra Oren Seed Pearl)"
    content = "Let's inspect one receipt first.\n" + action
    assert study.final_action(content) == action
    assert study.companion_text(content, action) == "Let's inspect one receipt first."
    assert study.companion_text(action, action) == ""


def test_generation_checkpoint_must_be_an_exact_hashed_plan_prefix(tmp_path: Path) -> None:
    protocol = study.load_protocol(PROTOCOL_PATH)
    first = study.generation_plan(protocol)[0]
    content = "A bounded answer."
    row = {
        "schema_version": "pixie_multi_adapter_noninferiority_generation_v1",
        "protocol_id": protocol["protocol_id"],
        "suite": first["suite"],
        "probe_id": first["probe"]["probe_id"],
        "condition_id": first["condition_id"],
        "content": content,
        "content_sha256": study.server.sha256_value(content),
    }
    path = tmp_path / "raw.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert study.read_generation_rows(path, protocol) == [row]
    row["condition_id"] = "stacked"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(study.NoninferiorityError, match="plan prefix"):
        study.read_generation_rows(path, protocol)


def test_paired_stratified_bootstrap_is_deterministic() -> None:
    rows = []
    for index, (reference, stacked) in enumerate([(0.6, 0.6), (0.7, 0.72), (0.8, 0.79), (0.9, 0.91)]):
        for condition, score in (("companion", reference), ("stacked", stacked)):
            rows.append(
                {
                    "probe_id": f"p{index}",
                    "family": "a" if index < 2 else "b",
                    "condition_id": condition,
                    "score": score,
                }
            )
    first = study.paired_stratified_bootstrap(
        rows, reference="companion", stacked="stacked", resamples=10000, seed=1701
    )
    second = study.paired_stratified_bootstrap(
        rows, reference="companion", stacked="stacked", resamples=10000, seed=1701
    )
    assert first == second
    assert first["n_pairs"] == 4
    assert first["point_difference"] == pytest.approx(0.005)


def test_analysis_classifies_pass_fail_and_inconclusive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    protocol = study.load_protocol(PROTOCOL_PATH)
    rows = []
    semantic = {}
    for item in study.generation_plan(protocol):
        probe = item["probe"]
        expected = probe.get("expected_action")
        row = {
            "suite": item["suite"],
            "family": probe["family"],
            "probe_id": probe["probe_id"],
            "condition_id": item["condition_id"],
            "action_exact": bool(expected),
            "semantic_reference": study.reference_text(probe["rubric"]) if "rubric" in probe else None,
        }
        rows.append(row)
        if "rubric" in probe and item["condition_id"] in {"companion", "stacked"}:
            semantic[(item["suite"], probe["probe_id"], item["condition_id"])] = 0.8

    monkeypatch.setattr(
        study,
        "cosine_semantic_scores",
        lambda rows, protocol, hf_home: (semantic, {"semantic_rows": len(semantic)}),
    )
    passed = study.analyze(rows, protocol, tmp_path)
    assert passed["verdict"] == "PASS"

    for key in list(semantic):
        if key[0] == "companion" and key[2] == "stacked":
            semantic[key] = 0.7
    failed = study.analyze(rows, protocol, tmp_path)
    assert failed["verdict"] == "FAIL"
