#!/usr/bin/env python3
"""Run a deterministic two-agent smoke and write an auditable receipt."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import server  # noqa: E402


def main() -> int:
    config_path = APP_ROOT / "config" / "agents.example.json"
    config = server.validate_agent_config(server.read_json(config_path))
    with tempfile.TemporaryDirectory(prefix="pixie-village-smoke-") as temporary:
        runtime = Path(temporary)
        service = server.ConversationService(config, runtime)
        created = service.create_session(
            "How can two persona adapters keep distinct voices while building one shared home?",
            session_id="smoke-two-agent-v1",
            seed=17,
        )
        current = created
        for _ in range(6):
            current = service.step(created["session_id"])
        resumed = server.ConversationService(config, runtime).get_session(created["session_id"])
        order = [row["speaker_id"] for row in current["transcript"]]
        expected = ["lumen", "moss", "lumen", "moss", "lumen", "moss"]
        event_rows = service.store.events_path(created["session_id"]).read_text(encoding="utf-8").splitlines()
        assertions = {
            "six_turns": len(current["transcript"]) == 6,
            "strict_alternation": order == expected,
            "distinct_public_messages": len({row["message"] for row in current["transcript"]}) >= 4,
            "resume_exact": resumed["transcript"] == current["transcript"],
            "fsynced_event_shape": len(event_rows) == 7 and json.loads(event_rows[-1])["event_type"] == "turn_committed",
            "public_config_redacted": all(
                token not in json.dumps(server.public_config(config))
                for token in ["private_system_prompt", "base_url", "api_key_env", "model"]
            ),
        }
        receipt = {
            "schema_version": "pixie_village_smoke_receipt_v1",
            "status": "PASS" if all(assertions.values()) else "FAIL",
            "evidence_class": "deterministic_demo_plumbing_only",
            "config_sha256": server.sha256_value(config),
            "session_schema": current["schema_version"],
            "turns": len(current["transcript"]),
            "speaker_order": order,
            "transcript_sha256": server.sha256_value(current["transcript"]),
            "assertions": assertions,
            "sample_transcript": [
                {"turn": row["turn"], "speaker_id": row["speaker_id"], "message": row["message"]}
                for row in current["transcript"]
            ],
            "note": "This receipt proves the two-agent room, alternation, persistence, and redaction path; it does not evaluate a LoRA.",
        }
    output = APP_ROOT / "reports" / "two_agent_smoke.receipt.json"
    server.atomic_json(output, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    print(f"Wrote {output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
