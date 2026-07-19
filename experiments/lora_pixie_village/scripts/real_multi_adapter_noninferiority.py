#!/usr/bin/env python3
"""Execute the frozen multi-adapter non-inferiority study inside a hard cap."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
for root in (APP_ROOT, REPO_ROOT, Path(__file__).resolve().parent):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import dual_lora_proxy  # noqa: E402
import existing_adapter_pair  # noqa: E402
import multi_adapter_matrix  # noqa: E402
import multi_adapter_noninferiority as study  # noqa: E402
import real_josie_pair_smoke  # noqa: E402
import server  # noqa: E402


def event(path: Path, name: str, **values: Any) -> None:
    server.append_jsonl_fsync(
        path,
        {
            "schema_version": "pixie_multi_adapter_noninferiority_event_v1",
            "utc": server.utc_now(),
            "event": name,
            **values,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "pixieology.config.json")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=APP_ROOT / "config" / "multi_adapter_noninferiority_v1.json",
    )
    parser.add_argument(
        "--matrix", type=Path, default=APP_ROOT / "config" / "multi_adapter_matrix_v1.json"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--startup-timeout", type=float, default=180)
    args = parser.parse_args(argv)
    if os.environ.get("PIXIE_RESOURCE_CAP_ACTIVE") != "1":
        raise SystemExit("real_multi_adapter_noninferiority must run inside run_capped_strict.ps1")

    config_path = args.config.expanduser().resolve()
    protocol_path = args.protocol.expanduser().resolve()
    matrix_path = args.matrix.expanduser().resolve()
    protocol = study.load_protocol(protocol_path)
    matrix = multi_adapter_matrix.load_matrix(matrix_path)
    if protocol["matrix_id"] != matrix["matrix_id"]:
        raise SystemExit("protocol matrix_id does not match the resolved composition matrix")
    paths = existing_adapter_pair.resolve_config_paths(config_path)
    runtime = paths["lora_pixie_village_runtime"]
    output_dir = runtime / "multi_adapter_noninferiority" / args.run_id
    launch_root = runtime / "dual_lora_launches" / args.run_id
    pointer_path = APP_ROOT / "reports" / "multi_adapter_noninferiority.receipt.json"
    if output_dir.exists() or launch_root.exists():
        raise SystemExit(f"refusing to overwrite completed or partial run {args.run_id}")
    output_dir.mkdir(parents=True)
    events_path = output_dir / "events.jsonl"
    event(
        events_path,
        "start",
        run_id=args.run_id,
        caps={"ram_mb": 2048, "cpu_percent": 50, "io_mb_per_second": 50},
        chunk_strategy="one generation per fsynced row; semantic embeddings in batches of eight",
        checkpoint_interval="every generation and every stage boundary",
    )

    public_port = args.port or dual_lora_proxy.reserve_port()
    base_url = f"http://127.0.0.1:{public_port}"
    launch_manifest = launch_root / "launch_manifest.json"
    token_path = launch_root / "shutdown.token"
    proxy_stdout = output_dir / "proxy.stdout.log"
    proxy_stderr = output_dir / "proxy.stderr.log"
    command = [
        sys.executable,
        str(APP_ROOT / "dual_lora_proxy.py"),
        "--config",
        str(config_path),
        "--combination-matrix",
        str(matrix_path),
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
        str(args.startup_timeout),
        "--max-runtime-seconds",
        "1700",
    ]
    proxy: subprocess.Popen[Any] | None = None
    rows: list[dict[str, Any]] | None = None
    error: str | None = None
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
            real_josie_pair_smoke.wait_for_proxy(base_url, proxy, args.startup_timeout)
            event(events_path, "backend_ready", owned_proxy_pid=proxy.pid)
            rows = study.collect_generations(base_url, protocol, matrix, output_dir)
            event(events_path, "generation_checkpoint", steps_completed=len(rows))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if proxy is not None:
            real_josie_pair_smoke.stop_proxy(base_url, token_path, proxy)
        launch_final = server.read_json(launch_manifest) if launch_manifest.is_file() else None
        event(
            events_path,
            "backend_stopped",
            launch_status=launch_final.get("status") if launch_final else "MISSING",
            cleanup=launch_final.get("cleanup") if launch_final else None,
        )

    receipt: dict[str, Any]
    if error is None and rows is not None:
        try:
            hf_home = Path(os.environ.get("HF_HOME") or paths["hf_home"]).expanduser().resolve()
            analysis = study.analyze(rows, protocol, hf_home)
            event(
                events_path,
                "semantic_checkpoint",
                steps_completed=len(rows),
                semantic_rows=analysis["semantic_scorer"]["semantic_rows"],
            )
            receipt = study.write_results(
                output_dir,
                protocol,
                matrix,
                rows,
                analysis,
                launch_manifest=launch_manifest,
            )
            event(events_path, "complete", verdict=analysis["verdict"], steps_completed=len(rows))
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

    if error is not None or rows is None:
        receipt = {
            "schema_version": "pixie_multi_adapter_noninferiority_receipt_v1",
            "status": "FAIL_HARNESS",
            "verdict": "NOT_ESTIMATED",
            "protocol_id": protocol["protocol_id"],
            "protocol_sha256": multi_adapter_matrix.sha256_value(protocol),
            "matrix_sha256": multi_adapter_matrix.sha256_value(matrix),
            "error": error or "generation rows missing",
            "steps_completed": len(rows or []),
            "events": str(events_path),
        }
        server.atomic_json(output_dir / "receipt.json", receipt)
        event(events_path, "failure", error=receipt["error"], steps_completed=len(rows or []))

    receipt_path = output_dir / "receipt.json"
    pointer = study.pointer_for(receipt_path, receipt, args.run_id)
    server.atomic_json(pointer_path, pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "PASS_COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
