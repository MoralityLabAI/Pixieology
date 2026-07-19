#!/usr/bin/env python3
"""Exercise persona-canary plumbing using two no-model development routes."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import mock_openai_endpoint  # noqa: E402
import persona_canary_eval  # noqa: E402
import server  # noqa: E402


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.partial")
    with temporary.open("wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def smoke_spec() -> dict:
    return {
        "schema_version": persona_canary_eval.SPEC_SCHEMA,
        "neutral_system_prompt": "Answer directly using public speech only.",
        "decoding": {"temperature": 0, "max_tokens": 32},
        "thresholds": {
            "minimum_probe_pass_rate": 1.0,
            "maximum_forbidden_violation_rate": 0.0,
            "maximum_cross_contamination_rate": 0.0,
        },
        "agents": [
            {
                "agent_id": agent_id,
                "unique_markers": [voice],
                "forbidden_markers": [other_voice],
                "probes": [
                    {
                        "probe_id": f"{agent_id}_smoke_{index}",
                        "prompt": f"Held-out village canary {index}: answer the other resident briefly.",
                        "required_any": [voice],
                    }
                    for index in range(4)
                ],
            }
            for agent_id, voice, other_voice in (
                ("lumen", "LUMEN_HTTP", "MOSS_HTTP"),
                ("moss", "MOSS_HTTP", "LUMEN_HTTP"),
            )
        ],
    }


def main() -> int:
    settings = [
        {
            "model": "lumen-canary-route",
            "adapter_label": "lumen-development-canary",
            "adapter_sha256": "a" * 64,
            "base_model_id": "development-mock-no-model",
            "voice": "LUMEN_HTTP",
        },
        {
            "model": "moss-canary-route",
            "adapter_label": "moss-development-canary",
            "adapter_sha256": "b" * 64,
            "base_model_id": "development-mock-no-model",
            "voice": "MOSS_HTTP",
        },
    ]
    endpoints = [mock_openai_endpoint.make_server("127.0.0.1", 0, row) for row in settings]
    threads = [threading.Thread(target=item.serve_forever, daemon=True) for item in endpoints]
    for thread in threads:
        thread.start()
    try:
        config = server.read_json(APP_ROOT / "config" / "agents.example.json")
        for agent, endpoint, values in zip(config["agents"], endpoints, settings, strict=True):
            agent["adapter_label"] = values["adapter_label"]
            agent["provider"] = {
                "type": "openai_compatible",
                "base_url": f"http://127.0.0.1:{endpoint.server_address[1]}",
                "model": values["model"],
                "identity_url": "/pixie/identity",
                "expected_adapter_sha256": values["adapter_sha256"],
                "timeout_seconds": 5,
                "max_tokens": 64,
            }
        with tempfile.TemporaryDirectory(prefix="pixie-village-canary-smoke-") as temporary:
            work = Path(temporary) / "run"
            report = persona_canary_eval.evaluate(config, smoke_spec(), work, allow_development=True)
            raw = (work / "raw_generations.jsonl").read_bytes()
            rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]
            assertions = {
                "development_status_explicit": report["status"] == "PASS_DEVELOPMENT_ONLY",
                "real_provenance_not_claimed": report["real_provenance"] is False,
                "two_distinct_identity_hashes": report["distinct_adapter_sha256s"] is True,
                "eight_held_out_requests": len(rows) == 8,
                "all_lexical_canaries_pass": all(row["passed"] for row in rows),
                "no_cross_contamination": all(not row["cross_contamination_hits"] for row in rows),
            }
            receipt = {
                **report,
                "schema_version": "pixie_village_persona_canary_smoke_v1",
                "status": "PASS" if all(assertions.values()) else "FAIL",
                "canary_gate_status": report["status"],
                "assertions": assertions,
                "note": "This uses two no-model development endpoints and certifies evaluator plumbing only, never LoRA behavior.",
            }
            server.atomic_json(APP_ROOT / "reports" / "persona_canary_development_smoke.receipt.json", receipt)
            atomic_bytes(APP_ROOT / "reports" / "persona_canary_development_smoke.raw.jsonl", raw)
    finally:
        for endpoint in endpoints:
            endpoint.shutdown()
            endpoint.server_close()
        for thread in threads:
            thread.join(timeout=5)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
