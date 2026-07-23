"""Held-out motif confirmation, catalog construction, and explicit verdicts."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Sequence

import numpy as np

from .mining import assign_motifs


def _agreement(assignments: Sequence[dict[str, Any]], left_variant: str, right_variant: str) -> float:
    by_group: dict[str, dict[str, str | None]] = defaultdict(dict)
    for assignment in assignments:
        by_group[str(assignment["semantic_group_id"])][str(assignment["variant"])] = assignment["motif_id"]
    pairs = [
        variants[left_variant] == variants[right_variant]
        for variants in by_group.values()
        if left_variant in variants and right_variant in variants
    ]
    return float(np.mean(pairs)) if pairs else 0.0


def confirm_motifs(
    receipts: Sequence[dict[str, Any]],
    model: dict[str, Any],
    *,
    minimum_inputs: int = 6,
    minimum_families: int = 2,
    paraphrase_agreement_floor: float = 0.70,
    semantic_gap_floor: float = 0.20,
) -> dict[str, Any]:
    if any(receipt.get("input", {}).get("split") != "confirmation" for receipt in receipts):
        raise ValueError("confirmation may consume confirmation receipts only")
    assignments = assign_motifs(receipts, model)
    canonical_paraphrase = _agreement(assignments, "canonical", "paraphrase")
    canonical_negative = _agreement(assignments, "canonical", "lexical_negative")
    counts = Counter(item["motif_id"] for item in assignments if item["motif_id"])
    families: dict[str, set[str]] = defaultdict(set)
    for item in assignments:
        if item["motif_id"]:
            families[item["motif_id"]].add(str(item["family"]))
    motifs: list[dict[str, Any]] = []
    for motif in model.get("motifs", []):
        motif_id = motif["motif_id"]
        recurrence_pass = counts[motif_id] >= minimum_inputs and len(families[motif_id]) >= minimum_families
        semantic_pass = (
            canonical_paraphrase >= paraphrase_agreement_floor
            and canonical_paraphrase - canonical_negative >= semantic_gap_floor
        )
        motifs.append(
            {
                **motif,
                "confirmation_input_count": counts[motif_id],
                "confirmation_family_count": len(families[motif_id]),
                "recurrence_pass": recurrence_pass,
                "semantic_stability_pass": semantic_pass,
                "evidence_class": "confirmed_descriptive" if recurrence_pass and semantic_pass else "confirmation_failed",
                "predictive_gate": "NOT_RUN",
                "random_adapter_max_stat_gate": "NOT_RUN",
                "causal_gate": "NOT_RUN",
                "learning_qualified": False,
                "craft_qualified": False,
            }
        )
    confirmed = [motif for motif in motifs if motif["evidence_class"] == "confirmed_descriptive"]
    return {
        "schema": "pixieology_etale_motif_confirmation_v1",
        "status": "DESCRIPTIVE_CANDIDATES" if confirmed else "NO_STABLE_MOTIFS",
        "assignment_count": len(assignments),
        "assigned_fraction": float(np.mean([item["status"] == "assigned" for item in assignments])),
        "canonical_paraphrase_agreement": canonical_paraphrase,
        "canonical_lexical_negative_agreement": canonical_negative,
        "semantic_agreement_gap": canonical_paraphrase - canonical_negative,
        "motifs": motifs,
        "assignments": assignments,
        "claim_boundary": (
            "Confirmation establishes recurring descriptive topology only. Predictive, random-control, "
            "causal, learning, and craft gates remain independently required."
        ),
    }


def _case_state(receipt: dict[str, Any]) -> dict[str, Any]:
    candidates: list[tuple[tuple[float, ...], dict[str, Any]]] = []
    for radius_key, radius in receipt["radii"].items():
        for layer in radius["layers"]:
            for epsilon_key, snapshot in layer["cuts"].items():
                epsilon = float(epsilon_key)
                if epsilon > 0.60:
                    continue
                components = [component for component in snapshot["components"] if len(component["members"]) > 1]
                if not components:
                    continue
                component = max(
                    components,
                    key=lambda item: (
                        len(item["members"]),
                        item["clique"],
                        item["bridge_status"] == "none",
                        -item["chain_excess"],
                    ),
                )
                score = (
                    float(len(component["members"])),
                    float(component["clique"]),
                    float(component["bridge_status"] == "none"),
                    -float(component["chain_excess"]),
                    -epsilon,
                    -float(radius_key),
                    -float(layer["layer"]),
                )
                candidates.append(
                    (
                        score,
                        {
                            "layer": int(layer["layer"]),
                            "module_id": str(component["members"][0]),
                            "chart_radius": int(radius_key),
                            "glue_tolerance": epsilon,
                            "lineage_floor": 0.20,
                            "spin_noise": 0.15,
                        },
                    )
                )
    return max(candidates, key=lambda item: item[0])[1] if candidates else {
        "layer": receipt["layer_count"] // 2,
        "module_id": str(receipt["module_ids"][0]),
        "chart_radius": 2,
        "glue_tolerance": 0.25,
        "lineage_floor": 0.20,
        "spin_noise": 0.15,
    }


def _catalog_cases(
    confirmation: dict[str, Any],
    receipts: Sequence[dict[str, Any]],
    confirmed_ids: set[str],
) -> list[dict[str, Any]]:
    by_input = {str(receipt["input"]["id"]): receipt for receipt in receipts}
    cases: list[dict[str, Any]] = []
    for motif_id in sorted(confirmed_ids):
        eligible = sorted([
            assignment
            for assignment in confirmation["assignments"]
            if assignment["motif_id"] == motif_id and assignment["input_id"] in by_input
        ], key=lambda item: (float(item["distance"]), str(item["input_id"])))
        for assignment in eligible:
            receipt = by_input[str(assignment["input_id"])]
            cases.append(
                {
                    "case_id": f"{motif_id.lower()}-{receipt['input']['id']}",
                    "input_id": receipt["input"]["id"],
                    "semantic_group_id": receipt["input"]["semantic_group_id"],
                    "family": receipt["input"]["family"],
                    "variant": receipt["input"]["variant"],
                    "outcome_eligible": bool(receipt["input"]["outcome_eligible"]),
                    "motif_ids": [motif_id],
                    "evidence_class": "confirmed_descriptive",
                    "assignment_distance": float(assignment["distance"]),
                    "assignment_radius": float(assignment["assignment_radius"]),
                    "coordinate_source": "activation_conditioned_trained_counterfactual_on_base",
                    "module_ids": list(receipt["module_ids"]),
                    "coordinates": receipt["coordinates"],
                    "state": _case_state(receipt),
                }
            )
    return cases


def build_catalog(
    confirmation: dict[str, Any],
    *,
    protocol_sha256: str,
    scaler_sha256: str,
    confirmation_receipts: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    if confirmation.get("status") == "DESCRIPTIVE_CANDIDATES":
        if not confirmation_receipts:
            raise ValueError("descriptive catalogs require their held-out form receipts")
        for receipt in confirmation_receipts:
            if receipt.get("condition") != "trained_counterfactual_on_base":
                raise ValueError("catalog receipts must come from registered trained counterfactual capture")
            if receipt.get("metric", {}).get("id") != "activation_conditioned_lora_response_xyz_v1":
                raise ValueError("catalog receipts use an unregistered coordinate metric")
            if receipt.get("metric", {}).get("scaler_sha256") != scaler_sha256:
                raise ValueError("catalog receipt scaler differs from the published scaler")
            if receipt.get("provenance", {}).get("protocol_sha256") != protocol_sha256:
                raise ValueError("catalog receipt protocol differs from the published protocol")
            if receipt.get("provenance", {}).get("real_model_evidence") is False:
                raise ValueError("synthetic fixtures cannot mint a motif catalog")
    motifs = [
        {
            "schema": "pixieology_mechinterp_motif_card_v1",
            "motif_id": motif["motif_id"],
            "human_label": motif.get("human_label"),
            "evidence_class": motif["evidence_class"],
            "medoid_input_id": motif["medoid_input_id"],
            "recognition": {
                "formal_definition": "frozen nearest-centroid assignment in the registered topology descriptor",
                "assignment_radius": motif["assignment_radius"],
            },
            "recommended_next_investigation": None,
            "prohibited_inference": "Do not infer a causal circuit, semantic identity, or holonomy from recurrence alone.",
            "gates": {
                "recurrence": motif["recurrence_pass"],
                "semantic_stability": motif["semantic_stability_pass"],
                "predictive": motif["predictive_gate"],
                "random_adapter_max_stat": motif["random_adapter_max_stat_gate"],
                "causal": motif["causal_gate"],
                "learning_qualified": motif["learning_qualified"],
                "craft_qualified": motif["craft_qualified"],
            },
        }
        for motif in confirmation["motifs"]
        if motif["evidence_class"] == "confirmed_descriptive"
    ]
    cases = _catalog_cases(
        confirmation,
        confirmation_receipts,
        {str(motif["motif_id"]) for motif in motifs},
    )
    return {
        "schema": "pixieology_etale_motif_catalog_v1",
        "status": "DESCRIPTIVE_ONLY" if motifs else "NO_STABLE_MOTIFS",
        "protocol_sha256": protocol_sha256,
        "scaler_sha256": scaler_sha256,
        "evidence_provenance": "registered_activation_capture" if motifs else "none",
        "motifs": motifs,
        "motif_count": len(motifs),
        "case_count": len(cases),
        "cases": cases,
        "human_evidence": {
            "craft_study": "NOT_RUN",
            "learning_study": "NOT_RUN",
            "synthetic_agent_smoke_is_human_evidence": False,
        },
        "claim_boundary": (
            "Cases are activation-conditioned descriptive topology. They do not establish semantic identity, "
            "a causal circuit, literal etale branching, or human usefulness unless the corresponding gates pass."
        ),
    }
