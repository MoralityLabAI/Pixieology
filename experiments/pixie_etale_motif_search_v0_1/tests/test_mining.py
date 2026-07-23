from pixie_etale_motifs.analysis import build_catalog, confirm_motifs
from pixie_etale_motifs.corpus import build_corpus
from pixie_etale_motifs.mining import assign_motifs, fit_motif_model
from pixie_etale_motifs.synthetic import build_synthetic_forms


MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def test_discovery_is_frozen_and_confirmation_is_assignment_only():
    rows = build_corpus()
    selected_groups = {
        row["semantic_group_id"]
        for row in rows
        if row["split"] == "discovery"
    }
    selected_groups = set(sorted(selected_groups)[:12])
    discovery_rows = [
        row for row in rows
        if row["split"] == "discovery" and row["semantic_group_id"] in selected_groups
    ]
    forms = build_synthetic_forms(discovery_rows, MODULES)
    model = fit_motif_model(
        forms,
        k_values=(2, 3, 4),
        silhouette_floor=-1.0,
        stability_floor=0.0,
        minimum_semantic_groups=2,
        stability_replicates=4,
    )
    assert model["status"] == "CANDIDATES_FROZEN"
    assert len(model["motifs"]) >= 2
    assignments = assign_motifs(forms, model)
    assert len(assignments) == len(forms)
    assert all(item["schema"] == "pixieology_etale_motif_assignment_v1" for item in assignments)

    confirmation_rows = [row for row in rows if row["split"] == "confirmation"]
    confirmation_forms = build_synthetic_forms(confirmation_rows, MODULES)
    result = confirm_motifs(
        confirmation_forms,
        model,
        minimum_inputs=1,
        minimum_families=1,
        paraphrase_agreement_floor=0.0,
        semantic_gap_floor=-1.0,
    )
    assert result["assignment_count"] == 48
    assert "causal" in result["claim_boundary"].lower()
    catalog_receipts = []
    for receipt in confirmation_forms:
        value = {**receipt}
        value["condition"] = "trained_counterfactual_on_base"
        value["metric"] = {
            "id": "activation_conditioned_lora_response_xyz_v1",
            "scaler_sha256": "b" * 64,
        }
        value["provenance"] = {"protocol_sha256": "a" * 64}
        catalog_receipts.append(value)
    catalog = build_catalog(
        result,
        protocol_sha256="a" * 64,
        scaler_sha256="b" * 64,
        confirmation_receipts=catalog_receipts,
    )
    assert catalog["case_count"] == len(catalog["cases"])
    assert catalog["case_count"] > 0
    assert all(case["coordinate_source"].startswith("activation_conditioned") for case in catalog["cases"])
