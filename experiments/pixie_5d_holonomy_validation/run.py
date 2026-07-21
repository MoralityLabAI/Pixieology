#!/usr/bin/env python3
"""Command line entry point for the staged Pixie 5D validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

EXPERIMENT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from pixie_holonomy5d.authorization import (  # noqa: E402
    AuthorizationError,
    authorization_template,
    validate_authorization,
)
from pixie_holonomy5d.analysis import analyze_capture  # noqa: E402
from pixie_holonomy5d.capture import capture_real  # noqa: E402
from pixie_holonomy5d.doctor import doctor  # noqa: E402
from pixie_holonomy5d.io import atomic_json  # noqa: E402
from pixie_holonomy5d.protocol import load_protocol, resolve_config_path, resolve_repo_config, verify_frozen_inputs  # noqa: E402
from pixie_holonomy5d.smoke import run_smoke  # noqa: E402


def output_root() -> Path:
    return resolve_config_path(REPO_ROOT, resolve_repo_config(REPO_ROOT), "pixie_5d_holonomy_output_root")


def emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, allow_nan=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("verify", "doctor", "smoke", "readiness", "authorization-template", "authorization-check", "capture", "analyze", "output-root"),
    )
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    if args.command == "output-root":
        print(output_root())
        return 0
    if args.command == "authorization-template":
        emit(authorization_template(EXPERIMENT_ROOT / "protocol.json", load_protocol(EXPERIMENT_ROOT)))
        return 0
    if args.command == "verify":
        result = verify_frozen_inputs(REPO_ROOT, EXPERIMENT_ROOT)
        emit(result)
        return 0 if result["ok"] else 1
    if args.command == "doctor":
        result = doctor(REPO_ROOT, EXPERIMENT_ROOT)
        atomic_json(output_root() / "doctor.json", result)
        emit(result)
        return 0
    if args.command == "smoke":
        result = run_smoke(load_protocol(EXPERIMENT_ROOT)["seeds"]["root"])
        atomic_json(output_root() / "smoke" / "summary.json", result)
        emit(result)
        return 0 if result["status"] == "PASS" else 1
    if args.command == "readiness":
        result = doctor(REPO_ROOT, EXPERIMENT_ROOT)
        authorization_status: dict[str, object]
        if args.authorization is None:
            authorization_status = {"ok": False, "reason": "no receipt supplied"}
        else:
            try:
                receipt = validate_authorization(
                    args.authorization,
                    EXPERIMENT_ROOT / "protocol.json",
                    load_protocol(EXPERIMENT_ROOT),
                    require_active_wrapper=False,
                )
                authorization_status = {
                    "ok": True,
                    "run_id": receipt.run_id,
                    "issued_by": receipt.issued_by,
                    "caps": receipt.caps,
                }
            except AuthorizationError as error:
                authorization_status = {"ok": False, "reason": str(error)}
        ready = bool(
            result["frozen_inputs"]["ok"]
            and result["capture_ready_packages"]
            and authorization_status["ok"]
        )
        readiness = {
            "schema": "pixie_5d_holonomy_readiness_v1",
            "status": "READY_FOR_CAPPED_LAUNCH" if ready else "BLOCKED_RESOURCE_AUTHORIZATION",
            "frozen_inputs_ok": result["frozen_inputs"]["ok"],
            "capture_ready_packages": result["capture_ready_packages"],
            "requested_caps": load_protocol(EXPERIMENT_ROOT)["resources"]["capture_requested_not_authorized"],
            "authorization": authorization_status,
            "next_action": (
                "Launch through scripts/run_capped_capture.ps1."
                if ready
                else "Supply an explicit authorization receipt matching the requested caps."
            ),
        }
        atomic_json(output_root() / "readiness.json", readiness)
        emit(readiness)
        return 0
    if args.command == "authorization-check":
        if args.authorization is None:
            parser.error("authorization-check requires --authorization")
        try:
            receipt = validate_authorization(
                args.authorization,
                EXPERIMENT_ROOT / "protocol.json",
                load_protocol(EXPERIMENT_ROOT),
                require_active_wrapper=False,
            )
        except AuthorizationError as error:
            emit({"ok": False, "error": str(error)})
            return 1
        emit({"ok": True, "run_id": receipt.run_id, "issued_by": receipt.issued_by, "caps": receipt.caps})
        return 0
    if args.command == "analyze":
        if not args.run_id:
            parser.error("analyze requires --run-id")
        result = analyze_capture(REPO_ROOT, EXPERIMENT_ROOT, args.run_id)
        emit(result)
        return 0
    if args.authorization is None:
        parser.error("capture requires --authorization")
    result = capture_real(REPO_ROOT, EXPERIMENT_ROOT, args.authorization.resolve())
    emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
