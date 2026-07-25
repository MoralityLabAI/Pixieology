import copy
import json
from pathlib import Path

import pytest

from pixie_etale_motifs.corpus import build_corpus
from pixie_etale_motifs.io import sha256_file
from pixie_lora_feedback.authorization import authorization_template
from pixie_lora_feedback.jobs import MODULE_IDS, build_job_queue, validate_job
from pixie_lora_feedback.protocol import load_protocol


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
CORPUS = build_corpus(root_seed=2026072301)


def _coordinates(x_values):
    return [
        [[float(value), 0.0, 0.0] for value in x_values]
        for _ in range(28)
    ]


def _case(case_id, motif_id, x_values, distance):
    return {
        "case_id": case_id,
        "motif_ids": [motif_id],
        "assignment_distance": distance,
        "module_ids": list(MODULE_IDS),
        "coordinates": _coordinates(x_values),
        "state": {
            "layer": 13,
            "module_id": "q_proj",
            "chart_radius": 2,
            "glue_tolerance": 0.1,
        },
    }


def _catalog_and_model():
    catalog = {
        "schema": "pixieology_etale_motif_catalog_v1",
        "status": "DESCRIPTIVE_ONLY",
        "evidence_provenance": "registered_activation_capture",
        "cases": [
            _case("case-robust", "M01", [0.0, 0.04, 0.08, 0.8, 1.1, 1.4, 1.7], 0.01),
            _case("case-chain", "M02", [0.0, 0.15, 0.30, 0.8, 1.1, 1.4, 1.7], 0.02),
        ],
    }
    model = {
        "schema": "pixieology_etale_motif_model_v1",
        "status": "CANDIDATES_FROZEN",
        "motifs": [
            {
                "motif_id": "M01",
                "discovery_input_ids": [
                    "pixie_canary-01-canonical",
                    "pixie_canary-01-paraphrase",
                    "pixie_canary-01-token_order_null",
                ],
            },
            {
                "motif_id": "M02",
                "discovery_input_ids": [
                    "pixie_canary-02-canonical",
                    "pixie_canary-02-paraphrase",
                ],
            },
        ],
    }
    return catalog, model


def _queue(catalog=None, model=None):
    protocol = load_protocol(EXPERIMENT_ROOT)
    return build_job_queue(
        protocol=protocol,
        protocol_sha256=sha256_file(EXPERIMENT_ROOT / "protocol.json"),
        implementation_lock_sha256="a" * 64,
        corpus_rows=CORPUS,
        catalog=catalog,
        model=model,
    )


def test_default_queue_slots_reference_jobs_without_inventing_motif_work():
    queue = _queue()
    assert queue["status"] == "STAGED_NOT_AUTHORIZED"
    assert queue["automatic_authorization"] is False
    assert queue["training_slot_status"] == "BLOCKED_NO_CONFIRMED_CATALOG"
    assert [job["method"] for job in queue["jobs"]] == [
        "base_qwen_derived_1p7b",
        "pixie_rank8",
    ]
    assert all(job["status"] == "PROPOSED" for job in queue["jobs"])


def test_confirmed_catalog_slots_paired_tinylora_and_qlora_jobs():
    catalog, model = _catalog_and_model()
    queue = _queue(catalog, model)
    assert queue["training_slot_status"] == "PROPOSED"
    assert queue["job_count"] == 6
    candidates = [job for job in queue["jobs"] if job["job_type"] == "TRAIN_ADAPTER"]
    assert {(job["origin"]["motif_id"], job["method"]) for job in candidates} == {
        ("M01", "tinylora"),
        ("M01", "qlora"),
        ("M02", "tinylora"),
        ("M02", "qlora"),
    }
    for job in candidates:
        assert job["status"] == "PROPOSED"
        assert job["dataset"]["training_split"] == "discovery"
        assert set(job["dataset"]["forbidden_training_splits"]) == {"confirmation", "transfer"}
        assert all(
            next(row for row in CORPUS if row["id"] == input_id)["split"] == "discovery"
            for input_id in job["dataset"]["training_input_ids"]
        )
        assert "token_order_null" not in " ".join(job["dataset"]["training_input_ids"])
        if job["method"] == "tinylora":
            assert job["adapter"]["rank"] == 2
            assert job["adapter"]["layers_to_transform"] == [11, 12, 13, 14, 15]
            assert set(job["adapter"]["target_modules"]) == {"q_proj", "k_proj", "v_proj"}
        else:
            assert job["adapter"]["rank"] == 4
            assert job["adapter"]["target_modules"] == MODULE_IDS
            assert job["adapter"]["layers_to_transform"] == list(range(28))


def test_job_hash_fails_closed_on_mutation():
    job = _queue()["jobs"][0]
    changed = copy.deepcopy(job)
    changed["resources"]["ram_mb"] = 4096
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_job(changed)


def test_authorization_template_is_inactive_and_exact_job_bound():
    if not (EXPERIMENT_ROOT / "protocol.lock.json").is_file():
        pytest.skip("implementation lock is added during protocol sealing")
    protocol = load_protocol(EXPERIMENT_ROOT)
    job = _queue()["jobs"][0]
    template = authorization_template(EXPERIMENT_ROOT, protocol, job)
    assert template["authorized"] is False
    assert template["job_id"] == job["job_id"]
    assert template["job_sha256"] == job["authorization"]["job_sha256"]
    assert template["acknowledgements"]["no_automatic_authorization"] is False


def test_schemas_are_parseable_and_pin_the_queue_and_job_names():
    schemas = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in (EXPERIMENT_ROOT / "schemas").glob("*.json")
    }
    assert schemas["pixieology_lora_feedback_job_v1.schema.json"]["properties"]["schema"]["const"] == (
        "pixieology_lora_feedback_job_v1"
    )
    assert schemas["pixieology_lora_feedback_queue_v1.schema.json"]["properties"]["automatic_authorization"]["const"] is False
