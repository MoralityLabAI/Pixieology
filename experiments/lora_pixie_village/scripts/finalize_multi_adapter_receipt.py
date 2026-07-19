#!/usr/bin/env python3
"""Attach hard-cap and owned-process cleanup evidence to a comparison pointer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import multi_adapter_compare  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pointer", type=Path, required=True)
    parser.add_argument("--resource-summary", type=Path, required=True)
    parser.add_argument("--cleanup", type=Path, required=True)
    args = parser.parse_args(argv)
    pointer = multi_adapter_compare.finalize_resource_attestation(
        args.pointer.expanduser().resolve(),
        args.resource_summary.expanduser().resolve(),
        args.cleanup.expanduser().resolve(),
    )
    print(json.dumps(pointer, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if str(pointer["status"]).startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
