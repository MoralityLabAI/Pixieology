#!/usr/bin/env python3
"""Exercise two attested HTTP routes through conversation and Storyworld layers.

The endpoints are development mocks with no model weights. This receipt proves
network routing and identity enforcement, never LoRA behavior.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import engine_bridge  # noqa: E402
import mock_openai_endpoint  # noqa: E402
import provider_preflight  # noqa: E402
import server  # noqa: E402
import storyworld_bridge  # noqa: E402


LUMEN_SHA = "a" * 64
MOSS_SHA = "b" * 64


def main() -> int:
    endpoint_specs = [
        {
            "model": "lumen-route",
            "adapter_label": "lumen-development-route",
            "adapter_sha256": LUMEN_SHA,
            "base_model_id": "development-mock-no-model",
            "voice": "LUMEN_HTTP",
        },
        {
            "model": "moss-route",
            "adapter_label": "moss-development-route",
            "adapter_sha256": MOSS_SHA,
            "base_model_id": "development-mock-no-model",
            "voice": "MOSS_HTTP",
        },
    ]
    endpoints = [mock_openai_endpoint.make_server("127.0.0.1", 0, settings) for settings in endpoint_specs]
    threads = [threading.Thread(target=endpoint.serve_forever, daemon=True) for endpoint in endpoints]
    for thread in threads:
        thread.start()
    try:
        config = server.read_json(APP_ROOT / "config" / "agents.example.json")
        for agent, endpoint, spec in zip(config["agents"], endpoints, endpoint_specs, strict=True):
            agent["adapter_label"] = spec["adapter_label"]
            agent["provider"] = {
                "type": "openai_compatible",
                "base_url": f"http://127.0.0.1:{endpoint.server_address[1]}",
                "model": spec["model"],
                "identity_url": "/pixie/identity",
                "expected_adapter_sha256": spec["adapter_sha256"],
                "timeout_seconds": 5,
                "max_tokens": 80,
            }
        config = server.validate_agent_config(config)
        preflight = provider_preflight.preflight_providers(config, require_attestation=True)
        catalog = server.DecisionCatalog(APP_ROOT / "decision_packets")
        _, _, _, source_root, engine_root = server.configured_paths()
        bridge = engine_bridge.StoryworldEngineBridge(engine_root, source_root, catalog)
        decision_id = catalog.public_index()[0]["decision_id"]
        source_world = storyworld_bridge.read_object(source_root / "worlds" / "dev" / "sealed_testimony_v1.json")
        private_values = storyworld_bridge.private_source_values(source_world)
        with tempfile.TemporaryDirectory(prefix="pixie-village-dual-http-") as temporary:
            runtime = Path(temporary)
            service = server.ConversationService(
                config,
                runtime,
                catalog,
                bridge,
                provider_preflight=preflight,
            )
            created = service.create_session(decision_id=decision_id, session_id="smoke-dual-http-v1", seed=23)
            current = created
            for _ in range(4):
                current = service.step(created["session_id"])
            encoded = server.canonical_json(current)
            voices = [row["message"].split()[0] for row in current["transcript"]]
            legal = {option["id"] for option in current["decision_packet"]["options"]}
            assertions = {
                "strict_attestation": preflight["status"] == "PASS_ATTESTED",
                "two_unique_routes": len({row["route_sha256"] for row in preflight["routes"]}) == 2,
                "alternating_http_voices": voices == ["LUMEN_HTTP", "MOSS_HTTP", "LUMEN_HTTP", "MOSS_HTTP"],
                "all_proposals_legal": all(row["proposed_action_id"] in legal for row in current["transcript"]),
                "canonical_engine_turns": current["engine"]["public_state"]["engine_turn"] == 4,
                "public_consequences_present": all(row["world_consequence"] for row in current["transcript"]),
                "private_values_absent": all(value not in encoded for value in private_values),
                "public_config_redacted": "127.0.0.1" not in json.dumps(service.public_configuration()),
                "no_model_weights_used": all(
                    row["identity"]["runtime"] == "development_mock_no_model" for row in preflight["agents"]
                ),
            }
            receipt = {
                "schema_version": "pixie_village_dual_http_smoke_v1",
                "status": "PASS" if all(assertions.values()) else "FAIL",
                "evidence_class": "development_mock_http_routing_only",
                "lora_behavior_evaluated": False,
                "model_weights_loaded": False,
                "provider_preflight_status": preflight["status"],
                "route_sha256s": [row["route_sha256"] for row in preflight["routes"]],
                "attested_development_adapter_sha256s": [
                    row["identity"]["adapter_sha256"] for row in preflight["agents"]
                ],
                "speaker_order": [row["speaker_id"] for row in current["transcript"]],
                "voices": voices,
                "proposals": [row["proposed_action_id"] for row in current["transcript"]],
                "outcomes": [row["world_consequence"]["outcome"] for row in current["transcript"]],
                "assertions": assertions,
                "note": "This certifies endpoint separation, attestation plumbing, and canonical-world routing using no-model development endpoints. It is not a LoRA result.",
            }
    finally:
        for endpoint in endpoints:
            endpoint.shutdown()
            endpoint.server_close()
        for thread in threads:
            thread.join(timeout=5)
    output = APP_ROOT / "reports" / "dual_http_route_smoke.receipt.json"
    server.atomic_json(output, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    print(f"Wrote {output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
