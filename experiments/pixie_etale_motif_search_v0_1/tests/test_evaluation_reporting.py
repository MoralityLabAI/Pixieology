import json
import numpy as np

from pixie_etale_motifs.evaluation import analyze_human_study, intervention_gate, predictive_gate
from pixie_etale_motifs.interventions import build_intervention_plan, resolve_energy_matched_masks
from pixie_etale_motifs.reporting import compile_report, publish_catalog_js


def _catalog():
    coordinates = [
        [
            [0.2 if module_index < 2 else 0.2 + 0.4 * (module_index - 1)] * 3
            for module_index in range(7)
        ]
        for _ in range(28)
    ]
    return {
        "schema": "pixieology_etale_motif_catalog_v1",
        "status": "DESCRIPTIVE_ONLY",
        "protocol_sha256": "a" * 64,
        "scaler_sha256": "b" * 64,
        "evidence_provenance": "registered_activation_capture",
        "motif_count": 1,
        "case_count": 1,
        "motifs": [{
            "schema": "pixieology_mechinterp_motif_card_v1",
            "motif_id": "M01",
            "evidence_class": "confirmed_descriptive",
            "medoid_input_id": "input-1",
            "recognition": {},
            "prohibited_inference": "causality",
            "gates": {
                "recurrence": True,
                "semantic_stability": True,
                "predictive": "NOT_RUN",
                "random_adapter_max_stat": "NOT_RUN",
                "causal": "NOT_RUN",
                "learning_qualified": False,
                "craft_qualified": False,
            },
        }],
        "cases": [{
            "case_id": "m01-input-1",
            "input_id": "input-1",
            "semantic_group_id": "group-1",
            "family": "pixie_style",
            "variant": "canonical",
            "outcome_eligible": True,
            "motif_ids": ["M01"],
            "evidence_class": "confirmed_descriptive",
            "coordinate_source": "activation_conditioned_trained_counterfactual_on_base",
            "module_ids": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            "coordinates": coordinates,
            "state": {
                "layer": 13,
                "module_id": "q_proj",
                "chart_radius": 2,
                "glue_tolerance": 0.2,
                "lineage_floor": 0.2,
                "spin_noise": 0.15,
            },
        }],
        "human_evidence": {
            "craft_study": "NOT_RUN",
            "learning_study": "NOT_RUN",
            "synthetic_agent_smoke_is_human_evidence": False,
        },
    }


def test_unavailable_predictive_gate_is_explicit():
    assert predictive_gate([], [])["status"] == "UNAVAILABLE"


def test_intervention_and_registered_plan(tmp_path):
    rows = []
    for index in range(6):
        for condition, outcome in (
            ("full_adapter", 1.0),
            ("targeted_mask", 0.3 + index * 0.01),
            ("energy_matched_mask", 0.8 + index * 0.005),
        ):
            rows.append({
                "schema": "pixieology_etale_intervention_observation_v1",
                "task_id": f"task-{index}",
                "plan_sha256": "a" * 64,
                "unit_id": f"u{index}",
                "semantic_group_id": f"g{index}",
                "motif_id": "M01",
                "condition": condition,
                "outcome": outcome,
            })
    assert intervention_gate(rows, bootstrap_replicates=100)["status"] == "PASS"
    plan = build_intervention_plan(_catalog())
    assert plan["execution_status"] == "NOT_RUN"
    assert plan["tasks"][0]["conditions"][2]["condition"] == "targeted_mask"
    assert "additive LoRA branch" in plan["mask_semantics"]
    modules = _catalog()["cases"][0]["module_ids"]
    arrays = {
        "row_ids": np.asarray(["input-1"]),
        "raw_coordinates": np.full((1, 28, 7, 3), 0.2, dtype=np.float32),
    }
    for layer in range(28):
        for module_id in modules:
            arrays[f"base_norm__{layer:02d}__{module_id}"] = np.asarray([1.0], dtype=np.float32)
    capture = tmp_path / "capture.npz"
    np.savez(capture, **arrays)
    resolved = resolve_energy_matched_masks(plan, [capture], modules)
    matched = next(
        item for item in resolved["tasks"][0]["conditions"]
        if item["condition"] == "energy_matched_mask"
    )
    assert resolved["execution_status"] == "READY"
    assert matched["mask"] is not None
    assert matched["selection_receipt"]["selected_without_outcome_access"] is True


def test_human_gates_and_strict_report(tmp_path):
    rows = []
    for index in range(12):
        for condition, correct, elapsed in (("raw", False, 1000), ("motif", True, 800)):
            rows.append({
                "schema": "pixieology_etale_human_study_row_v1",
                "study": "craft",
                "participant_id": f"craft-{index}",
                "condition": condition,
                "correct": correct,
                "elapsed_ms": elapsed,
                "unsupported_causal_claim": False,
            })
    for index in range(16):
        rows.extend([
            {
                "schema": "pixieology_etale_human_study_row_v1",
                "study": "learning",
                "participant_id": f"learning-c-{index}",
                "condition": "conventional",
                "pretest_accuracy": 0.5,
                "immediate_accuracy": 0.7,
                "transfer_accuracy": 0.6,
            },
            {
                "schema": "pixieology_etale_human_study_row_v1",
                "study": "learning",
                "participant_id": f"learning-m-{index}",
                "condition": "motif",
                "pretest_accuracy": 0.5,
                "immediate_accuracy": 0.9,
                "transfer_accuracy": 0.9,
            },
        ])
    human = analyze_human_study(rows)
    assert human["status"] == "PASS"
    random_null = {
        "status": "PASS",
        "motifs": [{"motif_id": "M01", "status": "PASS"}],
    }
    report, catalog = compile_report(
        _catalog(),
        predictive={"status": "PASS"},
        random_null=random_null,
        intervention={"status": "PASS"},
        human=human,
    )
    assert report["verdict"] == "MOTIF_CATALOG_VALIDATED"
    assert catalog["motifs"][0]["gates"]["learning_qualified"] is True
    output = tmp_path / "catalog.js"
    publish_catalog_js(catalog, output)
    source = output.read_text(encoding="utf-8")
    assert "PixieEtaleMotifCatalogData" in source
    assert json.dumps("MOTIF_CATALOG_VALIDATED") in source
