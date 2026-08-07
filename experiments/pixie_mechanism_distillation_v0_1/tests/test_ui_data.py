from __future__ import annotations

import json
from pathlib import Path

from pixie_mechanism_distillation.io_utils import object_sha256
from pixie_mechanism_distillation.ui_data import build_law_lab_dataset


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))


def test_law_lab_dataset_exposes_phase_law_alignment_and_falsification() -> None:
    value = build_law_lab_dataset(PROTOCOL, family_count=2)
    assert value["schema"] == "pixieology_mechanism_law_lab_dataset_v1"
    assert value["human_or_model_evidence"] is False
    assert value["evidence_class"] == "synthetic_implementation_fixture"
    assert len(value["families"]) == 2
    for family in value["families"]:
        assert family["complexity_values"]
        assert set(family["candidates"]) == {
            "base_qwen_derived_1p7b",
            "pixie_rank8",
        }
        assert family["comparison"]["isomorphism_verdict"] == "USABLE_ISOMORPHISM"
        assert all(
            family["alignments_by_state_count"][str(state_count)]["fidelity"] == 1.0
            for state_count in family["complexity_values"]
        )
        for candidate in family["candidates"].values():
            assert candidate["phase_scan"]
            assert candidate["transition_table"]
            assert candidate["interventions"]


def test_checked_in_law_lab_example_is_reproducible_and_hash_bound() -> None:
    observed = json.loads((ROOT / "ui" / "example_data.json").read_text(encoding="utf-8"))
    expected = build_law_lab_dataset(PROTOCOL, family_count=4)
    assert observed == expected
    digest_input = dict(observed)
    observed_hash = digest_input.pop("dataset_sha256")
    assert observed_hash == object_sha256(digest_input)


def test_checked_in_agent_receipt_never_upgrades_synthetic_evidence() -> None:
    receipt = json.loads(
        (ROOT / "ui" / "example_session_receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["status"] == "PASS"
    assert receipt["evidence_class"] == "synthetic_implementation_fixture"
    assert receipt["human_or_model_evidence"] is False
    assert receipt["result"]["claim_status"] == "IMPLEMENTATION_ONLY"
    assert receipt["result"]["underfit_snapshot"]["phase_status"] == "UNDERFIT_AT_K"
    assert receipt["result"]["selected_snapshot"]["phase_status"] == "PROVISIONAL_ISOMORPHISM"
