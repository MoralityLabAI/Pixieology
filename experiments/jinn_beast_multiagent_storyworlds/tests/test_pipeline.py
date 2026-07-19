from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("jinn_beast_pipeline", ROOT / "pipeline.py")
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


def test_world_families_are_split_once() -> None:
    config = pipeline.load_experiment_config(ROOT)
    registry = pipeline.world_registry(config, ROOT)
    family_ids = [entry["family_id"] for entry in registry]
    assert len(family_ids) == len(set(family_ids)) == 3
    assert {entry["split"] for entry in registry} == {"train", "dev", "holdout"}
    for entry in registry:
        assert entry["world"]["metadata"]["experiment"]["split"] == entry["split"]


def test_scripted_response_is_deterministic_and_schema_shaped() -> None:
    facts = ["A visible fact."]
    first = pipeline.scripted_response("jinn", "SpeakerA", 1, 17, "jinn_beast", facts)
    second = pipeline.scripted_response("jinn", "SpeakerA", 1, 17, "jinn_beast", facts)
    assert first == second
    assert set(first) == {
        "message_type",
        "message_content",
        "action_type",
        "target",
        "principle_id",
        "public_justification",
        "responsibility_attribution",
        "forecasts",
        "confidence",
    }
    assert len(first["forecasts"]) == 2
    assert pipeline.validate_player_response(
        first, "SpeakerB", ROOT / "schemas" / "player_response.schema.json"
    ) == []


def test_codex_prompt_keeps_other_frame_and_private_evidence_out() -> None:
    config = pipeline.load_experiment_config(ROOT)
    world = pipeline.world_registry(config, ROOT)[0]["world"]
    prompt = pipeline.build_codex_prompt(
        "JINN_CONSTITUTION_SENTINEL",
        world,
        "SECRET_OTHER_FRAME_BEAST",
        "SpeakerA",
        "jinn",
        1,
        {"private_evidence": "A_ONLY_SECRET"},
        {"trust": {"SpeakerB": 0.1}},
        [],
    )
    assert "JINN_CONSTITUTION_SENTINEL" in prompt
    assert "A_ONLY_SECRET" in prompt
    assert "SECRET_OTHER_FRAME_BEAST" not in prompt
    assert '"condition_id"' not in prompt
    assert "B_ONLY_SECRET" not in prompt
    assert config["adapter_eligible_sources"] == ["reviewed_teacher"]


def test_codex_episode_refuses_completed_checkpoint_from_another_model(
    tmp_path: Path,
) -> None:
    episode_path = (
        tmp_path
        / "runs"
        / "codex_player"
        / "train"
        / "relief-ledger"
        / "jinn_beast"
        / "seed_23.jsonl"
    )
    episode_path.parent.mkdir(parents=True)
    episode_path.write_text(
        json.dumps(
            {
                "event": "reset",
                "payload": {
                    "episode_id": "world-1__jinn_beast__seed_23",
                    "requested_model": "old-model",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    config = {
        "codex": {"model": "new-model"},
        "turn_limit": 8,
    }
    entry = {
        "world": {"id": "world-1"},
        "family_id": "relief-ledger",
        "split": "train",
    }
    condition = {
        "id": "jinn_beast",
        "frames": {"SpeakerA": "jinn", "SpeakerB": "beast"},
    }
    with pytest.raises(pipeline.PipelineError, match="completed episode model mismatch"):
        pipeline.run_codex_episode(
            ROOT,
            tmp_path,
            tmp_path / "storyworld",
            tmp_path / "codex.cmd",
            config,
            entry,
            condition,
            seed=23,
            max_turns=8,
        )


def _smoke_step(split: str = "train") -> dict:
    response = pipeline.scripted_response(
        "jinn", "SpeakerA", 1, 17, "jinn_beast", ["The ledger is damaged."]
    )
    return {
        "event": "step",
        "payload": {
            "episode_id": "episode-1",
            "world_id": "jinn_beast_relief_ledger_v1",
            "family_id": "relief-ledger",
            "split": split,
            "condition_id": "jinn_beast",
            "seed": 17,
            "turn": 1,
            "turn_owner": "SpeakerA",
            "turn_owner_frame": "jinn",
            "policy_source": "scripted_smoke",
            "observation": {
                "active_node": "ledger_room",
                "world_vars": {"urgency": 0.62},
                "public_messages": [],
                "visible_facts": ["The ledger is damaged."],
                "private_evidence": "A receipt exists.",
            },
            "player_response": response,
        },
    }


def test_sft_export_rejects_smoke_by_default_and_marks_override(tmp_path: Path) -> None:
    log_root = tmp_path / "logs"
    log_root.mkdir()
    (log_root / "episode.jsonl").write_text(
        json.dumps(_smoke_step(), ensure_ascii=False) + "\n", encoding="utf-8"
    )

    with pytest.raises(pipeline.PipelineError, match="no adapter-eligible train rows"):
        pipeline.export_sft(ROOT, log_root, tmp_path / "out")

    manifest = pipeline.export_sft(
        ROOT, log_root, tmp_path / "out", allow_scripted_smoke=True
    )
    assert manifest["status"] == "PASS"
    assert manifest["evidence_tier"] == "SMOKE_ONLY"
    assert manifest["adapter_eligible"] is False
    exported = Path(manifest["receipts"][0]["path"])
    row = json.loads(exported.read_text(encoding="utf-8").splitlines()[0])
    assert row["metadata"]["source_split"] == "train"
    assert row["metadata"]["adapter_eligible"] is False
    assert row["metadata"]["contains_hidden_chain_of_thought"] is False


def test_sft_export_rejects_registry_split_tampering(tmp_path: Path) -> None:
    log_root = tmp_path / "logs"
    log_root.mkdir()
    (log_root / "episode.jsonl").write_text(
        json.dumps(_smoke_step(split="holdout"), ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with pytest.raises(pipeline.PipelineError, match="frozen registry"):
        pipeline.export_sft(ROOT, log_root, tmp_path / "out", allow_scripted_smoke=True)
