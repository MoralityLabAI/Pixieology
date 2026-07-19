#!/usr/bin/env python3
"""Run a two-agent deliberation over a leakage-audited Storyworld decision."""

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
    with tempfile.TemporaryDirectory(prefix="pixie-village-storyworld-smoke-") as temporary:
        runtime = Path(temporary)
        service = server.ConversationService(config, runtime, catalog)
        created = service.create_session(decision_id=decision_id, session_id="smoke-storyworld-v1", seed=23)
        current = created
        for _ in range(6):
            current = service.step(created["session_id"])
        resumed = server.ConversationService(config, runtime, catalog).get_session(created["session_id"])
        packet_text = server.canonical_json(current["decision_packet"])
        legal = {option["id"] for option in current["decision_packet"]["options"]}
        assertions = {
            "storyworld_mode": current["mode"] == "storyworld_decision",
            "strict_alternation": [row["speaker_id"] for row in current["transcript"]] == ["lumen", "moss"] * 3,
            "all_proposals_legal": all(row["proposed_action_id"] in legal for row in current["transcript"]),
            "proposal_markers_not_public": all("[proposal:" not in row["message"] for row in current["transcript"]),
            "visible_facts_present": len(current["decision_packet"]["visible_facts"]) == 3,
            "private_values_absent": all(value not in packet_text for value in private_values),
            "resume_exact": resumed["transcript"] == current["transcript"],
        }
        receipt = {
            "schema_version": "pixie_village_storyworld_smoke_v1",
            "status": "PASS" if all(assertions.values()) else "FAIL",
            "evidence_class": "deterministic_storyworld_bridge_plumbing_only",
            "decision_id": decision_id,
            "decision_packet_sha256": server.sha256_value(current["decision_packet"]),
            "source_world_sha256": current["decision_packet"]["source"]["source_sha256"],
            "turns": len(current["transcript"]),
            "proposal_sequence": [row["proposed_action_id"] for row in current["transcript"]],
            "transcript_sha256": server.sha256_value(current["transcript"]),
            "forbidden_value_checks": len(private_values),
            "assertions": assertions,
            "note": "This proves public decision projection and two-agent deliberation plumbing; it does not execute world consequences or evaluate a LoRA.",
        }
    output = APP_ROOT / "reports" / "storyworld_decision_smoke.receipt.json"
    server.atomic_json(output, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    print(f"Wrote {output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
