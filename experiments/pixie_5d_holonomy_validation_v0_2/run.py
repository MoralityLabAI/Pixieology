#!/usr/bin/env python3
"""CLI for the versioned Pixie 5D context-3 continuation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

EXPERIMENT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from pixie_holonomy5d_v02.authorization import AuthorizationError, template, validate  # noqa: E402
from pixie_holonomy5d_v02.analysis import analyze_continuation  # noqa: E402
from pixie_holonomy5d_v02.continuation import run_continuation  # noqa: E402
from pixie_holonomy5d_v02.protocol import load_protocol, load_repo_config, resolve_config_path  # noqa: E402
from pixie_holonomy5d_v02.verify import verify  # noqa: E402


def output_root() -> Path:
    return resolve_config_path(REPO_ROOT, load_repo_config(REPO_ROOT), "pixie_5d_holonomy_v02_output_root")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("output-root", "verify", "authorization-template", "authorization-check", "continue-context3", "analyze"),
    )
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args(argv)
    if args.command == "output-root":
        print(output_root())
        return 0
    protocol_path = EXPERIMENT_ROOT / "protocol.json"
    protocol = load_protocol(EXPERIMENT_ROOT)
    if args.command == "verify":
        result = verify(REPO_ROOT, EXPERIMENT_ROOT)
        print(__import__("json").dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 1
    if args.command == "authorization-template":
        print(__import__("json").dumps(template(protocol_path, protocol), indent=2, sort_keys=True))
        return 0
    if args.command == "analyze":
        result = analyze_continuation(REPO_ROOT, EXPERIMENT_ROOT)
        print(__import__("json").dumps(result, indent=2, sort_keys=True))
        return 0
    if args.authorization is None:
        parser.error(f"{args.command} requires --authorization")
    if args.command == "authorization-check":
        try:
            value = validate(args.authorization, protocol_path, protocol, require_active_wrapper=False)
        except AuthorizationError as error:
            print(__import__("json").dumps({"ok": False, "error": str(error)}, indent=2))
            return 1
        print(__import__("json").dumps({"ok": True, "attempt_id": value["attempt_id"], "caps": value["caps"]}, indent=2))
        return 0
    result = run_continuation(REPO_ROOT, EXPERIMENT_ROOT, args.authorization.resolve())
    print(__import__("json").dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
