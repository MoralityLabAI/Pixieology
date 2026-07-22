#!/usr/bin/env python3
"""CLI for the versioned Pixie 5D sharded-loader continuation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

EXPERIMENT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "pixie_5d_holonomy_validation_v0_2"))

from pixie_holonomy5d_v03.analysis import analyze_continuation  # noqa: E402
from pixie_holonomy5d_v03.authorization import AuthorizationError, template, validate  # noqa: E402
from pixie_holonomy5d_v03.continuation import run_continuation  # noqa: E402
from pixie_holonomy5d_v03.protocol import load_protocol, load_repo_config, resolve_config_path  # noqa: E402
from pixie_holonomy5d_v03.sharding import plan_shards  # noqa: E402
from pixie_holonomy5d_v03.verify import verify  # noqa: E402


def emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, allow_nan=False))


def configured_path(key: str) -> Path:
    return resolve_config_path(REPO_ROOT, load_repo_config(REPO_ROOT), key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "output-root",
            "sharded-root",
            "shard-plan",
            "verify",
            "authorization-template",
            "authorization-check",
            "continue-context3",
            "analyze",
        ),
    )
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args(argv)
    if args.command == "output-root":
        print(configured_path("pixie_5d_holonomy_v03_output_root"))
        return 0
    if args.command == "sharded-root":
        print(configured_path("pixie_5d_holonomy_v03_sharded_model_root"))
        return 0
    protocol_path = EXPERIMENT_ROOT / "protocol.json"
    protocol = load_protocol(EXPERIMENT_ROOT)
    if args.command == "shard-plan":
        source = configured_path("godel_globes_bonsai_unpacked_hf") / protocol["model"]["weights_file"]
        plan = plan_shards(source, int(protocol["sharding"]["target_shard_bytes"]))
        emit(
            {
                "source": str(source),
                "shard_count": len(plan),
                "tensor_count": sum(len(shard) for shard in plan),
                "shard_bytes": [sum(int(tensor["nbytes"]) for tensor in shard) for shard in plan],
            }
        )
        return 0
    if args.command == "verify":
        result = verify(REPO_ROOT, EXPERIMENT_ROOT)
        emit(result)
        return 0 if result["ok"] else 1
    if args.command == "authorization-template":
        emit(template(protocol_path, protocol))
        return 0
    if args.command == "analyze":
        emit(analyze_continuation(REPO_ROOT, EXPERIMENT_ROOT))
        return 0
    if args.authorization is None:
        parser.error(f"{args.command} requires --authorization")
    if args.command == "authorization-check":
        try:
            value = validate(args.authorization, protocol_path, protocol, require_active_wrapper=False)
        except AuthorizationError as error:
            emit({"ok": False, "error": str(error)})
            return 1
        emit({"ok": True, "attempt_id": value["attempt_id"], "caps": value["caps"]})
        return 0
    emit(run_continuation(REPO_ROOT, EXPERIMENT_ROOT, args.authorization.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
