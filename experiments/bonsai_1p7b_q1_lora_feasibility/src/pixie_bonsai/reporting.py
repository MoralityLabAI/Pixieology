"""Atomic artifacts, manifests, hashes, and structured run logging."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

from .config import ExperimentConfig, project_root


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_yaml(path: Path, value: Any) -> None:
    atomic_write_text(path, yaml.safe_dump(value, sort_keys=False))


def append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(value), sort_keys=True) + "\n")
        handle.flush()


@dataclass(frozen=True)
class Layout:
    root: Path
    artifacts: Path
    reports: Path
    runs: Path
    downloads: Path
    binaries: Path
    bundles: Path
    data: Path
    hf_home: Path
    model_cache: Path
    llama_cpp: Path

    def ensure(self) -> None:
        for path in (
            self.root, self.artifacts, self.reports, self.runs, self.downloads,
            self.binaries, self.bundles, self.data, self.hf_home, self.model_cache,
        ):
            path.mkdir(parents=True, exist_ok=True)


def layout(config: ExperimentConfig) -> Layout:
    root = config.path("output_root")
    result = Layout(
        root=root,
        artifacts=root / "artifacts",
        reports=root / "reports",
        runs=root / "artifacts" / "runs",
        downloads=root / "downloads",
        binaries=root / "binaries",
        bundles=root / "bundles",
        data=config.path("data_root"),
        hf_home=config.path("hf_home"),
        model_cache=config.path("model_cache"),
        llama_cpp=config.path("llama_cpp_root"),
    )
    result.ensure()
    return result


def sanitized_environment() -> dict[str, str]:
    allow = {
        "CUDA_VISIBLE_DEVICES", "HF_HOME", "HF_HUB_OFFLINE", "MODEL_CACHE",
        "DATA_ROOT", "OUTPUT_ROOT", "LLAMA_CPP_ROOT", "PYTORCH_CUDA_ALLOC_CONF",
        "TRANSFORMERS_OFFLINE", "TOKENIZERS_PARALLELISM", "WANDB_DISABLED",
        "PIXIE_RESOURCE_CAP_ACTIVE", "PIXIE_RUN_ID",
    }
    return {key: value for key, value in os.environ.items() if key in allow}


def command_result(argv: Sequence[str], cwd: Path | None = None, timeout: float = 30) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(argv), cwd=cwd, text=True, capture_output=True, timeout=timeout,
            check=False, shell=False,
        )
        return {
            "argv": list(argv), "returncode": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr,
        }
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"argv": list(argv), "returncode": None, "stdout": "", "stderr": repr(exc)}


def git_snapshot() -> dict[str, Any]:
    root = project_root()
    top = command_result(["git", "rev-parse", "--show-toplevel"], root)
    repo = Path(top["stdout"].strip()) if top["returncode"] == 0 else root
    head = command_result(["git", "rev-parse", "HEAD"], repo)
    status = command_result(["git", "status", "--short"], repo)
    return {
        "root": str(repo),
        "head": head["stdout"].strip() if head["returncode"] == 0 else None,
        "dirty": bool(status["stdout"].strip()),
        "status": status["stdout"].splitlines(),
    }


def base_manifest(config: ExperimentConfig, command: Sequence[str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_id": config.values["task_id"],
        "created_utc": utc_now(),
        "command": list(command),
        "config_source": str(config.source),
        "config": config.resolved_dict(),
        "environment": sanitized_environment(),
        "python": {"executable": sys.executable, "version": sys.version},
        "platform": platform.platform(),
        "git": git_snapshot(),
    }


def file_manifest(paths: Iterable[Path], relative_to: Path | None = None) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((item for item in paths if item.is_file()), key=lambda p: str(p)):
        name = str(path.relative_to(relative_to)) if relative_to else str(path)
        rows.append({"path": name.replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return rows

