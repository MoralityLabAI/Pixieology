#!/usr/bin/env python3
"""Model-free held-out canary gate for two attested village residents.

This evaluator uses lexical markers, not NLI or a semantic persona judge. It is
an inexpensive end-to-end check that two routes retain distinct trained
behavior under a neutral prompt. Development endpoints can exercise the
plumbing, but receive a non-real evidence status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from provider_preflight import ProviderPreflightError, preflight_providers
from server import atomic_json, canonical_json, configured_paths, read_json, sha256_value, validate_agent_config


SCHEMA = "pixie_village_persona_canary_report_v1"
SPEC_SCHEMA = "pixie_village_persona_canaries_v1"
REAL_RUNTIME = "pixie_attested_llama_proxy_v1"
ID_RE = re.compile(r"^[a-zA-Z0-9_-]{3,80}$")


class CanaryError(RuntimeError):
    """A canary specification, route, or result violated the frozen gate."""


def _nonempty_strings(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
        raise CanaryError(f"{field} must be a nonempty list of nonempty strings")
    return [item.strip() for item in value]


def validate_canary_spec(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != SPEC_SCHEMA:
        raise CanaryError(f"unsupported canary schema: {payload.get('schema_version')!r}")
    neutral = str(payload.get("neutral_system_prompt") or "").strip()
    if not neutral:
        raise CanaryError("neutral_system_prompt is required")
    decoding = payload.get("decoding")
    if not isinstance(decoding, dict) or float(decoding.get("temperature", -1)) != 0:
        raise CanaryError("primary canary decoding must use temperature 0")
    max_tokens = int(decoding.get("max_tokens", 0))
    if not 8 <= max_tokens <= 512:
        raise CanaryError("decoding.max_tokens must be between 8 and 512")
    thresholds = payload.get("thresholds")
    if not isinstance(thresholds, dict):
        raise CanaryError("thresholds are required")
    minimum = float(thresholds.get("minimum_probe_pass_rate", -1))
    maximum_forbidden = float(thresholds.get("maximum_forbidden_violation_rate", -1))
    maximum_cross = float(thresholds.get("maximum_cross_contamination_rate", -1))
    if not 0 <= minimum <= 1 or not 0 <= maximum_forbidden <= 1 or not 0 <= maximum_cross <= 1:
        raise CanaryError("canary thresholds must be between 0 and 1")
    raw_agents = payload.get("agents")
    if not isinstance(raw_agents, list) or len(raw_agents) != 2:
        raise CanaryError("the phase-1 canary gate requires exactly two agents")
    configured_ids = {row["id"] for row in config["agents"]}
    seen_agents: set[str] = set()
    seen_probes: set[str] = set()
    all_unique_markers: dict[str, str] = {}
    normalized_agents = []
    for raw_agent in raw_agents:
        if not isinstance(raw_agent, dict):
            raise CanaryError("each canary agent must be an object")
        agent_id = str(raw_agent.get("agent_id") or "")
        if agent_id not in configured_ids or agent_id in seen_agents:
            raise CanaryError(f"canary agent is missing, duplicated, or unconfigured: {agent_id!r}")
        seen_agents.add(agent_id)
        markers = _nonempty_strings(raw_agent.get("unique_markers"), f"{agent_id}.unique_markers")
        for marker in markers:
            folded = marker.casefold()
            if folded in all_unique_markers:
                raise CanaryError(f"unique marker {marker!r} is shared by {agent_id} and {all_unique_markers[folded]}")
            all_unique_markers[folded] = agent_id
        forbidden = raw_agent.get("forbidden_markers", [])
        if not isinstance(forbidden, list) or any(not isinstance(item, str) or not item.strip() for item in forbidden):
            raise CanaryError(f"{agent_id}.forbidden_markers must contain strings")
        probes = raw_agent.get("probes")
        if not isinstance(probes, list) or len(probes) < 4:
            raise CanaryError(f"{agent_id} requires at least four held-out probes")
        normalized_probes = []
        for probe in probes:
            if not isinstance(probe, dict):
                raise CanaryError(f"{agent_id} probe must be an object")
            probe_id = str(probe.get("probe_id") or "")
            if not ID_RE.fullmatch(probe_id) or probe_id in seen_probes:
                raise CanaryError(f"invalid or duplicate probe_id: {probe_id!r}")
            seen_probes.add(probe_id)
            prompt = str(probe.get("prompt") or "").strip()
            if not prompt:
                raise CanaryError(f"probe {probe_id} has no prompt")
            probe_forbidden = probe.get("forbidden_any", [])
            if not isinstance(probe_forbidden, list) or any(
                not isinstance(item, str) or not item.strip() for item in probe_forbidden
            ):
                raise CanaryError(f"{probe_id}.forbidden_any must contain strings")
            normalized_probes.append(
                {
                    "probe_id": probe_id,
                    "prompt": prompt,
                    "required_any": _nonempty_strings(probe.get("required_any"), f"{probe_id}.required_any"),
                    "forbidden_any": [str(item).strip() for item in probe_forbidden],
                }
            )
        normalized_agents.append(
            {
                "agent_id": agent_id,
                "unique_markers": markers,
                "forbidden_markers": [str(item).strip() for item in forbidden],
                "probes": normalized_probes,
            }
        )
    if seen_agents != configured_ids:
        raise CanaryError("canary agents must match the two configured village residents exactly")
    return {
        "schema_version": SPEC_SCHEMA,
        "neutral_system_prompt": neutral,
        "decoding": {"temperature": 0, "max_tokens": max_tokens},
        "thresholds": {
            "minimum_probe_pass_rate": minimum,
            "maximum_forbidden_violation_rate": maximum_forbidden,
            "maximum_cross_contamination_rate": maximum_cross,
        },
        "agents": normalized_agents,
    }


def _chat_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    return clean + "/chat/completions" if clean.endswith("/v1") else clean + "/v1/chat/completions"


def _invoke(agent: dict[str, Any], system: str, prompt: str, decoding: dict[str, Any]) -> tuple[str, str, int]:
    provider = agent["provider"]
    if provider["type"] != "openai_compatible":
        raise CanaryError(f"agent {agent['id']} does not use an HTTP model route")
    payload = {
        "model": provider["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": int(decoding["max_tokens"]),
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key_env = str(provider.get("api_key_env") or "").strip()
    if api_key_env and os.environ.get(api_key_env):
        headers["Authorization"] = f"Bearer {os.environ[api_key_env]}"
    request = urllib.request.Request(
        _chat_url(str(provider["base_url"])),
        data=canonical_json(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=float(provider.get("timeout_seconds", 90))) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise CanaryError(f"agent {agent['id']} canary request failed: {exc}") from exc
    try:
        content = str(decoded["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise CanaryError(f"agent {agent['id']} returned an invalid chat completion") from exc
    if not content:
        raise CanaryError(f"agent {agent['id']} returned an empty canary completion")
    return content, sha256_value(payload), max(0, round((time.perf_counter() - started) * 1000))


def _append_fsync(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(payload) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _owned_process_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _command_value(command: list[Any], flag: str) -> str:
    try:
        index = command.index(flag)
        return str(command[index + 1])
    except (ValueError, IndexError) as exc:
        raise CanaryError(f"launcher command is missing {flag}") from exc


def verify_launch_manifest(agent: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    configured_path = str(agent["provider"].get("launch_manifest") or "").strip()
    if not configured_path:
        raise CanaryError(f"agent {agent['id']} claims a real runtime but has no launch_manifest")
    path = Path(configured_path).expanduser().resolve()
    if not path.is_file():
        raise CanaryError(f"agent {agent['id']} launch manifest is unavailable: {path}")
    manifest = read_json(path)
    if manifest.get("schema_version") != "pixie_attested_llama_launch_v1" or manifest.get("status") != "READY":
        raise CanaryError(f"agent {agent['id']} launcher manifest is not in READY state")
    if manifest.get("runtime") != REAL_RUNTIME or identity.get("runtime") != REAL_RUNTIME:
        raise CanaryError(f"agent {agent['id']} launcher runtime identifier mismatch")
    manifest_identity = manifest.get("identity")
    if not isinstance(manifest_identity, dict):
        raise CanaryError(f"agent {agent['id']} launcher manifest has no identity receipt")
    compared_fields = (
        "adapter_label",
        "adapter_sha256",
        "base_model_id",
        "base_model_sha256",
        "llama_server_sha256",
        "model_alias",
        "owned_pid",
    )
    if any(manifest_identity.get(field) != identity.get(field) for field in compared_fields):
        raise CanaryError(f"agent {agent['id']} endpoint identity differs from its launch manifest")
    provider = agent["provider"]
    parsed = urlparse(str(provider["base_url"]))
    public_route = manifest.get("public_route") or {}
    route_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if parsed.hostname != public_route.get("host") or route_port != public_route.get("port"):
        raise CanaryError(f"agent {agent['id']} provider route differs from its launch manifest")
    if str(provider["model"]) != manifest.get("model_alias") or identity.get("model_alias") != provider["model"]:
        raise CanaryError(f"agent {agent['id']} model alias differs from its launch manifest")
    pid = manifest.get("owned_pid")
    if pid != identity.get("owned_pid") or not _owned_process_alive(pid):
        raise CanaryError(f"agent {agent['id']} launcher-owned PID is not alive")
    files = manifest.get("files")
    hashes = manifest.get("hashes")
    command = manifest.get("command")
    if not isinstance(files, dict) or not isinstance(hashes, dict) or not isinstance(command, list):
        raise CanaryError(f"agent {agent['id']} launcher manifest has invalid file or command records")
    expected = {
        "llama_server": "llama_server_sha256",
        "base_model": "base_model_sha256",
        "adapter": "adapter_sha256",
    }
    verified_hashes = {}
    for file_key, hash_key in expected.items():
        file_path = Path(str(files.get(file_key) or "")).expanduser().resolve()
        if not file_path.is_file():
            raise CanaryError(f"agent {agent['id']} launch input disappeared: {file_key}")
        observed = _file_sha256(file_path)
        if observed != hashes.get(hash_key) or observed != identity.get(hash_key):
            raise CanaryError(f"agent {agent['id']} {file_key} hash differs from launch provenance")
        verified_hashes[hash_key] = observed
    if Path(_command_value(command, "-m")).resolve() != Path(str(files["base_model"])).resolve():
        raise CanaryError(f"agent {agent['id']} base-model command argument differs from manifest")
    if Path(_command_value(command, "--lora")).resolve() != Path(str(files["adapter"])).resolve():
        raise CanaryError(f"agent {agent['id']} adapter command argument differs from manifest")
    if _command_value(command, "--alias") != provider["model"]:
        raise CanaryError(f"agent {agent['id']} alias command argument differs from manifest")
    return {
        "agent_id": agent["id"],
        "manifest_sha256": _file_sha256(path),
        "owned_pid": pid,
        "route_verified": True,
        "command_verified": True,
        "file_hashes_verified": verified_hashes,
    }


def evaluate(
    config: dict[str, Any],
    spec: dict[str, Any],
    out_dir: Path,
    *,
    allow_development: bool = False,
) -> dict[str, Any]:
    config = validate_agent_config(config)
    spec = validate_canary_spec(spec, config)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise CanaryError(f"refusing to overwrite nonempty canary directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        preflight = preflight_providers(config, require_attestation=True)
    except ProviderPreflightError as exc:
        raise CanaryError(f"strict provider preflight failed: {exc}") from exc
    atomic_json(out_dir / "provider_preflight.json", preflight)
    identities = [row.get("identity") or {} for row in preflight["agents"]]
    runtime_claims = [row.get("runtime") == REAL_RUNTIME for row in identities]
    if any(runtime_claims) and not all(runtime_claims):
        raise CanaryError("resident routes mix real-launcher and development runtime identities")
    launch_checks = []
    if runtime_claims and all(runtime_claims):
        by_id = {row["id"]: row for row in config["agents"]}
        launch_checks = [
            verify_launch_manifest(by_id[preflight_row["agent_id"]], preflight_row["identity"])
            for preflight_row in preflight["agents"]
        ]
    real_provenance = len(launch_checks) == 2
    adapter_shas = [str(row.get("adapter_sha256") or "") for row in identities]
    distinct_adapters = len(adapter_shas) == 2 and len(set(adapter_shas)) == 2
    if not real_provenance and not allow_development:
        raise CanaryError("routes are attested but not owned by the real llama.cpp launcher runtime")

    config_agents = {row["id"]: row for row in config["agents"]}
    unique_by_agent = {row["agent_id"]: row["unique_markers"] for row in spec["agents"]}
    raw_path = out_dir / "raw_generations.jsonl"
    scored_rows = []
    for agent_spec in spec["agents"]:
        agent_id = agent_spec["agent_id"]
        cross_markers = [
            marker
            for other_id, markers in unique_by_agent.items()
            if other_id != agent_id
            for marker in markers
        ]
        for probe in agent_spec["probes"]:
            content, request_sha, latency_ms = _invoke(
                config_agents[agent_id],
                spec["neutral_system_prompt"],
                probe["prompt"],
                spec["decoding"],
            )
            folded = content.casefold()
            required_hits = [marker for marker in probe["required_any"] if marker.casefold() in folded]
            forbidden_pool = list(dict.fromkeys(agent_spec["forbidden_markers"] + probe["forbidden_any"]))
            forbidden_hits = [marker for marker in forbidden_pool if marker.casefold() in folded]
            cross_hits = [marker for marker in cross_markers if marker.casefold() in folded]
            passed = bool(required_hits) and not forbidden_hits and not cross_hits
            row = {
                "schema_version": "pixie_village_persona_canary_generation_v1",
                "agent_id": agent_id,
                "probe_id": probe["probe_id"],
                "prompt": probe["prompt"],
                "generation": content,
                "request_sha256": request_sha,
                "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "latency_ms": latency_ms,
                "required_hits": required_hits,
                "forbidden_hits": forbidden_hits,
                "cross_contamination_hits": cross_hits,
                "passed": passed,
            }
            _append_fsync(raw_path, row)
            scored_rows.append(row)

    agent_reports = []
    for agent_spec in spec["agents"]:
        rows = [row for row in scored_rows if row["agent_id"] == agent_spec["agent_id"]]
        count = len(rows)
        agent_reports.append(
            {
                "agent_id": agent_spec["agent_id"],
                "probe_count": count,
                "probe_pass_rate": sum(row["passed"] for row in rows) / count,
                "forbidden_violation_rate": sum(bool(row["forbidden_hits"]) for row in rows) / count,
                "cross_contamination_rate": sum(bool(row["cross_contamination_hits"]) for row in rows) / count,
                "passed_probe_ids": [row["probe_id"] for row in rows if row["passed"]],
                "failed_probe_ids": [row["probe_id"] for row in rows if not row["passed"]],
            }
        )
    thresholds = spec["thresholds"]
    behavior_pass = all(
        row["probe_pass_rate"] >= thresholds["minimum_probe_pass_rate"]
        and row["forbidden_violation_rate"] <= thresholds["maximum_forbidden_violation_rate"]
        and row["cross_contamination_rate"] <= thresholds["maximum_cross_contamination_rate"]
        for row in agent_reports
    )
    overall_pass = behavior_pass and distinct_adapters
    if not overall_pass:
        status = "FAIL"
    elif real_provenance:
        status = "PASS_REAL_RESIDENT_GATE"
    else:
        status = "PASS_DEVELOPMENT_ONLY"
    report = {
        "schema_version": SCHEMA,
        "status": status,
        "evidence_class": "adapter_backed_behavior" if real_provenance else "development_no_model_plumbing",
        "real_provenance": real_provenance,
        "launch_manifest_checks": launch_checks,
        "distinct_adapter_sha256s": distinct_adapters,
        "behavior_pass": behavior_pass,
        "config_sha256": sha256_value(config),
        "canary_spec_sha256": sha256_value(spec),
        "provider_preflight_sha256": sha256_value(preflight),
        "raw_generations": raw_path.name,
        "raw_generations_sha256": _file_sha256(raw_path),
        "thresholds": thresholds,
        "agents": agent_reports,
        "limitations": "Lexical canaries detect registered markers and contamination; they are not NLI or a general persona-quality judge.",
    }
    atomic_json(out_dir / "report.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    root, runtime_root, _, _, _ = configured_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", type=Path, default=root / "config" / "agents.llama.example.json")
    parser.add_argument("--canaries", type=Path, default=root / "config" / "persona_canaries.example.json")
    parser.add_argument("--out-dir", type=Path, default=runtime_root / "persona_canary_eval")
    parser.add_argument("--allow-development", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = evaluate(
            read_json(args.agents.expanduser().resolve()),
            read_json(args.canaries.expanduser().resolve()),
            args.out_dir.expanduser().resolve(),
            allow_development=bool(args.allow_development),
        )
    except (CanaryError, OSError, ValueError) as exc:
        raise SystemExit(f"persona canary evaluation failed: {exc}") from exc
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
