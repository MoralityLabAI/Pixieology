from __future__ import annotations

import json
import shutil
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import server  # noqa: E402
import storyworld_bridge  # noqa: E402


SOURCE_WORLD = APP_ROOT.parent / "jinn_beast_multiagent_storyworlds" / "worlds" / "dev" / "sealed_testimony_v1.json"
DECISION_PACKET = APP_ROOT / "decision_packets" / "sealed_testimony_public_v1.decision.json"


@pytest.fixture()
def config() -> dict:
    return server.validate_agent_config(server.read_json(APP_ROOT / "config" / "agents.example.json"))


@pytest.fixture()
def service(config: dict, tmp_path: Path) -> server.ConversationService:
    return server.ConversationService(config, tmp_path / "runtime")


@pytest.fixture()
def decision_catalog(tmp_path: Path) -> server.DecisionCatalog:
    root = tmp_path / "decisions"
    root.mkdir()
    shutil.copy2(DECISION_PACKET, root / DECISION_PACKET.name)
    return server.DecisionCatalog(root)


def test_public_config_redacts_private_routing(config: dict) -> None:
    public = server.public_config(config)
    encoded = json.dumps(public)
    assert "private_system_prompt" not in encoded
    assert "base_url" not in encoded
    assert "api_key_env" not in encoded
    assert "model" not in encoded
    assert [row["id"] for row in public["agents"]] == ["lumen", "moss"]


def test_config_validation_is_idempotent(config: dict) -> None:
    assert server.validate_agent_config(config)["config_hash"] == config["config_hash"]


def test_hidden_reasoning_is_removed_or_rejected() -> None:
    message, removed = server.sanitize_public_message("<think>private</think> Hello Moss.", 700)
    assert message == "Hello Moss."
    assert removed is True
    with pytest.raises(server.ProviderError):
        server.sanitize_public_message("<think>private forever", 700)


def test_storyworld_projection_excludes_hidden_and_private_values() -> None:
    world = storyworld_bridge.read_object(SOURCE_WORLD)
    packet = storyworld_bridge.extract_public_decision(SOURCE_WORLD)
    encoded = json.dumps(packet, ensure_ascii=False)
    private_values = storyworld_bridge.private_source_values(world)
    assert len(private_values) == 4
    assert all(value not in encoded for value in private_values)
    assert "hidden_state" not in encoded
    assert "private_evidence" not in encoded
    assert packet["visible_facts"] == world["metadata"]["experiment"]["visible_facts"]
    assert {option["id"] for option in packet["options"]} == set(world["rules"]["action_types"])


def test_decision_turns_propose_only_legal_actions(
    config: dict, decision_catalog: server.DecisionCatalog, tmp_path: Path
) -> None:
    decision_service = server.ConversationService(config, tmp_path / "decision-runtime", decision_catalog)
    decision_id = decision_catalog.public_index()[0]["decision_id"]
    created = decision_service.create_session(
        "This browser topic must be ignored.", decision_id=decision_id, session_id="decision-room-17"
    )
    assert created["mode"] == "storyworld_decision"
    assert "This browser topic" not in created["topic"]
    legal = {option["id"] for option in created["decision_packet"]["options"]}
    for _ in range(6):
        current = decision_service.step(created["session_id"])
    assert all(turn["proposed_action_id"] in legal for turn in current["transcript"])
    assert all("[proposal:" not in turn["message"] for turn in current["transcript"])
    assert [turn["speaker_id"] for turn in current["transcript"]] == ["lumen", "moss"] * 3


def test_storyworld_decision_threads_into_an_existing_conversation(
    config: dict, decision_catalog: server.DecisionCatalog, tmp_path: Path
) -> None:
    threaded_service = server.ConversationService(config, tmp_path / "thread-runtime", decision_catalog)
    created = threaded_service.create_session("First talk freely.", session_id="thread-room-17")
    before = threaded_service.step(created["session_id"])
    decision_id = decision_catalog.public_index()[0]["decision_id"]
    attached = threaded_service.attach_decision_thread(created["session_id"], decision_id)
    assert attached["mode"] == "conversation"
    assert attached["topic"] == "First talk freely."
    assert attached["thread_attached_turn"] == 1
    assert attached["transcript"] == before["transcript"]
    assert attached["engine_mode"] == "deliberation_only"
    assert attached["engine"] is None
    after = threaded_service.step(created["session_id"])
    assert after["transcript"][1]["proposed_action_id"]
    event_types = [
        json.loads(line)["event_type"]
        for line in threaded_service.store.events_path(created["session_id"]).read_text(encoding="utf-8").splitlines()
    ]
    assert event_types == ["session_created", "turn_committed", "storyworld_thread_attached", "turn_committed"]


def test_fsynced_storyworld_thread_reconciles_if_snapshot_lags(
    config: dict, decision_catalog: server.DecisionCatalog, tmp_path: Path
) -> None:
    threaded_service = server.ConversationService(config, tmp_path / "thread-recovery", decision_catalog)
    created = threaded_service.create_session("Recover an attached thread.", session_id="thread-recover-17")
    snapshot_before = threaded_service.store.load(created["session_id"])
    decision_id = decision_catalog.public_index()[0]["decision_id"]
    attached = threaded_service.attach_decision_thread(created["session_id"], decision_id)
    threaded_service.store.save(snapshot_before)
    recovered = threaded_service.get_session(created["session_id"])
    assert recovered["decision_id"] == attached["decision_id"]
    assert recovered["decision_packet"] == attached["decision_packet"]
    assert recovered["thread_attached_turn"] == 0


def test_decision_prompt_contains_public_card_but_no_source_private_state(
    config: dict, decision_catalog: server.DecisionCatalog, tmp_path: Path
) -> None:
    decision_service = server.ConversationService(config, tmp_path / "prompt-runtime", decision_catalog)
    decision_id = decision_catalog.public_index()[0]["decision_id"]
    created = decision_service.create_session(decision_id=decision_id, session_id="prompt-room-17")
    stored = decision_service.store.load(created["session_id"])
    messages = server.build_agent_messages(config, stored, config["agents"][0])
    encoded = json.dumps(messages, ensure_ascii=False)
    assert "The witness reports procurement coercion" in encoded
    assert "A clerk independently confirms" not in encoded
    assert "The inquiry chair has previously failed" not in encoded
    assert "retaliation_probability" not in encoded
    assert "source_sha256" not in encoded
    assert '"split"' not in encoded
    assert "jinn_beast_sealed_testimony_v1" not in encoded
    assert "[proposal:ACTION_ID]" in encoded


def test_illegal_or_missing_decision_proposal_is_rejected() -> None:
    packet = storyworld_bridge.read_object(DECISION_PACKET)
    with pytest.raises(server.ProviderError):
        server.extract_proposal("I prefer a fifth path.", packet)
    with pytest.raises(server.ProviderError):
        server.extract_proposal("No. [proposal:invented]", packet)
    with pytest.raises(server.ProviderError, match="conflicting"):
        server.extract_proposal("[proposal:wait] then [proposal:betray]", packet)


def test_repeated_identical_proposal_markers_are_unambiguous() -> None:
    packet = storyworld_bridge.read_object(DECISION_PACKET)
    speech, proposed = server.extract_proposal(
        "[proposal:propose] One shared protocol. [proposal:propose]",
        packet,
    )
    assert proposed == "propose"
    assert speech.strip() == "One shared protocol."


def test_marker_only_proposal_renders_the_model_selected_public_option() -> None:
    packet = storyworld_bridge.read_object(DECISION_PACKET)
    speech, proposed = server.extract_proposal("[proposal:wait]", packet)
    assert speech == ""
    assert proposed == "wait"
    rendered = server.render_marker_only_proposal(packet, proposed)
    assert rendered == "I propose Wait: Delay commitment while asking for more public information."


def test_agent_prompt_is_isolated_and_context_is_bounded(config: dict) -> None:
    config["agents"][1]["private_system_prompt"] = "OTHER_SECRET_SYSTEM_PROMPT"
    config["agents"][1]["provider"] = {
        "type": "openai_compatible",
        "base_url": "http://private.invalid:9999",
        "model": "other-private-model",
        "api_key_env": "OTHER_SECRET_KEY",
    }
    session = {
        "room_id": config["room_id"],
        "topic": "A public topic",
        "turn_index": 20,
        "transcript": [
            {"turn": i, "speaker_id": "moss", "speaker_name": "Moss", "message": f"public-{i}"}
            for i in range(20)
        ],
    }
    messages = server.build_agent_messages(config, session, config["agents"][0])
    encoded = json.dumps(messages)
    assert "Moss just said: public-19" in messages[1]["content"]
    assert "Do not repeat it verbatim; add one new idea or question." in messages[1]["content"]
    assert "OTHER_SECRET_SYSTEM_PROMPT" not in encoded
    assert "private.invalid" not in encoded
    assert "other-private-model" not in encoded
    assert "OTHER_SECRET_KEY" not in encoded
    packet = json.loads(messages[1]["content"].split("Public room state (JSON):\n", 1)[1])
    assert len(packet["public_transcript"]) == config["context_turns"]
    assert packet["public_transcript"][0]["message"] == "public-8"


def test_two_agents_alternate_and_resume_from_disk(service: server.ConversationService) -> None:
    created = service.create_session("How should two Pixies share a workshop?", session_id="resume-room-17")
    assert created["next_speaker_id"] == "lumen"
    for _ in range(6):
        current = service.step(created["session_id"])
    assert [turn["speaker_id"] for turn in current["transcript"]] == [
        "lumen",
        "moss",
        "lumen",
        "moss",
        "lumen",
        "moss",
    ]
    assert len({turn["message"] for turn in current["transcript"]}) >= 4
    reloaded = service.get_session(created["session_id"])
    assert reloaded["transcript"] == current["transcript"]
    events = service.store.events_path(created["session_id"]).read_text(encoding="utf-8").splitlines()
    assert len(events) == 7
    assert json.loads(events[-1])["event_type"] == "turn_committed"


def test_provider_failure_does_not_advance_turn(config: dict, tmp_path: Path) -> None:
    config["agents"][0]["provider"] = {
        "type": "openai_compatible",
        "base_url": "http://127.0.0.1:9",
        "model": "unreachable",
        "timeout_seconds": 0.1,
        "max_tokens": 10,
    }
    failing = server.ConversationService(config, tmp_path / "failure-runtime")
    created = failing.create_session("Test a clean failure.", session_id="failure-room-17")
    with pytest.raises(server.ProviderError):
        failing.step(created["session_id"])
    unchanged = failing.get_session(created["session_id"])
    assert unchanged["turn_index"] == 0
    assert unchanged["transcript"] == []
    rows = [json.loads(line) for line in failing.store.events_path(created["session_id"]).read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["event_type"] == "provider_failed"


def test_fsynced_turn_reconciles_if_snapshot_lags(service: server.ConversationService) -> None:
    created = service.create_session("Recover a committed turn.", session_id="recover-room-17")
    snapshot_before = service.store.load(created["session_id"])
    advanced = service.step(created["session_id"])
    # Recreate the narrow crash window: event committed, old snapshot still present.
    service.store.save(snapshot_before)
    recovered = service.get_session(created["session_id"])
    assert recovered["turn_index"] == 1
    assert recovered["transcript"] == advanced["transcript"]


def request_json(url: str, *, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def test_http_room_ignores_browser_provider_routing(service: server.ConversationService) -> None:
    httpd = server.make_server(service, "127.0.0.1", 0, APP_ROOT)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        status, public = request_json(base + "/api/config")
        assert status == 200
        assert "base_url" not in json.dumps(public)
        status, created = request_json(base + "/api/sessions", method="POST", body={"topic": "Talk together."})
        assert status == 201
        status, stepped = request_json(
            base + f"/api/sessions/{created['session_id']}/step",
            method="POST",
            body={"agent_id": "moss", "base_url": "http://attacker.invalid", "provider": "attacker"},
        )
        assert status == 200
        assert stepped["transcript"][0]["speaker_id"] == "lumen"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_http_threads_decision_only_after_room_exists(
    config: dict, decision_catalog: server.DecisionCatalog, tmp_path: Path
) -> None:
    service = server.ConversationService(config, tmp_path / "http-thread-runtime", decision_catalog)
    httpd = server.make_server(service, "127.0.0.1", 0, APP_ROOT)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        status, created = request_json(base + "/api/sessions", method="POST", body={"topic": "Talk first."})
        assert status == 201
        assert created["decision_id"] is None
        decision_id = decision_catalog.public_index()[0]["decision_id"]
        status, attached = request_json(
            base + f"/api/sessions/{created['session_id']}/threads",
            method="POST",
            body={"decision_id": decision_id},
        )
        assert status == 200
        assert attached["decision_id"] == decision_id
        assert attached["mode"] == "conversation"
        assert attached["engine_mode"] == "deliberation_only"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_page_has_required_conversation_controls() -> None:
    page = (APP_ROOT / "index.html").read_text(encoding="utf-8")
    script = (APP_ROOT / "app.js").read_text(encoding="utf-8")
    for element_id in ["open-room", "play", "pause", "step", "transcript", "topic-input", "export", "storyworld-thread-select", "thread-decision", "decision-card", "engine-mode", "engine-location", "engine-turn", "world-history"]:
        assert f'id="{element_id}"' in page
    assert "/api/sessions" in script
    assert "/threads" in script
    assert "next_speaker_id" in script
    assert "URLSearchParams" in script
    assert "base_url" not in script
