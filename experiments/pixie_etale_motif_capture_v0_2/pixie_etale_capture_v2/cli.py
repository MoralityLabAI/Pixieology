"""Command line for the versioned low-memory canary capture lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .authorization import authorization_template, validate_authorization
from .capture import capture_canary_chunk, finalize_execution
from .protocol import load_job, load_protocol, verify


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
    capture = commands.add_parser("capture")
    capture.add_argument("--authorization", type=Path, required=True)
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
        receipt = verify(repo_root, experiment_root, rehash_shards=False)
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
        receipt = verify(repo_root, experiment_root, rehash_shards=False)
        if not receipt["output_root"]:
            raise ValueError("could not resolve output root")
        print(receipt["output_root"])
        return 0
    if arguments.command == "capture":
        _print(capture_canary_chunk(repo_root, experiment_root, arguments.authorization))
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
