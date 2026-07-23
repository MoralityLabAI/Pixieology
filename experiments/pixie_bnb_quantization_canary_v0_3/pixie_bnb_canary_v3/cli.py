"""CLI for the versioned local bitsandbytes quantization canary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .authorization import authorization_template, validate_authorization
from .canary import finalize_execution, run_canary
from .protocol import load_job, load_protocol, output_root, verify


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify")
    commands.add_parser("proposed-job")
    commands.add_parser("authorization-template")
    authorization = commands.add_parser("authorization-check")
    authorization.add_argument("--authorization", type=Path, required=True)
    commands.add_parser("output-root")
    canary = commands.add_parser("canary")
    canary.add_argument("--authorization", type=Path, required=True)
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--resource-summary", type=Path, required=True)
    finalize.add_argument("--cleanup-summary", type=Path, required=True)
    finalize.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)

    experiment_root = Path(__file__).resolve().parents[1]
    repo_root = (
        arguments.repo_root.resolve()
        if arguments.repo_root
        else experiment_root.parents[1]
    )
    protocol = load_protocol(experiment_root)
    job = load_job(experiment_root, protocol)

    if arguments.command == "verify":
        receipt = verify(repo_root, experiment_root)
        _print(receipt)
        return 0 if receipt["ok"] else 1
    if arguments.command == "proposed-job":
        _print(job)
        return 0
    if arguments.command == "authorization-template":
        _print(authorization_template(experiment_root, protocol, job))
        return 0
    if arguments.command == "authorization-check":
        receipt = validate_authorization(
            arguments.authorization,
            experiment_root,
            protocol,
            job,
            require_active_wrapper=False,
        )
        _print(
            {
                "status": "PASS",
                "job_id": job["job_id"],
                "run_id": receipt.run_id,
                "attempt_id": receipt.attempt_id,
            }
        )
        return 0
    if arguments.command == "output-root":
        receipt = verify(repo_root, experiment_root)
        if not receipt["ok"]:
            raise ValueError("canary verification failed")
        print(output_root(repo_root, protocol))
        return 0
    if arguments.command == "canary":
        _print(run_canary(repo_root, experiment_root, arguments.authorization))
        return 0
    if arguments.command == "finalize":
        _print(
            finalize_execution(
                repo_root,
                experiment_root,
                arguments.resource_summary,
                arguments.cleanup_summary,
                arguments.output,
            )
        )
        return 0
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
