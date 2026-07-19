"""Transport and identity preflight for server-owned Pixie model routes."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse


PREFLIGHT_SCHEMA = "pixie_village_provider_preflight_v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProviderPreflightError(RuntimeError):
    """A server-owned model route failed discovery or identity checks."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _json_request(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float = 15.0,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None if payload is None else canonical_json(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    headers.update(extra_headers or {})
    method = "GET"
    if data is not None:
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
            if not isinstance(decoded, dict):
                raise ProviderPreflightError(f"endpoint returned non-object JSON: {url}")
            return response.status, decoded
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ProviderPreflightError(f"endpoint request failed at {url}: {exc}") from exc


def _models_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    return clean + "/models" if clean.endswith("/v1") else clean + "/v1/models"


def _chat_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    return clean + "/chat/completions" if clean.endswith("/v1") else clean + "/v1/chat/completions"


def _identity_url(base_url: str, configured: Any) -> str | None:
    value = str(configured or "").strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value
    return urljoin(base_url.rstrip("/") + "/", value.lstrip("/"))


def validate_unique_routes(config: dict[str, Any]) -> list[dict[str, str]]:
    routes: list[dict[str, str]] = []
    seen: dict[tuple[str, str], str] = {}
    for agent in config.get("agents", []):
        provider = agent.get("provider", {})
        if provider.get("type") != "openai_compatible":
            continue
        base_url = str(provider.get("base_url") or "").rstrip("/").lower()
        model = str(provider.get("model") or "")
        key = (base_url, model)
        if key in seen:
            raise ProviderPreflightError(
                f"agents {seen[key]} and {agent['id']} share the same endpoint/model route; adapter identity is ambiguous"
            )
        seen[key] = agent["id"]
        routes.append(
            {
                "agent_id": agent["id"],
                "model": model,
                "route_sha256": sha256_value({"base_url": base_url, "model": model}),
            }
        )
    return routes


def probe_agent(agent: dict[str, Any], *, require_attestation: bool = False) -> dict[str, Any]:
    provider = agent["provider"]
    if provider["type"] == "deterministic":
        if require_attestation:
            raise ProviderPreflightError(f"agent {agent['id']} uses deterministic demo provider, not an attested adapter")
        return {
            "agent_id": agent["id"],
            "provider_type": "deterministic",
            "status": "DEMO_ONLY",
            "transport_ok": True,
            "model_list_ok": None,
            "chat_ok": None,
            "adapter_attested": False,
        }
    base_url = str(provider["base_url"]).rstrip("/")
    model = str(provider["model"])
    timeout = float(provider.get("timeout_seconds", 90))
    request_headers: dict[str, str] = {}
    api_key_env = str(provider.get("api_key_env") or "").strip()
    if api_key_env and os.environ.get(api_key_env):
        request_headers["Authorization"] = f"Bearer {os.environ[api_key_env]}"
    started = time.perf_counter()
    model_status, models = _json_request(
        _models_url(base_url), timeout=min(timeout, 20.0), extra_headers=request_headers
    )
    model_ids = [str(row.get("id")) for row in models.get("data", []) if isinstance(row, dict)]
    if model_status != 200 or model not in model_ids:
        raise ProviderPreflightError(f"agent {agent['id']} model {model!r} is not advertised by its endpoint")
    chat_payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": f"Transport check for route {agent['id']}. Reply with one short public sentence.",
            }
        ],
        "temperature": 0,
        "max_tokens": 24,
    }
    chat_status, chat = _json_request(
        _chat_url(base_url), payload=chat_payload, timeout=timeout, extra_headers=request_headers
    )
    try:
        content = str(chat["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderPreflightError(f"agent {agent['id']} returned an invalid chat completion") from exc
    if chat_status != 200 or not content:
        raise ProviderPreflightError(f"agent {agent['id']} chat transport returned no public content")

    expected_sha = str(provider.get("expected_adapter_sha256") or "").lower().strip()
    identity_url = _identity_url(base_url, provider.get("identity_url"))
    attested = False
    identity_receipt: dict[str, Any] | None = None
    if identity_url:
        _, identity = _json_request(
            identity_url, timeout=min(timeout, 20.0), extra_headers=request_headers
        )
        observed_label = str(identity.get("adapter_label") or "")
        observed_sha = str(identity.get("adapter_sha256") or "").lower()
        if observed_label != agent["adapter_label"]:
            raise ProviderPreflightError(
                f"agent {agent['id']} adapter label mismatch: expected {agent['adapter_label']!r}, got {observed_label!r}"
            )
        if not expected_sha or not SHA256_RE.fullmatch(expected_sha):
            raise ProviderPreflightError(f"agent {agent['id']} needs a valid expected_adapter_sha256 for attestation")
        if observed_sha != expected_sha:
            raise ProviderPreflightError(
                f"agent {agent['id']} adapter SHA-256 mismatch: expected {expected_sha}, got {observed_sha}"
            )
        attested = True
        identity_receipt = {
            "schema_version": str(identity.get("schema_version") or ""),
            "adapter_label": observed_label,
            "adapter_sha256": observed_sha,
            "base_model_id": str(identity.get("base_model_id") or ""),
            "base_model_sha256": str(identity.get("base_model_sha256") or "").lower(),
            "llama_server_sha256": str(identity.get("llama_server_sha256") or "").lower(),
            "model_alias": str(identity.get("model_alias") or ""),
            "owned_pid": identity.get("owned_pid"),
            "runtime": str(identity.get("runtime") or ""),
        }
    elif require_attestation:
        raise ProviderPreflightError(f"agent {agent['id']} has no identity_url for adapter attestation")
    return {
        "agent_id": agent["id"],
        "provider_type": "openai_compatible",
        "status": "PASS_ATTESTED" if attested else "PASS_TRANSPORT_ADAPTER_UNVERIFIED",
        "transport_ok": True,
        "model_list_ok": True,
        "chat_ok": True,
        "adapter_attested": attested,
        "model": model,
        "route_sha256": sha256_value({"base_url": base_url.lower(), "model": model}),
        "chat_response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "identity": identity_receipt,
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }


def preflight_providers(config: dict[str, Any], *, require_attestation: bool = False) -> dict[str, Any]:
    routes = validate_unique_routes(config)
    agent_rows = [probe_agent(agent, require_attestation=require_attestation) for agent in config["agents"]]
    openai_rows = [row for row in agent_rows if row["provider_type"] == "openai_compatible"]
    if openai_rows and all(row["adapter_attested"] for row in openai_rows):
        status = "PASS_ATTESTED"
    elif openai_rows:
        status = "PASS_TRANSPORT_ADAPTER_UNVERIFIED"
    else:
        status = "PASS_DETERMINISTIC_DEMO_ONLY"
    return {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": status,
        "require_attestation": require_attestation,
        "route_count": len(routes),
        "routes": routes,
        "agents": agent_rows,
        "config_sha256": sha256_value(config),
    }
