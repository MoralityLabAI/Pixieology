#!/usr/bin/env python3
"""Prove that free conversation precedes an optional Storyworld thread."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import server  # noqa: E402
import storyworld_bridge  # noqa: E402


def main() -> int:
    config = server.validate_agent_config(server.read_json(APP_ROOT / "config" / "agents.example.json"))
    catalog = server.DecisionCatalog(APP_ROOT / "decision_packets")
    decision_id = catalog.public_index()[0]["decision_id"]
    source_world = APP_ROOT.parent / "jinn_beast_multiagent_storyworlds" / "worlds" / "dev" / "sealed_testimony_v1.json"
    private_values = storyworld_bridge.private_source_values(storyworld_bridge.read_object(source_world))
    with tempfile.TemporaryDirectory(prefix="pixie-village-thread-smoke-") as temporary:
        runtime = Path(temporary)
        service = server.ConversationService(config, runtime, catalog)
        created = service.create_session(
            "How should two residents make a difficult public choice together?",
            session_id="smoke-thread-v1",
            seed=23,
        )
        current = service.step(created["session_id"])
        current = service.step(created["session_id"])
        free_transcript = list(current["transcript"])
        current = service.attach_decision_thread(created["session_id"], decision_id)
        for _ in range(4):
            current = service.step(created["session_id"])
        resumed = server.ConversationService(config, runtime, catalog).get_session(created["session_id"])
        packet_text = server.canonical_json(current["decision_packet"])
        legal = {option["id"] for option in current["decision_packet"]["options"]}
        threaded_turns = current["transcript"][2:]
        event_rows = [
            json.loads(line)
            for line in service.store.events_path(created["session_id"]).read_text(encoding="utf-8").splitlines()
        ]
        assertions = {
            "conversation_created_without_storyworld": created["mode"] == "conversation" and created["decision_id"] is None,
            "free_talk_precedes_thread": len(free_transcript) == 2 and all(row["proposed_action_id"] is None for row in free_transcript),
            "prior_transcript_preserved": current["transcript"][:2] == free_transcript,
            "thread_boundary_recorded": current["thread_attached_turn"] == 2,
            "thread_is_deliberation_only": current["engine_mode"] == "deliberation_only" and current["engine"] is None,
            "strict_alternation": [row["speaker_id"] for row in current["transcript"]] == ["lumen", "moss"] * 3,
            "threaded_proposals_legal": all(row["proposed_action_id"] in legal for row in threaded_turns),
            "proposal_markers_not_public": all("[proposal:" not in row["message"] for row in threaded_turns),
            "private_values_absent": all(value not in packet_text for value in private_values),
            "attachment_fsynced": [row["event_type"] for row in event_rows].count("storyworld_thread_attached") == 1,
            "resume_exact": resumed["transcript"] == current["transcript"] and resumed["decision_id"] == decision_id,
        }
        receipt = {
            "schema_version": "pixie_village_storyworld_thread_smoke_v1",
            "status": "PASS" if all(assertions.values()) else "FAIL",
            "evidence_class": "deterministic_conversation_then_context_thread_plumbing_only",
            "decision_id": decision_id,
            "decision_packet_sha256": server.sha256_value(current["decision_packet"]),
            "free_turns_before_thread": len(free_transcript),
            "threaded_turns": len(threaded_turns),
            "transcript_sha256": server.sha256_value(current["transcript"]),
            "assertions": assertions,
            "note": "This proves platform-first conversation followed by optional public decision context; it does not execute a world or evaluate a LoRA.",
        }
    output = APP_ROOT / "reports" / "storyworld_thread_smoke.receipt.json"
    server.atomic_json(output, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    print(f"Wrote {output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
