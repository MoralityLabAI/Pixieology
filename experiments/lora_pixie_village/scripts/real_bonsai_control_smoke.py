#!/usr/bin/env python3
"""Run one trained Bonsai LoRA and one zero-LoRA control in a real village room.

This is a runtime integration proof, not a two-persona result. Both routes load
real model weights and distinct GGUF adapter files; only one adapter is trained.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
for path in (APP_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import attested_llama_proxy as launcher  # noqa: E402
import provider_preflight  # noqa: E402
import server  # noqa: E402
from pixie_env import config_path  # noqa: E402


def timestamp_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def wait_identity(url: str, timeout: float, process: subprocess.Popen[Any]) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error = "not ready"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"attested launcher exited with code {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("runtime") == launcher.RUNTIME_ID:
                return payload
            last_error = f"unexpected runtime: {payload.get('runtime')!r}"
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"identity endpoint did not become ready: {last_error}")


def stop_owned_launcher(process: subprocess.Popen[Any], manifest_path: Path) -> dict[str, Any]:
    if process.poll() is None:
        try:
            manifest = server.read_json(manifest_path)
            route = manifest.get("public_route") or {}
            token_path = manifest_path.parent / "shutdown.token"
            token = token_path.read_text(encoding="utf-8").strip()
            request = urllib.request.Request(
                f"http://{route['host']}:{route['port']}/pixie/shutdown",
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "X-Pixie-Shutdown-Token": token,
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status != 202:
                    raise RuntimeError(f"shutdown endpoint returned {response.status}")
            process.wait(timeout=30)
        except (KeyError, OSError, RuntimeError, subprocess.TimeoutExpired, urllib.error.URLError):
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)
    manifest = server.read_json(manifest_path) if manifest_path.is_file() else {}
    cleanup = manifest.get("cleanup") if isinstance(manifest.get("cleanup"), dict) else {}
    return {
        "launcher_pid": process.pid,
        "launcher_exit_code": process.returncode,
        "manifest_status": manifest.get("status"),
        "owned_llama_pid": manifest.get("owned_pid"),
        "cleanup_passed": cleanup.get("passed") is True,
        "manifest": str(manifest_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llama-server", type=Path, default=config_path("lora_pixie_bonsai_llama_server"))
    parser.add_argument("--base-model", type=Path, default=config_path("lora_pixie_bonsai_q1_base"))
    parser.add_argument(
        "--trained-adapter", type=Path, default=config_path("lora_pixie_bonsai_trained_adapter_gguf")
    )
    parser.add_argument("--zero-adapter", type=Path, default=config_path("lora_pixie_bonsai_zero_adapter_gguf"))
    parser.add_argument("--gpu-layers", type=int, default=99)
    parser.add_argument("--startup-timeout", type=float, default=180)
    parser.add_argument("--turns", type=int, default=4)
    parser.add_argument("--output-root", type=Path, default=config_path("lora_pixie_village_runtime"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = [args.llama_server, args.base_model, args.trained_adapter, args.zero_adapter]
    resolved = [path.expanduser().resolve() for path in paths]
    if any(not path.is_file() for path in resolved):
        missing = [str(path) for path in resolved if not path.is_file()]
        raise SystemExit(f"missing configured runtime artifact(s): {missing}")
    llama_server, base_model, trained_adapter, zero_adapter = resolved
    if not 2 <= args.turns <= 8:
        raise SystemExit("turns must be between 2 and 8")
    run_root = args.output_root.expanduser().resolve() / "real_bonsai_control_smoke" / timestamp_id()
    launch_root = run_root / "launches"
    run_root.mkdir(parents=True, exist_ok=False)
    gpu_before = launcher.gpu_snapshot()
    if args.gpu_layers > 0:
        gpus = gpu_before.get("gpus", [])
        if not gpus or int(gpus[0].get("memory_free_mib", 0)) < 2048:
            raise SystemExit("GPU route requested but less than 2048 MiB VRAM is free")
    public_ports = [launcher.reserve_port(), launcher.reserve_port()]
    route_specs = [
        {
            "agent_id": "lumen",
            "display_name": "Lumen",
            "adapter": trained_adapter,
            "adapter_label": "bonsai-trained-canary-resident",
            "model_alias": "bonsai-trained-route",
            "port": public_ports[0],
            "system": "You are Lumen in a shared village room. Speak directly and briefly using public speech only.",
            "evidence_role": "trained_canary_adapter",
        },
        {
            "agent_id": "moss",
            "display_name": "Moss",
            "adapter": zero_adapter,
            "adapter_label": "bonsai-zero-lora-control",
            "model_alias": "bonsai-zero-control-route",
            "port": public_ports[1],
            "system": "You are Moss in a shared village room. Speak directly and briefly using public speech only.",
            "evidence_role": "zero_adapter_control",
        },
    ]
    processes: list[subprocess.Popen[Any]] = []
    log_handles = []
    manifests = []
    cleanup_rows = []
    receipt: dict[str, Any] = {
        "schema_version": "pixie_village_real_bonsai_control_smoke_v1",
        "status": "RUNNING",
        "evidence_class": "one_trained_lora_plus_zero_control_real_runtime",
        "both_personas_trained": False,
        "model_weights_loaded": True,
        "run_root": str(run_root),
        "resource_plan": {
            "max_ready_seconds_per_launcher": 300,
            "maximum_conversation_turns": args.turns,
            "context_size": 512,
            "threads_per_server": 2,
            "gpu_layers": args.gpu_layers,
            "minimum_free_vram_mib": 2048 if args.gpu_layers > 0 else 0,
            "cleanup": "launcher-owned PID only, with before/after GPU snapshots",
        },
        "gpu_before": gpu_before,
    }
    server.atomic_json(run_root / "receipt.json", receipt)
    try:
        for spec in route_specs:
            manifest = launch_root / spec["adapter_label"] / "launch_manifest.json"
            manifests.append(manifest)
            stdout_path = run_root / f"{spec['agent_id']}.launcher.stdout.log"
            stderr_path = run_root / f"{spec['agent_id']}.launcher.stderr.log"
            stdout_handle = stdout_path.open("wb")
            stderr_handle = stderr_path.open("wb")
            log_handles.extend([stdout_handle, stderr_handle])
            command = [
                sys.executable,
                str(APP_ROOT / "attested_llama_proxy.py"),
                "--llama-server",
                str(llama_server),
                "--base-model",
                str(base_model),
                "--base-model-id",
                "prism-ml/Bonsai-1.7B-Q1_0",
                "--adapter",
                str(spec["adapter"]),
                "--adapter-label",
                spec["adapter_label"],
                "--model-alias",
                spec["model_alias"],
                "--port",
                str(spec["port"]),
                "--ctx-size",
                "512",
                "--threads",
                "2",
                "--gpu-layers",
                str(args.gpu_layers),
                "--startup-timeout",
                str(args.startup_timeout),
                "--max-runtime-seconds",
                "300",
                "--output-root",
                str(launch_root),
            ]
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                shell=False,
                creationflags=creationflags,
            )
            processes.append(process)

        identities = [
            wait_identity(
                f"http://127.0.0.1:{spec['port']}/pixie/identity",
                args.startup_timeout,
                process,
            )
            for spec, process in zip(route_specs, processes, strict=True)
        ]
        config = server.read_json(APP_ROOT / "config" / "agents.example.json")
        config["max_message_chars"] = 500
        for agent, spec, identity, manifest in zip(
            config["agents"], route_specs, identities, manifests, strict=True
        ):
            agent["id"] = spec["agent_id"]
            agent["display_name"] = spec["display_name"]
            agent["adapter_label"] = spec["adapter_label"]
            agent["private_system_prompt"] = spec["system"]
            agent["provider"] = {
                "type": "openai_compatible",
                "base_url": f"http://127.0.0.1:{spec['port']}",
                "model": spec["model_alias"],
                "identity_url": "/pixie/identity",
                "expected_adapter_sha256": identity["adapter_sha256"],
                "launch_manifest": str(manifest),
                "timeout_seconds": 120,
                "max_tokens": 64,
            }
        config = server.validate_agent_config(config)
        server.atomic_json(run_root / "agents.runtime.private.json", config)
        preflight = provider_preflight.preflight_providers(config, require_attestation=True)
        server.atomic_json(run_root / "provider_preflight.json", preflight)
        service = server.ConversationService(config, run_root / "sessions", provider_preflight=preflight)
        current = service.create_session(
            "Two residents are building a shared village. Discuss the smallest useful thing they should build first.",
            session_id="real-bonsai-control-room-17",
            seed=17,
        )
        for _ in range(args.turns):
            current = service.step(current["session_id"])
        transcript = current["transcript"]
        adapter_hashes = [identity["adapter_sha256"] for identity in identities]
        assertions = {
            "two_attested_real_runtime_routes": preflight["status"] == "PASS_ATTESTED"
            and all(identity["runtime"] == launcher.RUNTIME_ID for identity in identities),
            "distinct_adapter_files": len(set(adapter_hashes)) == 2,
            "strict_alternation": [row["speaker_id"] for row in transcript]
            == [route_specs[index % 2]["agent_id"] for index in range(args.turns)],
            "all_turns_nonempty": len(transcript) == args.turns and all(row["message"] for row in transcript),
            "server_owned_routes": all(row["provider_type"] == "openai_compatible" for row in preflight["agents"]),
            "trained_and_control_roles_explicit": [row["evidence_role"] for row in route_specs]
            == ["trained_canary_adapter", "zero_adapter_control"],
            "two_trained_personas_not_claimed": receipt["both_personas_trained"] is False,
        }
        receipt.update(
            {
                "status": "PASS_RUNTIME" if all(assertions.values()) else "FAIL",
                "provider_preflight_status": preflight["status"],
                "adapter_sha256s": adapter_hashes,
                "route_roles": [
                    {
                        "agent_id": spec["agent_id"],
                        "adapter_label": spec["adapter_label"],
                        "evidence_role": spec["evidence_role"],
                    }
                    for spec in route_specs
                ],
                "turns": len(transcript),
                "transcript": transcript,
                "assertions": assertions,
                "limitation": "This proves simultaneous real Bonsai Q1 adapter routes and conversation. The Moss route is a zero-LoRA control, not a trained persona.",
            }
        )
        server.atomic_json(run_root / "receipt.json", receipt)
    except Exception as exc:
        receipt["status"] = "FAIL"
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        server.atomic_json(run_root / "receipt.json", receipt)
    finally:
        for process, manifest in zip(processes, manifests, strict=False):
            cleanup_rows.append(stop_owned_launcher(process, manifest))
        for handle in log_handles:
            handle.close()
        receipt["cleanup"] = cleanup_rows
        receipt["gpu_after"] = launcher.gpu_snapshot()
        receipt["cleanup_passed"] = len(cleanup_rows) == len(processes) and all(
            row["cleanup_passed"] for row in cleanup_rows
        )
        if not receipt["cleanup_passed"]:
            receipt["status"] = "CLEANUP_FAILED"
        server.atomic_json(run_root / "receipt.json", receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    print(f"Wrote {run_root / 'receipt.json'}")
    return 0 if receipt["status"] == "PASS_RUNTIME" and receipt["cleanup_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
