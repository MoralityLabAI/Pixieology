#!/usr/bin/env python3
"""Exercise proposal -> canonical world transition -> next-Pixie context."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import engine_bridge  # noqa: E402
import server  # noqa: E402
import storyworld_bridge  # noqa: E402


def main() -> int:
    _, _, _, source_root, engine_root = server.configured_paths()
    config = server.validate_agent_config(server.read_json(APP_ROOT / "config" / "agents.example.json"))
    catalog = server.DecisionCatalog(APP_ROOT / "decision_packets")
    bridge = engine_bridge.StoryworldEngineBridge(engine_root, source_root, catalog)
    decision_id = catalog.public_index()[0]["decision_id"]
    source_world = storyworld_bridge.read_object(source_root / "worlds" / "dev" / "sealed_testimony_v1.json")
    private_values = storyworld_bridge.private_source_values(source_world)
    with tempfile.TemporaryDirectory(prefix="pixie-village-engine-smoke-") as temporary:
        runtime = Path(temporary)
        service = server.ConversationService(config, runtime, catalog, bridge)
        created = service.create_session(decision_id=decision_id, session_id="smoke-engine-loop-v1", seed=23)
        current = created
        for _ in range(4):
            current = service.step(created["session_id"])
        fresh_catalog = server.DecisionCatalog(APP_ROOT / "decision_packets")
        fresh_bridge = engine_bridge.StoryworldEngineBridge(engine_root, source_root, fresh_catalog)
        resumed_service = server.ConversationService(config, runtime, fresh_catalog, fresh_bridge)
        resumed = resumed_service.step(created["session_id"])
        encoded = server.canonical_json(resumed)
        outcomes = [row["public_event"]["outcome"] for row in resumed["engine"]["history"]]
        locations = [row["public_event"]["location"] for row in resumed["engine"]["history"]]
        prompt = server.build_agent_messages(config, resumed_service.store.load(created["session_id"]), config["agents"][1])
        prompt_packet = json.loads(prompt[1]["content"])
        assertions = {
            "canonical_engine_mode": resumed["engine_mode"] == "canonical",
            "five_engine_steps": len(resumed["engine"]["history"]) == 5,
            "conversation_and_engine_turns_match": resumed["turn_index"] == resumed["engine"]["public_state"]["engine_turn"],
            "fresh_service_replay": resumed["engine"]["history"][-1]["replay_prefix_sha256"]
            == server.sha256_value(resumed["engine"]["history"][:-1]),
            "public_consequences_in_prompt": len(prompt_packet["public_world_history"]) == 5,
            "private_values_absent": all(value not in encoded and value not in json.dumps(prompt) for value in private_values),
            "forbidden_keys_absent": all(f'"{key}"' not in encoded for key in engine_bridge.FORBIDDEN_PUBLIC_KEYS),
            "canonical_validation": resumed["engine"]["canonical_validation"] is True,
        }
        receipt = {
            "schema_version": "pixie_village_engine_loop_smoke_v1",
            "status": "PASS" if all(assertions.values()) else "FAIL",
            "evidence_class": "deterministic_canonical_engine_plumbing_only",
            "decision_id": decision_id,
            "source_world_sha256": resumed["engine"]["source_sha256"],
            "canonical_engine_sha256": resumed["engine"]["engine_sha256"],
            "turns": resumed["turn_index"],
            "outcomes": outcomes,
            "locations": locations,
            "final_public_state": resumed["engine"]["public_state"],
            "forbidden_value_checks": len(private_values),
            "assertions": assertions,
            "note": "This proves canonical engine replay and public consequence feedback with deterministic demo speakers; it does not evaluate a LoRA.",
        }
    output = APP_ROOT / "reports" / "canonical_engine_loop_smoke.receipt.json"
    server.atomic_json(output, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    print(f"Wrote {output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
