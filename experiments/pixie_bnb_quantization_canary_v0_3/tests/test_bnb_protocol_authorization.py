from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from pixie_bnb_canary_v3.authorization import authorization_template, validate_authorization
from pixie_bnb_canary_v3.protocol import (
    job_sha256,
    load_job,
    load_protocol,
    verify_protocol_shape,
)


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]


def test_protocol_fixes_small_caps_and_exact_qwen_sweep():
    protocol = load_protocol(EXPERIMENT_ROOT)
    assert verify_protocol_shape(protocol) == []
    assert protocol["resources"]["canary_requested_not_authorized"] == {
        "ram_mb": 2048,
        "cpu_pct": 50,
        "io_mb_s": 50,
        "timeout_seconds": 600,
    }
    sweep = protocol["canary"]["cases"][-1]
    assert sweep["layers"] == 28
    assert [value["name"] for value in sweep["projections"]] == [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ]


def test_job_is_synthetic_inactive_and_hash_bound():
    protocol = load_protocol(EXPERIMENT_ROOT)
    job = load_job(EXPERIMENT_ROOT, protocol)
    assert job["model_loading"] is False
    assert job["adapter_loading"] is False
    assert job["synthetic_weights_only"] is True
    assert job["authorization"]["automatic_authorization"] is False
    assert job_sha256(job) == job["authorization"]["job_sha256"]


def test_inactive_authorization_is_rejected(tmp_path):
    protocol = load_protocol(EXPERIMENT_ROOT)
    job = load_job(EXPERIMENT_ROOT, protocol)
    template = authorization_template(EXPERIMENT_ROOT, protocol, job)
    path = tmp_path / "inactive.json"
    path.write_text(json.dumps(template), encoding="utf-8")
    with pytest.raises(ValueError, match="not active"):
        validate_authorization(
            path,
            EXPERIMENT_ROOT,
            protocol,
            job,
            require_active_wrapper=False,
        )


def test_complete_active_authorization_validates_without_wrapper(tmp_path):
    protocol = load_protocol(EXPERIMENT_ROOT)
    job = load_job(EXPERIMENT_ROOT, protocol)
    receipt = authorization_template(EXPERIMENT_ROOT, protocol, job)
    receipt["authorized"] = True
    receipt["run_id"] = "unit-run"
    receipt["attempt_id"] = "unit-attempt"
    receipt["expires_utc"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    receipt["acknowledgements"] = {
        key: True for key in receipt["acknowledgements"]
    }
    path = tmp_path / "active.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    result = validate_authorization(
        path,
        EXPERIMENT_ROOT,
        protocol,
        job,
        require_active_wrapper=False,
    )
    assert result.run_id == "unit-run"
