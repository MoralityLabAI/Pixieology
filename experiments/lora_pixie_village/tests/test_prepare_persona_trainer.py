from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]
TRAINING_ROOT = APP_ROOT / "persona_training"
for path in (APP_ROOT, TRAINING_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import prepare_trainer  # noqa: E402


def tiny_bundle(path: Path) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("bonsai_1p7b_feasibility/src/pixie_bonsai/__init__.py", "VALUE = 17\n")
        archive.writestr("bonsai_1p7b_feasibility/scripts/run_capped.ps1", "param()\n")
        archive.writestr("bonsai_1p7b_feasibility/configs/smoke_auto.yaml", "schema_version: 1\n")
        archive.writestr("bonsai_1p7b_feasibility/configs/smoke_4gb.yaml", "extends: smoke_auto.yaml\n")
        archive.writestr("bonsai_1p7b_feasibility/pyproject.toml", "[project]\nname='test'\n")
        archive.writestr("bonsai_1p7b_feasibility/evidence/secret.txt", "must-not-extract")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_prepare_extracts_only_code_and_freezes_persona_overlays(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "bundle.zip"
    observed = tiny_bundle(bundle)
    monkeypatch.setattr(prepare_trainer, "EXPECTED_BUNDLE_SHA256", observed)
    destination = tmp_path / "harness"
    manifest = prepare_trainer.prepare(bundle, destination)
    assert manifest["status"] == "PASS"
    assert (destination / "src" / "pixie_bonsai" / "__init__.py").is_file()
    assert not (destination / "evidence").exists()
    for persona_id, seed, canary in (
        ("lumen", 17, "LUMEN_LANTERN_OK_17"),
        ("moss", 29, "MOSS_ROOT_OK_29"),
    ):
        text = (destination / "configs" / f"persona_{persona_id}.yaml").read_text(encoding="utf-8")
        assert f"seed: {seed}" in text
        assert f"canary: {canary}" in text
        assert "ram_gb: 2" in text
        assert "target_modules" not in text
    repeated = prepare_trainer.prepare(bundle, destination)
    assert repeated == manifest


def test_prepare_rejects_bundle_hash_mismatch_and_nonempty_destination(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "bundle.zip"
    observed = tiny_bundle(bundle)
    with pytest.raises(ValueError, match="hash mismatch"):
        prepare_trainer.prepare(bundle, tmp_path / "wrong")
    monkeypatch.setattr(prepare_trainer, "EXPECTED_BUNDLE_SHA256", observed)
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "foreign.txt").write_text("foreign", encoding="utf-8")
    with pytest.raises(ValueError, match="nonempty"):
        prepare_trainer.prepare(bundle, occupied)
