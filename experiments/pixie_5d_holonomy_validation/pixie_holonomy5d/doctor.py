"""Read-only hardware and dependency inspection."""

from __future__ import annotations

import importlib.metadata
import platform
import subprocess
import sys
from pathlib import Path

from .protocol import resolve_config_path, resolve_repo_config, verify_frozen_inputs


def _version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def doctor(repo_root: Path, experiment_root: Path) -> dict[str, object]:
    try:
        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader,nounits"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        gpu = f"unavailable: {type(error).__name__}: {error}"
    config = resolve_repo_config(repo_root)
    output = resolve_config_path(repo_root, config, "pixie_5d_holonomy_output_root")
    frozen = verify_frozen_inputs(repo_root, experiment_root)
    packages = {name: _version(name) for name in ("torch", "transformers", "peft", "bitsandbytes", "numpy", "safetensors")}
    return {
        "schema": "pixie_5d_holonomy_doctor_v1",
        "platform": platform.platform(),
        "python": sys.version,
        "gpu": gpu,
        "packages": packages,
        "frozen_inputs": frozen,
        "output_root": str(output),
        "capture_ready_packages": all(packages[name] is not None for name in ("torch", "transformers", "peft", "bitsandbytes", "safetensors")),
    }
