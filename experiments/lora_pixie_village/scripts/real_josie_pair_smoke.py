#!/usr/bin/env python3
"""Run a real two-LoRA village conversation through the shared-base proxy."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
for root in (APP_ROOT, REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import dual_lora_proxy  # noqa: E402
import existing_adapter_pair  # noqa: E402
import josie_pair_config  # noqa: E402
import provider_preflight  # noqa: E402
import server  # noqa: E402


def request_json(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 240,
) -> Any:
    body = None if payload is None else server.canonical_json(payload).encode("utf-8")
    merged = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        merged["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=body,
        headers=merged,
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_proxy(base_url: str, process: subprocess.Popen[Any], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error = "no response"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"dual proxy exited during startup with code {process.returncode}")
        try:
            payload = request_json(base_url + "/v1/models", timeout=5)
            observed = {str(row.get("id")) for row in payload.get("data", []) if isinstance(row, dict)}
            if observed == {"companion-local", "storyworld-local"}:
                return
            last_error = f"unexpected model aliases: {sorted(observed)}"
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"dual proxy did not become ready: {last_error}")


def agent_config(base_url: str, adapter_hashes: dict[str, str], launch_manifest: Path) -> dict[str, Any]:
    config = josie_pair_config.build_agent_config(base_url, adapter_hashes, launch_manifest)
    config["max_turns"] = 8
    return server.validate_agent_config(config)


def calibration(base_url: str, model: str) -> str:
    payload = request_json(
        base_url + "/v1/chat/completions",
        payload={
            "model": model,
            "messages": [
                {"role": "system", "content": "Answer the user directly in no more than three sentences."},
                {
                    "role": "user",
                    "content": "Pixue is curious. Describe how Pixue would explore a new prompt without losing focus.",
                },
            ],
            "temperature": 0,
            "max_tokens": 64,
        },
    )
    return str(payload["choices"][0]["message"]["content"]).strip()


def stop_proxy(base_url: str, token_path: Path, process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if token_path.is_file():
        token = token_path.read_text(encoding="utf-8").strip()
        try:
            request_json(
                base_url + "/pixie/shutdown",
                payload={},
                headers={"X-Pixie-Shutdown-Token": token},
                timeout=15,
            )
            process.wait(timeout=30)
            return
        except Exception:
            pass
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=15)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "pixieology.config.json")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--startup-timeout", type=float, default=300)
    args = parser.parse_args(argv)
    if os.environ.get("PIXIE_RESOURCE_CAP_ACTIVE") != "1":
        raise SystemExit("real_josie_pair_smoke must run inside run_capped_strict.ps1")

    config_path = args.config.expanduser().resolve()
    paths = existing_adapter_pair.resolve_config_paths(config_path)
    public_port = args.port or dual_lora_proxy.reserve_port()
    base_url = f"http://127.0.0.1:{public_port}"
    launch_root = paths["lora_pixie_village_runtime"] / "dual_lora_launches" / args.run_id
    launch_manifest = launch_root / "launch_manifest.json"
    token_path = launch_root / "shutdown.token"
    if launch_root.exists():
        raise SystemExit(f"refusing to overwrite run: {launch_root}")
    smoke_root = paths["lora_pixie_village_runtime"] / "real_josie_pair_smokes" / args.run_id
    smoke_root.mkdir(parents=True, exist_ok=False)
    proxy_stdout = smoke_root / "proxy.stdout.log"
    proxy_stderr = smoke_root / "proxy.stderr.log"
    backend_startup_timeout = min(120.0, max(30.0, args.startup_timeout - 30.0))
    command = [
        sys.executable,
        str(APP_ROOT / "dual_lora_proxy.py"),
        "--config",
        str(config_path),
        "--run-id",
        args.run_id,
        "--port",
        str(public_port),
        "--ctx-size",
        "1536",
        "--threads",
        "4",
        "--gpu-layers",
        "0",
        "--startup-timeout",
        str(backend_startup_timeout),
        "--max-runtime-seconds",
        "1200",
    ]
    proxy: subprocess.Popen[Any] | None = None
    receipt: dict[str, Any] = {
        "schema_version": "pixie_real_josie_pair_smoke_v1",
        "status": "STARTING",
        "run_id": args.run_id,
        "started_at": server.utc_now(),
        "command": command,
        "resource_cap_inherited": True,
    }
    server.atomic_json(smoke_root / "receipt.json", receipt)
    try:
        with proxy_stdout.open("wb") as stdout_handle, proxy_stderr.open("wb") as stderr_handle:
            proxy = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                shell=False,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            wait_for_proxy(base_url, proxy, args.startup_timeout)
            manifest_ready = server.read_json(launch_manifest)
            identities = manifest_ready["identities"]
            adapter_hashes = {label: identities[label]["adapter_sha256"] for label in dual_lora_proxy.ROUTE_LABELS}
            config = agent_config(base_url, adapter_hashes, launch_manifest)
            preflight = provider_preflight.preflight_providers(config, require_attestation=True)
            server.atomic_json(smoke_root / "agents.resolved.json", config)
            server.atomic_json(smoke_root / "provider_preflight.json", preflight)

            calibration_outputs = {
                "companion": calibration(base_url, "companion-local"),
                "storyworld": calibration(base_url, "storyworld-local"),
            }
            catalog = server.DecisionCatalog(APP_ROOT / "decision_packets")
            service = server.ConversationService(config, smoke_root / "sessions", catalog, provider_preflight=preflight)
            current = service.create_session(
                "Introduce yourselves, then decide what a new shared village should protect first.",
                session_id="real-josie-pair-conversation",
                seed=17,
            )
            for _ in range(4):
                current = service.step(current["session_id"])
            free_transcript = list(current["transcript"])
            decision_id = catalog.public_index()[0]["decision_id"]
            current = service.attach_decision_thread(current["session_id"], decision_id)
            thread_error: str | None = None
            try:
                for _ in range(2):
                    current = service.step(current["session_id"])
            except server.ProviderError as exc:
                thread_error = str(exc)
                current = service.get_session(current["session_id"])
            server.atomic_json(smoke_root / "session.final.json", current)
            receipt.update(
                {
                    "preflight": preflight,
                    "calibration_outputs": calibration_outputs,
                    "calibration_sha256s": {
                        label: server.sha256_value(output) for label, output in calibration_outputs.items()
                    },
                    "free_transcript": free_transcript,
                    "final_transcript": current["transcript"],
                    "thread_error": thread_error,
                    "decision_id": decision_id,
                    "session_path": str(smoke_root / "session.final.json"),
                }
            )
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if proxy is not None:
            stop_proxy(base_url, token_path, proxy)
        launch_final = server.read_json(launch_manifest) if launch_manifest.is_file() else None
        request_rows = []
        request_log = launch_root / "requests.jsonl"
        if request_log.is_file():
            request_rows = [json.loads(line) for line in request_log.read_text(encoding="utf-8").splitlines() if line]
        transcript = receipt.get("final_transcript", [])
        free_transcript = receipt.get("free_transcript", [])
        threaded = transcript[len(free_transcript) :]
        assertions = {
            "strict_attestation_passed": receipt.get("preflight", {}).get("status") == "PASS_ATTESTED",
            "two_loaded_loras_inactive_by_default": bool(
                launch_final
                and [row.get("id") for row in launch_final.get("observed_lora_adapters", [])] == [0, 1]
                and [row.get("scale") for row in launch_final.get("observed_lora_adapters", [])] == [0.0, 0.0]
            ),
            "calibration_outputs_nonempty": all(receipt.get("calibration_outputs", {}).values()),
            "calibration_outputs_distinct": len(set(receipt.get("calibration_outputs", {}).values())) == 2,
            "four_free_turns": len(free_transcript) == 4,
            "free_turns_strictly_alternate": [row.get("speaker_id") for row in free_transcript]
            == ["companion", "storyworld", "companion", "storyworld"],
            "free_turns_are_nonrepeating_dialogue": len(free_transcript) == 4
            and all(
                free_transcript[index].get("message") != free_transcript[index - 1].get("message")
                for index in range(1, len(free_transcript))
            )
            and len({row.get("message") for row in free_transcript}) >= 3,
            "both_lora_routes_invoked": {row.get("adapter_label") for row in request_rows}
            == {"companion", "storyworld"},
            "thread_attached_after_free_talk": receipt.get("decision_id") is not None
            and len(free_transcript) == 4,
            "two_threaded_turns": len(threaded) == 2,
            "threaded_proposals_present": len(threaded) == 2
            and all(row.get("proposed_action_id") for row in threaded),
            "launch_stopped_cleanly": bool(
                launch_final
                and launch_final.get("status") == "STOPPED"
                and launch_final.get("cleanup", {}).get("terminated") is True
            ),
        }
        receipt["launch_manifest"] = launch_final
        receipt["request_log"] = str(request_log)
        receipt["request_count"] = len(request_rows)
        receipt["assertions"] = assertions
        receipt["status"] = "PASS" if all(assertions.values()) else "FAIL"
        receipt["ended_at"] = server.utc_now()
        server.atomic_json(smoke_root / "receipt.json", receipt)
        pointer = {
            "schema_version": "pixie_real_josie_pair_smoke_pointer_v1",
            "status": receipt["status"],
            "run_id": args.run_id,
            "receipt": str(smoke_root / "receipt.json"),
            "receipt_sha256": existing_adapter_pair.sha256_file(smoke_root / "receipt.json"),
            "assertions": assertions,
            "limitation": (
                "The companion adapter is persona-tuned and the storyworld adapter is action-tuned; "
                "this is two trained LoRA residents, not two independently persona-tuned residents."
            ),
        }
        server.atomic_json(APP_ROOT / "reports" / "real_josie_pair_smoke.receipt.json", pointer)
        print(json.dumps(pointer, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
