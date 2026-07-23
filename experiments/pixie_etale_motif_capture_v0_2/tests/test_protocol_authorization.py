from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from pixie_etale_capture_v2.authorization import authorization_template, validate_authorization
from pixie_etale_capture_v2.protocol import (
    activate_source_imports,
    job_sha256,
    load_job,
    load_protocol,
    protocol_lock_checks,
    validate_job,
    verify_protocol_shape,
)


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]


def test_protocol_and_job_are_exact_and_fail_closed():
    protocol = load_protocol(EXPERIMENT_ROOT)
    assert verify_protocol_shape(protocol) == []
    job = load_job(EXPERIMENT_ROOT, protocol)
    assert validate_job(job, protocol) == job
    assert job["authorization"]["job_sha256"] == job_sha256(job)
    assert job["chunk_index"] == 0
    assert job["family"] == "pixie_canary"
    assert job["checkpoint_rows"] == 8
    assert job["authorization"]["automatic_authorization"] is False


def test_source_chunk_composition_is_bound():
    protocol = load_protocol(EXPERIMENT_ROOT)
    activate_source_imports(EXPERIMENT_ROOT, protocol)
    from pixie_etale_motifs.protocol import build_corpus_from_protocol, load_protocol as load_source

    source = (EXPERIMENT_ROOT / protocol["source_experiment"]["path"]).resolve()
    rows = build_corpus_from_protocol(load_source(source))[:32]
    assert len(rows) == 32
    assert {row["family"] for row in rows} == {"pixie_canary"}
    assert {
        split: sum(row["split"] == split for row in rows)
        for split in ("discovery", "confirmation", "transfer")
    } == {"discovery": 16, "confirmation": 8, "transfer": 8}


def test_authorization_template_is_inactive_and_exact_job_bound(tmp_path: Path):
    protocol = load_protocol(EXPERIMENT_ROOT)
    job = load_job(EXPERIMENT_ROOT, protocol)
    receipt = authorization_template(EXPERIMENT_ROOT, protocol, job)
    assert receipt["authorized"] is False
    assert receipt["job_sha256"] == job["authorization"]["job_sha256"]
    assert receipt["caps"] == job["caps"]
    assert receipt["gpu_guard"] == job["gpu_guard"]
    assert not any(receipt["acknowledgements"].values())

    receipt["authorized"] = True
    receipt["run_id"] = "unit-v2"
    receipt["attempt_id"] = "capture-00-unit"
    receipt["expires_utc"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    receipt["acknowledgements"] = {
        key: True for key in receipt["acknowledgements"]
    }
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    validated = validate_authorization(
        path,
        EXPERIMENT_ROOT,
        protocol,
        job,
        require_active_wrapper=False,
    )
    assert validated.run_id == "unit-v2"
    assert validated.attempt_id == "capture-00-unit"


def test_protocol_lock_binds_local_and_source_files():
    protocol = load_protocol(EXPERIMENT_ROOT)
    checks = protocol_lock_checks(EXPERIMENT_ROOT, protocol)
    assert checks
    assert all(checks.values()), checks
