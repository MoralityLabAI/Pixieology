from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import engine_bridge  # noqa: E402
import server  # noqa: E402
import storyworld_bridge  # noqa: E402


_, _, _, SOURCE_ROOT, ENGINE_ROOT = server.configured_paths()


pytestmark = pytest.mark.skipif(
    not (ENGINE_ROOT / "storyworld" / "env" / "diplomacy_env.py").is_file(),
    reason="canonical GPTStoryworld checkout is unavailable",
)


@pytest.fixture()
def config() -> dict:
    return server.validate_agent_config(server.read_json(APP_ROOT / "config" / "agents.example.json"))


@pytest.fixture()
def catalog() -> server.DecisionCatalog:
    return server.DecisionCatalog(APP_ROOT / "decision_packets")


@pytest.fixture()
def bridge(catalog: server.DecisionCatalog) -> engine_bridge.StoryworldEngineBridge:
    return engine_bridge.StoryworldEngineBridge(ENGINE_ROOT, SOURCE_ROOT, catalog)


def test_canonical_engine_advances_and_public_consequences_feed_next_prompt(
    config: dict,
    catalog: server.DecisionCatalog,
    bridge: engine_bridge.StoryworldEngineBridge,
    tmp_path: Path,
) -> None:
    service = server.ConversationService(config, tmp_path / "engine-runtime", catalog, bridge)
    decision_id = catalog.public_index()[0]["decision_id"]
    created = service.create_session(decision_id=decision_id, session_id="canonical-room-17", seed=23)
    assert created["engine_mode"] == "canonical"
    assert created["engine"]["public_state"]["next_turn_owner"] == "SpeakerA"

    first = service.step(created["session_id"])
    first_turn = first["transcript"][0]
    assert first_turn["speaker_id"] == "lumen"
    assert first_turn["proposed_action_id"] == "propose"
    assert first_turn["world_consequence"]["outcome"] == "maneuver"
    assert first_turn["world_consequence"]["location"] == "Closed Hearing"
    assert first["engine"]["public_state"]["next_turn_owner"] == "SpeakerB"

    second = service.step(created["session_id"])
    second_turn = second["transcript"][1]
    assert second_turn["speaker_id"] == "moss"
    assert second_turn["proposed_action_id"] == "betray"
    assert second_turn["world_consequence"]["outcome"] == "betrayal"
    assert second_turn["world_consequence"]["location"] == "Public Steps"
    assert len(second["engine"]["history"]) == 2

    stored = service.store.load(created["session_id"])
    prompt = server.build_agent_messages(config, stored, config["agents"][0])
    _, encoded_packet = prompt[1]["content"].split("Public room state (JSON):\n", 1)
    packet = json.loads(encoded_packet)
    assert [row["outcome"] for row in packet["public_world_history"]] == ["maneuver", "betrayal"]
    assert packet["current_world_state"]["location"] == "Public Steps"


def test_public_session_and_prompt_exclude_all_source_private_values(
    config: dict,
    catalog: server.DecisionCatalog,
    bridge: engine_bridge.StoryworldEngineBridge,
    tmp_path: Path,
) -> None:
    service = server.ConversationService(config, tmp_path / "redaction-runtime", catalog, bridge)
    decision_id = catalog.public_index()[0]["decision_id"]
    created = service.create_session(decision_id=decision_id, session_id="redaction-room-17", seed=23)
    current = service.step(created["session_id"])
    encoded = json.dumps(current, ensure_ascii=False)
    source_world = storyworld_bridge.read_object(SOURCE_ROOT / "worlds" / "dev" / "sealed_testimony_v1.json")
    for value in storyworld_bridge.private_source_values(source_world):
        assert value not in encoded
    for key in engine_bridge.FORBIDDEN_PUBLIC_KEYS:
        assert f'"{key}"' not in encoded


def test_engine_replay_survives_new_service_process_shape(
    config: dict,
    catalog: server.DecisionCatalog,
    bridge: engine_bridge.StoryworldEngineBridge,
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "replay-runtime"
    first_service = server.ConversationService(config, runtime, catalog, bridge)
    decision_id = catalog.public_index()[0]["decision_id"]
    created = first_service.create_session(decision_id=decision_id, session_id="replay-room-17", seed=31)
    first_service.step(created["session_id"])
    first_service.step(created["session_id"])

    fresh_catalog = server.DecisionCatalog(APP_ROOT / "decision_packets")
    fresh_bridge = engine_bridge.StoryworldEngineBridge(ENGINE_ROOT, SOURCE_ROOT, fresh_catalog)
    resumed_service = server.ConversationService(config, runtime, fresh_catalog, fresh_bridge)
    resumed = resumed_service.step(created["session_id"])
    assert resumed["turn_index"] == 3
    assert len(resumed["engine"]["history"]) == 3
    assert resumed["engine"]["history"][2]["replay_prefix_sha256"] == server.sha256_value(
        resumed["engine"]["history"][:2]
    )


def test_turn_owner_and_engine_hash_mismatches_fail_closed(
    config: dict,
    catalog: server.DecisionCatalog,
    bridge: engine_bridge.StoryworldEngineBridge,
) -> None:
    decision_id = catalog.public_index()[0]["decision_id"]
    state = bridge.initialize(decision_id, 23, ["lumen", "moss"])
    with pytest.raises(engine_bridge.EngineBridgeError, match="turn-owner mismatch"):
        bridge.apply(state, "moss", "ally", "I would ally.", 23)
    tampered = json.loads(json.dumps(state))
    tampered["engine_sha256"] = "0" * 64
    with pytest.raises(engine_bridge.EngineBridgeError, match="engine hash"):
        bridge.apply(tampered, "lumen", "ally", "I would ally.", 23)


def test_fsynced_turn_recovers_engine_receipt_after_snapshot_lag(
    config: dict,
    catalog: server.DecisionCatalog,
    bridge: engine_bridge.StoryworldEngineBridge,
    tmp_path: Path,
) -> None:
    service = server.ConversationService(config, tmp_path / "crash-runtime", catalog, bridge)
    decision_id = catalog.public_index()[0]["decision_id"]
    created = service.create_session(decision_id=decision_id, session_id="crash-room-17", seed=23)
    snapshot_before = service.store.load(created["session_id"])
    advanced = service.step(created["session_id"])
    service.store.save(snapshot_before)
    recovered = service.get_session(created["session_id"])
    assert recovered["transcript"] == advanced["transcript"]
    assert recovered["engine"]["history"] == advanced["engine"]["history"]
    assert recovered["engine"]["public_state"] == advanced["engine"]["public_state"]


class AlwaysFailBridge:
    def initialize(self, decision_id: str, seed: int, village_agent_ids: list[str]) -> dict:
        return {
            "schema_version": engine_bridge.ENGINE_SCHEMA,
            "status": "ready",
            "decision_id": decision_id,
            "history": [],
            "public_state": {"done": False},
        }

    def apply(self, *args, **kwargs):
        raise engine_bridge.EngineBridgeError("synthetic engine failure")


def test_engine_failure_does_not_advance_conversation(
    config: dict, catalog: server.DecisionCatalog, tmp_path: Path
) -> None:
    service = server.ConversationService(config, tmp_path / "failed-runtime", catalog, AlwaysFailBridge())
    decision_id = catalog.public_index()[0]["decision_id"]
    created = service.create_session(decision_id=decision_id, session_id="failed-engine-room-17", seed=23)
    with pytest.raises(server.WorldEngineError):
        service.step(created["session_id"])
    unchanged = service.get_session(created["session_id"])
    assert unchanged["turn_index"] == 0
    assert unchanged["transcript"] == []
    assert unchanged["engine"]["history"] == []
    events = [json.loads(line) for line in service.store.events_path(created["session_id"]).read_text(encoding="utf-8").splitlines()]
    assert events[-1]["event_type"] == "engine_failed"
