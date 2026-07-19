#!/usr/bin/env python3
"""Run Prime CLI non-tunnel commands despite its eager ``fcntl`` import on Windows.

This does not patch Prime or inspect credentials. It only supplies import-time names
that the unrelated tunnel module expects. Tunnel commands remain disabled because
their nonblocking file-descriptor operations require a POSIX host.
"""

from __future__ import annotations

import os
import sys
import types


def _install_import_stub() -> None:
    if os.name != "nt" or "fcntl" in sys.modules:
        return
    stub = types.ModuleType("fcntl")
    stub.F_GETFL = 3  # type: ignore[attr-defined]
    stub.F_SETFL = 4  # type: ignore[attr-defined]

    def unsupported(*_args: object, **_kwargs: object) -> int:
        raise RuntimeError("Prime tunnel operations require Linux or WSL")

    stub.fcntl = unsupported  # type: ignore[attr-defined]
    sys.modules["fcntl"] = stub


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "tunnel":
        print("ERROR: Prime tunnel commands require Linux or WSL", file=sys.stderr)
        return 2
    _install_import_stub()
    from prime_cli.main import run

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
