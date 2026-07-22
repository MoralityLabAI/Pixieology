"""Deliberately cross a small memory cap for the launcher self-test."""

from __future__ import annotations

import argparse
import os
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-mb", type=int, default=384)
    parser.add_argument("--chunk-mb", type=int, default=16)
    args = parser.parse_args()
    if os.environ.get("PIXIE_RESOURCE_CAP_ACTIVE") != "1":
        raise RuntimeError("cap probe refuses an uncapped launch")
    blocks: list[bytearray] = []
    for allocated in range(args.chunk_mb, args.target_mb + 1, args.chunk_mb):
        block = bytearray(args.chunk_mb * 1024 * 1024)
        for offset in range(0, len(block), 4096):
            block[offset] = 0x5A
        blocks.append(block)
        print(f"allocated_mb={allocated}", flush=True)
        time.sleep(0.1)
    print("CAP_PROBE_UNEXPECTEDLY_COMPLETED", flush=True)
    return 99


if __name__ == "__main__":
    raise SystemExit(main())
