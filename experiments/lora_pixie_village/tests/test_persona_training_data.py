from __future__ import annotations

import json
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
TRAINING_ROOT = APP_ROOT / "persona_training"
for path in (APP_ROOT, TRAINING_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_persona_data  # noqa: E402
import persona_canary_eval  # noqa: E402
import server  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_frozen_persona_data_is_disjoint_nested_and_neutral(tmp_path: Path) -> None:
    output = tmp_path / "persona-data"
    manifest = build_persona_data.build(output)
    assert manifest["status"] == "PASS"
    assert manifest["global_record_id_count"] == 128
    all_ids = set()
    for persona_id, marker, forbidden in (
        ("lumen", "lanternwise", "rootward"),
        ("moss", "rootward", "lanternwise"),
    ):
        train = load_jsonl(output / persona_id / "smoke_train.jsonl")
        evaluation = load_jsonl(output / persona_id / "smoke_eval.jsonl")
        assert len(train) == 48
        assert len(evaluation) == 16
        assert {row["kind"] for row in evaluation} == {"canary", "style"}
        assert all(row["messages"][0]["content"] == build_persona_data.NEUTRAL_SYSTEM for row in train + evaluation)
        prompts_train = {build_persona_data.normalize_prompt(row["messages"][1]["content"]) for row in train}
        prompts_eval = {build_persona_data.normalize_prompt(row["messages"][1]["content"]) for row in evaluation}
        assert prompts_train.isdisjoint(prompts_eval)
        style_outputs = [row["messages"][2]["content"].casefold() for row in train if row["kind"] == "style"]
        assert all(marker in value and forbidden not in value for value in style_outputs)
        ids = {row["id"] for row in train + evaluation}
        assert all_ids.isdisjoint(ids)
        all_ids.update(ids)
    assert len(all_ids) == 128


def test_generated_canaries_validate_against_two_resident_config(tmp_path: Path) -> None:
    output = tmp_path / "persona-data"
    build_persona_data.build(output)
    config = server.read_json(APP_ROOT / "config" / "agents.example.json")
    spec = server.read_json(output / "persona_canaries.json")
    normalized = persona_canary_eval.validate_canary_spec(spec, server.validate_agent_config(config))
    assert len(normalized["agents"]) == 2
    assert all(len(row["probes"]) == 16 for row in normalized["agents"])
    markers = {marker for row in normalized["agents"] for marker in row["unique_markers"]}
    assert markers == {"LUMEN_LANTERN_OK_17", "lanternwise", "MOSS_ROOT_OK_29", "rootward"}
