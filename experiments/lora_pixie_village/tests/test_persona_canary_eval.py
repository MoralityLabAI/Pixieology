from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import mock_openai_endpoint  # noqa: E402
import persona_canary_eval as canary  # noqa: E402
import server  # noqa: E402


@pytest.fixture()
def mock_routes():
    settings = [
        {
            "model": "lumen-route",
            "adapter_label": "lumen-test",
            "adapter_sha256": "a" * 64,
            "base_model_id": "no-model",
            "voice": "LUMEN_HTTP",
        },
        {
            "model": "moss-route",
            "adapter_label": "moss-test",
            "adapter_sha256": "b" * 64,
            "base_model_id": "no-model",
            "voice": "MOSS_HTTP",
        },
    ]
    endpoints = [mock_openai_endpoint.make_server("127.0.0.1", 0, row) for row in settings]
    threads = [threading.Thread(target=item.serve_forever, daemon=True) for item in endpoints]
    for thread in threads:
        thread.start()
    try:
        yield endpoints, settings
    finally:
        for endpoint in endpoints:
            endpoint.shutdown()
            endpoint.server_close()
        for thread in threads:
            thread.join(timeout=5)


def routed_config(endpoints, settings) -> dict:
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
    return config


def spec() -> dict:
    return {
        "schema_version": canary.SPEC_SCHEMA,
        "neutral_system_prompt": "Answer directly with public speech only.",
        "decoding": {"temperature": 0, "max_tokens": 32},
        "thresholds": {
            "minimum_probe_pass_rate": 1.0,
            "maximum_forbidden_violation_rate": 0.0,
            "maximum_cross_contamination_rate": 0.0,
        },
        "agents": [
            {
                "agent_id": "lumen",
                "unique_markers": ["LUMEN_HTTP"],
                "forbidden_markers": ["MOSS_HTTP"],
                "probes": [
                    {"probe_id": f"lumen_{index}", "prompt": f"Held-out prompt {index}", "required_any": ["LUMEN_HTTP"]}
                    for index in range(4)
                ],
            },
            {
                "agent_id": "moss",
                "unique_markers": ["MOSS_HTTP"],
                "forbidden_markers": ["LUMEN_HTTP"],
                "probes": [
                    {"probe_id": f"moss_{index}", "prompt": f"Held-out prompt {index}", "required_any": ["MOSS_HTTP"]}
                    for index in range(4)
                ],
            },
        ],
    }


def test_development_canaries_pass_only_as_development_evidence(mock_routes, tmp_path: Path) -> None:
    endpoints, settings = mock_routes
    report = canary.evaluate(
        routed_config(endpoints, settings),
        spec(),
        tmp_path / "canaries",
        allow_development=True,
    )
    assert report["status"] == "PASS_DEVELOPMENT_ONLY"
    assert report["real_provenance"] is False
    assert report["behavior_pass"] is True
    assert report["distinct_adapter_sha256s"] is True
    raw = (tmp_path / "canaries" / "raw_generations.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(raw) == 8
    assert all(json.loads(line)["passed"] for line in raw)


def test_development_runtime_is_rejected_by_real_gate(mock_routes, tmp_path: Path) -> None:
    endpoints, settings = mock_routes
    with pytest.raises(canary.CanaryError, match="not owned by the real"):
        canary.evaluate(routed_config(endpoints, settings), spec(), tmp_path / "real-only")


def test_cross_resident_contamination_fails_behavior_gate(mock_routes, tmp_path: Path) -> None:
    endpoints, settings = mock_routes
    endpoints[1].settings["voice"] = "MOSS_HTTP LUMEN_HTTP"  # type: ignore[attr-defined]
    report = canary.evaluate(
        routed_config(endpoints, settings),
        spec(),
        tmp_path / "contaminated",
        allow_development=True,
    )
    assert report["status"] == "FAIL"
    assert report["behavior_pass"] is False
    moss = next(row for row in report["agents"] if row["agent_id"] == "moss")
    assert moss["cross_contamination_rate"] == 1.0


def test_spec_rejects_shared_markers_and_persona_mismatch(mock_routes) -> None:
    endpoints, settings = mock_routes
    config = server.validate_agent_config(routed_config(endpoints, settings))
    bad = spec()
    bad["agents"][1]["unique_markers"] = ["LUMEN_HTTP"]
    with pytest.raises(canary.CanaryError, match="shared"):
        canary.validate_canary_spec(bad, config)
    missing = spec()
    missing["agents"][1]["agent_id"] = "other"
    with pytest.raises(canary.CanaryError, match="unconfigured"):
        canary.validate_canary_spec(missing, config)


def test_real_provenance_verifies_live_pid_command_route_and_file_hashes(mock_routes, tmp_path: Path) -> None:
    endpoints, settings = mock_routes
    config = server.validate_agent_config(routed_config(endpoints, settings))
    agent = config["agents"][0]
    executable = tmp_path / "llama-server.exe"
    base = tmp_path / "base.gguf"
    adapter = tmp_path / "lumen.gguf"
    executable.write_bytes(b"runtime")
    base.write_bytes(b"base")
    adapter.write_bytes(b"adapter")
    identity = {
        "runtime": canary.REAL_RUNTIME,
        "adapter_label": agent["adapter_label"],
        "adapter_sha256": canary._file_sha256(adapter),
        "base_model_id": "test-base",
        "base_model_sha256": canary._file_sha256(base),
        "llama_server_sha256": canary._file_sha256(executable),
        "model_alias": agent["provider"]["model"],
        "owned_pid": os.getpid(),
    }
    manifest = {
        "schema_version": "pixie_attested_llama_launch_v1",
        "status": "READY",
        "runtime": canary.REAL_RUNTIME,
        "adapter_label": agent["adapter_label"],
        "base_model_id": "test-base",
        "model_alias": agent["provider"]["model"],
        "public_route": {"host": "127.0.0.1", "port": endpoints[0].server_address[1]},
        "owned_pid": os.getpid(),
        "files": {
            "llama_server": str(executable),
            "base_model": str(base),
            "adapter": str(adapter),
        },
        "hashes": {
            "llama_server_sha256": identity["llama_server_sha256"],
            "base_model_sha256": identity["base_model_sha256"],
            "adapter_sha256": identity["adapter_sha256"],
        },
        "command": [
            str(executable),
            "-m",
            str(base),
            "--lora",
            str(adapter),
            "--alias",
            agent["provider"]["model"],
        ],
        "identity": identity,
    }
    manifest_path = tmp_path / "launch_manifest.json"
    server.atomic_json(manifest_path, manifest)
    agent["provider"]["launch_manifest"] = str(manifest_path)
    check = canary.verify_launch_manifest(agent, identity)
    assert check["route_verified"] is True
    assert check["command_verified"] is True
    assert check["owned_pid"] == os.getpid()
    adapter.write_bytes(b"changed-after-launch")
    with pytest.raises(canary.CanaryError, match="adapter hash differs"):
        canary.verify_launch_manifest(agent, identity)
