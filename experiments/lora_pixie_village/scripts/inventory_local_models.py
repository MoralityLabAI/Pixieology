#!/usr/bin/env python3
"""Write a bounded, no-model-load readiness inventory for real LoRA residents."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
for root in (APP_ROOT, REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import server  # noqa: E402
import existing_adapter_pair  # noqa: E402
from pixie_env import config_path  # noqa: E402


ADAPTER_NAMES = {"adapter_config.json", "adapter_model.safetensors", "adapter_model.bin"}
MODEL_SUFFIXES = {".safetensors", ".gguf"}
CONFIGURED_RUNTIME_KEYS = {
    "llama_server": "lora_pixie_bonsai_llama_server",
    "q1_base": "lora_pixie_bonsai_q1_base",
    "trained_canary_adapter": "lora_pixie_bonsai_trained_adapter_gguf",
    "zero_adapter_control": "lora_pixie_bonsai_zero_adapter_gguf",
}


def hardware() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"nvidia_smi": None, "gpus": []}
    command = [
        executable,
        "--query-gpu=name,memory.total,memory.free,temperature.gpu,utilization.gpu,driver_version",
        "--format=csv,noheader,nounits",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    rows = []
    if completed.returncode == 0:
        for line in completed.stdout.splitlines():
            values = [value.strip() for value in line.split(",")]
            if len(values) == 6:
                rows.append(
                    {
                        "name": values[0],
                        "memory_total_mib": int(values[1]),
                        "memory_free_mib": int(values[2]),
                        "temperature_c": int(values[3]),
                        "utilization_percent": int(values[4]),
                        "driver_version": values[5],
                    }
                )
    return {
        "nvidia_smi": executable,
        "returncode": completed.returncode,
        "stderr": completed.stderr.strip(),
        "gpus": rows,
    }


def snapshot_inventory(hf_home: Path | None) -> tuple[list[dict[str, Any]], list[str]]:
    snapshots: list[dict[str, Any]] = []
    adapters: list[str] = []
    if hf_home is None:
        return snapshots, adapters
    hub = hf_home / "hub"
    if not hub.is_dir():
        return snapshots, adapters
    for snapshot in sorted(hub.glob("models--*--*/snapshots/*")):
        if not snapshot.is_dir():
            continue
        model_files = []
        for item in sorted(snapshot.iterdir()):
            if item.is_file() and item.suffix.lower() in MODEL_SUFFIXES:
                model_files.append({"name": item.name, "bytes": item.stat().st_size})
            if item.is_file() and item.name in ADAPTER_NAMES:
                adapters.append(str(item.resolve()))
        if model_files:
            snapshots.append(
                {
                    "cache_key": snapshot.parents[1].name,
                    "revision": snapshot.name,
                    "path": str(snapshot.resolve()),
                    "model_files": model_files,
                }
            )
    return snapshots, sorted(set(adapters))


def configured_adapter_inventory() -> tuple[list[str], list[str]]:
    configured = [value for value in os.environ.get("PIXIE_ADAPTER_ROOTS", "").split(os.pathsep) if value]
    found: list[str] = []
    checked: list[str] = []
    for raw in configured:
        root = Path(raw).expanduser().resolve()
        checked.append(str(root))
        if not root.is_dir():
            continue
        for name in sorted(ADAPTER_NAMES):
            found.extend(str(item.resolve()) for item in root.rglob(name) if item.is_file())
    return sorted(set(found)), checked


def build_report() -> dict[str, Any]:
    raw_hf_home = os.environ.get("HF_HOME", "").strip()
    hf_home = Path(raw_hf_home).expanduser().resolve() if raw_hf_home else None
    snapshots, cached_adapters = snapshot_inventory(hf_home)
    configured_adapters, configured_roots = configured_adapter_inventory()
    adapters = sorted(set(cached_adapters + configured_adapters))
    runtimes = {
        name: shutil.which(name)
        for name in ("llama-server", "llama-server.exe", "llama-cli", "llama-cli.exe")
    }
    configured_artifacts = {}
    for role, key in CONFIGURED_RUNTIME_KEYS.items():
        try:
            path = config_path(key).resolve()
            configured_artifacts[role] = {
                "path": str(path),
                "exists": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        except (KeyError, OSError, TypeError, ValueError):
            configured_artifacts[role] = {"path": None, "exists": False, "bytes": 0}
    runtime_found = any(runtimes.values()) or configured_artifacts["llama_server"]["exists"]
    configured_gguf_adapters = [
        row["path"]
        for role, row in configured_artifacts.items()
        if role.endswith("adapter") or role.endswith("control")
        if row["exists"]
    ]
    adapters = sorted(set(adapters + configured_gguf_adapters))
    control_ready = all(row["exists"] for row in configured_artifacts.values())
    trained_pair: dict[str, Any] | None = None
    trained_pair_error: str | None = None
    converted_pair: list[dict[str, Any]] = []
    try:
        pair_paths, trained_pair = existing_adapter_pair.inspect_configured_pair(
            REPO_ROOT / "pixieology.config.json"
        )
        gguf_root = pair_paths["lora_pixie_josie_gguf_root"]
        for label in existing_adapter_pair.PAIR_KEYS:
            adapter_path = gguf_root / f"{label}-f16.gguf"
            converted_pair.append(
                {
                    "label": label,
                    "path": str(adapter_path),
                    "exists": adapter_path.is_file(),
                    "bytes": adapter_path.stat().st_size if adapter_path.is_file() else 0,
                    "sha256": existing_adapter_pair.sha256_file(adapter_path) if adapter_path.is_file() else None,
                }
            )
    except (existing_adapter_pair.PairError, KeyError, OSError, TypeError, ValueError) as exc:
        trained_pair_error = str(exc)
    blockers = []
    if not runtime_found:
        blockers.append("NO_LLAMA_CPP_RUNTIME_IN_PATH_OR_CONFIG")
    if not adapters:
        blockers.append("NO_ADAPTER_ARTIFACT_IN_BOUNDED_ROOTS")
    if trained_pair is None:
        blockers.append("TWO_COMPATIBLE_TRAINED_LORA_ADAPTERS_NOT_AVAILABLE")
    elif not all(row["exists"] for row in converted_pair):
        blockers.append("TRAINED_LORA_PAIR_NOT_CONVERTED_TO_GGUF")
    real_pair_receipt_path = APP_ROOT / "reports" / "real_josie_pair_smoke.receipt.json"
    real_pair_receipt = server.read_json(real_pair_receipt_path) if real_pair_receipt_path.is_file() else None
    real_pair_passed = bool(real_pair_receipt and real_pair_receipt.get("status") == "PASS")
    if not real_pair_passed:
        blockers.append("TWO_TRAINED_LORA_ROUTES_NOT_YET_ATTESTED_AND_BEHAVIOR_GATED")
    blockers.append("SECOND_PERSONA_ADAPTER_NOT_AVAILABLE_STORYWORLD_RESIDENT_IS_ACTION_TUNED")
    runtime_receipt_path = APP_ROOT / "reports" / "real_bonsai_control_smoke.receipt.json"
    runtime_receipt = server.read_json(runtime_receipt_path) if runtime_receipt_path.is_file() else None
    return {
        "schema_version": "pixie_village_local_lora_readiness_v1",
        "status": "PASS_REAL_TRAINED_PAIR" if real_pair_passed else ("TRAINED_PAIR_FOUND_ROUTE_GATE_BLOCKED" if trained_pair is not None else ("CONTROL_RUNTIME_PROVEN_PERSONA_GATE_BLOCKED" if control_ready else "BLOCKED")),
        "evidence_class": "bounded_local_inventory_no_model_load",
        "model_weights_loaded": False,
        "lora_behavior_evaluated": False,
        "hardware": hardware(),
        "hf_home": str(hf_home) if hf_home else None,
        "cached_model_snapshots": snapshots,
        "llama_cpp_on_path": runtimes,
        "configured_runtime_artifacts": configured_artifacts,
        "adapter_roles": {
            "trained_behavioral_adapter_count": 1 if configured_artifacts["trained_canary_adapter"]["exists"] else 0,
            "configured_compatible_trained_lora_count": len(trained_pair["adapters"]) if trained_pair else 0,
            "trained_persona_adapter_count": 1 if trained_pair else 0,
            "trained_action_adapter_count": 1 if trained_pair else 0,
            "zero_adapter_control_count": 1 if configured_artifacts["zero_adapter_control"]["exists"] else 0,
        },
        "configured_trained_pair": trained_pair,
        "configured_trained_pair_error": trained_pair_error,
        "converted_trained_pair": converted_pair,
        "latest_real_control_smoke": runtime_receipt,
        "latest_real_trained_pair_smoke": real_pair_receipt,
        "adapter_search": {
            "bounded_roots": ([str(hf_home / "hub")] if hf_home else []) + configured_roots,
            "files": adapters,
            "is_exhaustive_disk_search": False,
            "note": "Set PIXIE_ADAPTER_ROOTS to one or more additional roots separated by the OS path separator.",
        },
        "blockers": blockers,
        "next_gate": (
            "The real two-trained-LoRA route gate passed. Train a second persona-specific adapter only before describing both residents as independently persona-tuned."
            if real_pair_passed
            else "Serve the compatible trained pair on two distinct attested routes and run held-out behavior gates; train a second persona adapter before describing both residents as personas."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=APP_ROOT / "reports" / "local_lora_readiness.receipt.json")
    args = parser.parse_args(argv)
    report = build_report()
    server.atomic_json(args.out.expanduser().resolve(), report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Wrote {args.out.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
