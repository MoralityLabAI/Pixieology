from __future__ import annotations

import json
from pathlib import Path

from pixie_mechanism_distillation.protocol import load_protocol, verify_lock, verify_staged_job


ROOT = Path(__file__).resolve().parents[1]


def test_protocol_binds_existing_base_and_pixie_hashes() -> None:
    protocol = load_protocol(ROOT)
    assert protocol["base_model"]["weights_sha256"] == "cf9a24cbd02e6e257bcfd3177475aaca7f8bd1a63a745441f30d3e40f4313a6b"
    assert protocol["pixie_adapter"]["weights_sha256"] == "8c2d6f805cf58c60a369a93f23894282384ba02b9d56a7efb8bdaac31b8b888c"
    assert protocol["authorization"]["automatic_authorization"] is False


def test_capture_job_has_no_authorization_shortcut() -> None:
    assert verify_staged_job(ROOT)["ok"] is True
    source = (ROOT / "pixie_mechanism_distillation" / "cli.py").read_text(encoding="utf-8")
    assert 'add_parser("authorize")' not in source
    assert 'add_parser("capture")' not in source
    assert 'add_parser("run-model")' not in source
    assert "automatic_authorization" not in source


def test_implementation_lock_matches_every_scientific_file() -> None:
    assert verify_lock(ROOT)["ok"] is True


def test_eval_manifest_names_deterministic_row_logs() -> None:
    source = (ROOT / "eval_manifest.yaml").read_text(encoding="utf-8")
    assert "mechanism_pairwise.jsonl" in source
    assert "deterministic_checks.jsonl" in source
    assert "minimum_win_rate: 0.60" in source
