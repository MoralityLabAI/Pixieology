from __future__ import annotations

import copy
import json
import sys
import threading
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import mock_openai_endpoint  # noqa: E402
import provider_preflight  # noqa: E402
import server  # noqa: E402


LUMEN_SHA = "a" * 64
MOSS_SHA = "b" * 64


@pytest.fixture()
def mock_routes():
    lumen = mock_openai_endpoint.make_server(
        "127.0.0.1",
        0,
        {
            "model": "lumen-route",
            "adapter_label": "lumen-lora-test",
            "adapter_sha256": LUMEN_SHA,
            "base_model_id": "cached-test-base",
            "voice": "LUMEN_HTTP",
        },
    )
    moss = mock_openai_endpoint.make_server(
        "127.0.0.1",
        0,
        {
            "model": "moss-route",
            "adapter_label": "moss-lora-test",
            "adapter_sha256": MOSS_SHA,
            "base_model_id": "cached-test-base",
            "voice": "MOSS_HTTP",
        },
    )
    threads = [threading.Thread(target=item.serve_forever, daemon=True) for item in (lumen, moss)]
    for thread in threads:
        thread.start()
    try:
        yield lumen, moss
    finally:
        for item in (lumen, moss):
            item.shutdown()
            item.server_close()
        for thread in threads:
            thread.join(timeout=5)


def routed_config(mock_routes, *, with_attestation: bool = True) -> dict:
    lumen, moss = mock_routes
    config = server.read_json(APP_ROOT / "config" / "agents.example.json")
    routes = [
        (lumen, "lumen-route", "lumen-lora-test", LUMEN_SHA),
        (moss, "moss-route", "moss-lora-test", MOSS_SHA),
    ]
    for agent, (endpoint, model, label, adapter_sha) in zip(config["agents"], routes, strict=True):
        agent["adapter_label"] = label
        agent["provider"] = {
            "type": "openai_compatible",
            "base_url": f"http://127.0.0.1:{endpoint.server_address[1]}",
            "model": model,
            "timeout_seconds": 5,
            "max_tokens": 80,
        }
        if with_attestation:
            agent["provider"].update(
                {
                    "identity_url": "/pixie/identity",
                    "expected_adapter_sha256": adapter_sha,
                }
            )
    return server.validate_agent_config(config)


def test_two_distinct_http_routes_pass_strict_attestation(mock_routes) -> None:
    config = routed_config(mock_routes)
    report = provider_preflight.preflight_providers(config, require_attestation=True)
    assert report["status"] == "PASS_ATTESTED"
    assert report["route_count"] == 2
    assert len({row["route_sha256"] for row in report["routes"]}) == 2
    assert [row["identity"]["adapter_sha256"] for row in report["agents"]] == [LUMEN_SHA, MOSS_SHA]


def test_http_routes_drive_the_correct_village_resident(mock_routes, tmp_path: Path) -> None:
    config = routed_config(mock_routes)
    report = provider_preflight.preflight_providers(config, require_attestation=True)
    service = server.ConversationService(config, tmp_path / "http-runtime", provider_preflight=report)
    created = service.create_session("Can two routed residents hear each other?", session_id="http-route-room-17")
    first = service.step(created["session_id"])
    second = service.step(created["session_id"])
    assert first["transcript"][0]["speaker_id"] == "lumen"
    assert first["transcript"][0]["message"].startswith("LUMEN_HTTP")
    assert second["transcript"][1]["speaker_id"] == "moss"
    assert second["transcript"][1]["message"].startswith("MOSS_HTTP")
    assert second["transcript"][0]["request_sha256"] != second["transcript"][1]["request_sha256"]
    public = service.public_configuration()
    assert public["provider_preflight_status"] == "PASS_ATTESTED"
    assert "127.0.0.1" not in json.dumps(public)


def test_http_routes_emit_legal_storyworld_proposals(mock_routes, tmp_path: Path) -> None:
    config = routed_config(mock_routes)
    report = provider_preflight.preflight_providers(config, require_attestation=True)
    catalog = server.DecisionCatalog(APP_ROOT / "decision_packets")
    service = server.ConversationService(config, tmp_path / "decision-http-runtime", catalog, provider_preflight=report)
    decision_id = catalog.public_index()[0]["decision_id"]
    created = service.create_session(decision_id=decision_id, session_id="http-decision-room-17")
    first = service.step(created["session_id"])
    second = service.step(created["session_id"])
    assert [row["proposed_action_id"] for row in second["transcript"]] == ["propose", "propose"]
    assert all("[proposal:" not in row["message"] for row in second["transcript"])
    assert first["transcript"][0]["message"].startswith("LUMEN_HTTP")
    assert second["transcript"][1]["message"].startswith("MOSS_HTTP")


def test_duplicate_endpoint_model_route_is_rejected(mock_routes) -> None:
    config = routed_config(mock_routes)
    config["agents"][1]["provider"]["base_url"] = config["agents"][0]["provider"]["base_url"]
    config["agents"][1]["provider"]["model"] = config["agents"][0]["provider"]["model"]
    with pytest.raises(provider_preflight.ProviderPreflightError, match="ambiguous"):
        provider_preflight.preflight_providers(config)


def test_adapter_attestation_mismatch_fails_closed(mock_routes) -> None:
    config = routed_config(mock_routes)
    config["agents"][0]["provider"]["expected_adapter_sha256"] = "c" * 64
    with pytest.raises(provider_preflight.ProviderPreflightError, match="SHA-256 mismatch"):
        provider_preflight.preflight_providers(config, require_attestation=True)


def test_transport_can_pass_while_adapter_remains_explicitly_unverified(mock_routes) -> None:
    config = routed_config(mock_routes, with_attestation=False)
    report = provider_preflight.preflight_providers(config)
    assert report["status"] == "PASS_TRANSPORT_ADAPTER_UNVERIFIED"
    assert all(row["adapter_attested"] is False for row in report["agents"])
    with pytest.raises(provider_preflight.ProviderPreflightError, match="identity_url"):
        provider_preflight.preflight_providers(config, require_attestation=True)


def test_unreachable_route_and_demo_strict_mode_fail() -> None:
    config = server.validate_agent_config(server.read_json(APP_ROOT / "config" / "agents.example.json"))
    with pytest.raises(provider_preflight.ProviderPreflightError, match="deterministic demo"):
        provider_preflight.preflight_providers(config, require_attestation=True)
    broken = copy.deepcopy(config)
    broken["agents"][0]["provider"] = {
        "type": "openai_compatible",
        "base_url": "http://127.0.0.1:9",
        "model": "missing",
        "timeout_seconds": 0.1,
    }
    with pytest.raises(provider_preflight.ProviderPreflightError, match="request failed"):
        provider_preflight.preflight_providers(broken)


def test_server_cli_preflight_only_writes_attested_report(mock_routes, tmp_path: Path) -> None:
    config_path = tmp_path / "agents.local.json"
    report_path = tmp_path / "provider_preflight.json"
    config_path.write_text(
        json.dumps(routed_config(mock_routes), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    result = server.main(
        [
            "--agents",
            str(config_path),
            "--runtime-root",
            str(tmp_path / "runtime"),
            "--require-adapter-attestation",
            "--preflight-only",
            "--preflight-report",
            str(report_path),
        ]
    )
    assert result == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "PASS_ATTESTED"
    assert report["route_count"] == 2
    assert len({row["route_sha256"] for row in report["routes"]}) == 2
