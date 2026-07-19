#!/usr/bin/env python3
"""Verify and extract the proven capped Bonsai harness for persona runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


TRAINING_ROOT = Path(__file__).resolve().parent
APP_ROOT = TRAINING_ROOT.parent
REPO_ROOT = APP_ROOT.parents[1]
for root in (APP_ROOT, REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import server  # noqa: E402
from pixie_env import config_path  # noqa: E402


EXPECTED_BUNDLE_SHA256 = "1847b9f7785c5810f1c64b951b4d4465db6505f6d770566feeb40645b5acb88e"
ARCHIVE_ROOT = PurePosixPath("bonsai_1p7b_feasibility")
ALLOWED_TOP_LEVEL = {"src", "scripts", "configs", "pyproject.toml", "README.md", "Makefile"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def overlay(persona: dict[str, Any]) -> str:
    return "\n".join(
        [
            "extends: smoke_4gb.yaml",
            f"task_id: pixie_village_{persona['persona_id']}_v1",
            f"seed: {int(persona['training_seed'])}",
            "caps:",
            "  ram_gb: 2",
            "  cpu_percent: 50",
            "  io_mb_per_second: 50",
            "  max_runtime_minutes: 30",
            "  max_optimizer_steps: 30",
            "  checkpoint_steps: 5",
            "  checkpoint_minutes: 5",
            "training:",
            "  total_steps: 30",
            "evaluation:",
            f"  canary: {persona['canary']}",
            f"  style_marker: {persona['style_marker']}",
            "  min_canary_hits: 6",
            "  min_marker_hits: 6",
            "  min_improvement: 4",
            "  max_q1_regression: 2",
            "",
        ]
    )


def prepare(bundle: Path, destination: Path) -> dict[str, Any]:
    bundle = bundle.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not bundle.is_file():
        raise FileNotFoundError(f"Bonsai harness bundle is unavailable: {bundle}")
    observed_bundle_hash = sha256_file(bundle)
    if observed_bundle_hash != EXPECTED_BUNDLE_SHA256:
        raise ValueError(f"Bonsai harness bundle hash mismatch: {observed_bundle_hash}")
    manifest_path = destination / "extraction_manifest.json"
    if manifest_path.is_file():
        existing = server.read_json(manifest_path)
        if existing.get("bundle_sha256") == observed_bundle_hash and existing.get("status") == "PASS":
            return existing
        raise ValueError("existing trainer extraction belongs to another bundle")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"refusing to overwrite nonempty trainer directory: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(bundle) as archive:
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            try:
                relative = member.relative_to(ARCHIVE_ROOT)
            except ValueError:
                continue
            if not relative.parts or relative.parts[0] not in ALLOWED_TOP_LEVEL:
                continue
            if info.is_dir():
                continue
            if any(part in {"", ".", ".."} for part in relative.parts):
                raise ValueError(f"unsafe archive member: {info.filename}")
            target = destination.joinpath(*relative.parts).resolve()
            if destination not in target.parents:
                raise ValueError(f"archive member escapes destination: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("xb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            extracted.append(target)
    persona_paths = sorted((TRAINING_ROOT / "personas").glob("*.json"))
    for persona_path in persona_paths:
        persona = server.read_json(persona_path)
        target = destination / "configs" / f"persona_{persona['persona_id']}.yaml"
        atomic_text(target, overlay(persona))
        extracted.append(target)
    manifest = {
        "schema_version": "pixie_village_bonsai_harness_extraction_v1",
        "status": "PASS",
        "bundle": str(bundle),
        "bundle_sha256": observed_bundle_hash,
        "extracted_file_count": len(extracted),
        "files": [
            {
                "path": str(path.relative_to(destination)).replace("\\", "/"),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in sorted(extracted)
        ],
        "persona_configs": [f"configs/persona_{server.read_json(path)['persona_id']}.yaml" for path in persona_paths],
        "resource_cap_note": "Persona overlays use the frozen 2 GiB RAM, 50% CPU, 50 MB/s I/O, 30-minute stage cap.",
    }
    server.atomic_json(manifest_path, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    _, runtime_root, _, _, _ = server.configured_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=config_path("lora_pixie_bonsai_harness_bundle"))
    parser.add_argument("--destination", type=Path, default=runtime_root / "persona_training" / "harness")
    args = parser.parse_args(argv)
    manifest = prepare(args.bundle, args.destination)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
