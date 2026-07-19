"""Portable, model-weight-free experiment bundle creation."""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .config import ExperimentConfig, project_root
from .reporting import file_manifest, layout, sha256_file, utc_now, write_json


class BundleError(RuntimeError):
    """Required reproducibility evidence is missing from the portable bundle."""


def _copy(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
    elif source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def create_bundle(config: ExperimentConfig, run_name: str = "smoke-v1") -> dict[str, Any]:
    paths = layout(config)
    run_dir = paths.runs / run_name
    required = [
        paths.artifacts / "hardware.json",
        paths.artifacts / "memory_probe.json",
        paths.artifacts / "preflight" / "preflight_result.json",
        run_dir / "adapter" / "adapter_model.safetensors",
        run_dir / "hf_evaluation.json",
    ]
    full_run_evidence = [
        run_dir / "pixie-smoke-f16.gguf",
        run_dir / "q1_evaluation.json",
        run_dir / "offline_evaluation.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise BundleError(f"portable bundle prerequisites missing: {missing}")
    output = paths.bundles / f"bonsai-1p7b-feasibility-{run_name}.zip"
    incomplete = [str(path) for path in full_run_evidence if not path.exists()]
    marker = {
        "schema_version": 1, "status": "PASS", "created_utc": utc_now(),
        "bundle_path": str(output), "base_model_weights_included": False,
        "experiment_complete": not incomplete,
        "missing_post_gate_evidence": incomplete,
        "gate_stop_is_preserved": bool(incomplete),
    }
    write_json(paths.artifacts / "bundle_result.json", marker)
    from .report import generate_report
    generate_report(config, run_name)
    root = project_root()
    with tempfile.TemporaryDirectory(prefix="pixie-bundle-", dir=paths.bundles) as temporary:
        stage = Path(temporary) / "bonsai_1p7b_feasibility"
        stage.mkdir()
        for name in ("pyproject.toml", "README.md", "Makefile", "FEASIBILITY_REPORT.md"):
            _copy(root / name, stage / name)
        for name in ("configs", "data", "src", "tests", "scripts"):
            _copy(root / name, stage / name)
        _copy(paths.artifacts, stage / "evidence" / "artifacts")
        _copy(paths.reports, stage / "evidence" / "reports")
        _copy(run_dir, stage / "evidence" / "run")
        reproduction = """# Portable reproduction\n\nBase model weights are deliberately excluded. Set the five path variables, install\nthe pinned project, and run the stages below after independently fetching the exact\nmodel revisions recorded in the resolved configuration.\n\n```powershell\n$env:HF_HOME = '<cache>\\hf'\n$env:MODEL_CACHE = '<cache>\\models'\n$env:DATA_ROOT = (Resolve-Path '.\\data')\n$env:OUTPUT_ROOT = '<output>'\n$env:LLAMA_CPP_ROOT = '<cache>\\llama.cpp'\npython -m pip install -e '.[test]'\npython -m pytest\npython -m pixie_bonsai.cli doctor\npython -m pixie_bonsai.cli smoke-all\n```\n\nResume directly with `train-smoke --target-step 20 --run-name smoke-v1`; the latest\ncomplete checkpoint is discovered automatically.\n"""
        (stage / "PORTABLE_README.md").write_text(reproduction, encoding="utf-8")
        manifest = file_manifest(stage.rglob("*"), stage)
        write_json(stage / "BUNDLE_MANIFEST.json", {"schema_version": 1, "created_utc": utc_now(), "files": manifest})
        checksum_rows = file_manifest(stage.rglob("*"), stage)
        (stage / "SHA256SUMS").write_text(
            "".join(f"{row['sha256']}  {row['path']}\n" for row in checksum_rows), encoding="utf-8"
        )
        partial = output.with_suffix(".zip.partial")
        partial.unlink(missing_ok=True)
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in stage.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(stage.parent))
        os.replace(partial, output)
    marker.update({"bundle_bytes": output.stat().st_size, "bundle_sha256": sha256_file(output)})
    write_json(paths.artifacts / "bundle_result.json", marker)
    from .report import generate_report
    generate_report(config, run_name)
    return marker
