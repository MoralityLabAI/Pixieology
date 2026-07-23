"""Strict gate aggregation and browser-catalog publication."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from .io import atomic_json, atomic_text, object_sha256


def _status(receipt: dict[str, Any] | None) -> str:
    return "NOT_RUN" if receipt is None else str(receipt.get("status", "INVALID"))


def compile_report(
    catalog: dict[str, Any],
    *,
    predictive: dict[str, Any] | None = None,
    random_null: dict[str, Any] | None = None,
    intervention: dict[str, Any] | None = None,
    human: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if catalog.get("schema") != "pixieology_etale_motif_catalog_v1":
        raise ValueError("invalid motif catalog schema")
    updated = deepcopy(catalog)
    random_by_motif = {
        str(item["motif_id"]): str(item["status"])
        for item in (random_null or {}).get("motifs", [])
    }
    predictive_status = _status(predictive)
    intervention_status = _status(intervention)
    craft_status = str((human or {}).get("craft", {}).get("status", "NOT_RUN"))
    learning_status = str((human or {}).get("learning", {}).get("status", "NOT_RUN"))
    validated_ids: list[str] = []
    for motif in updated.get("motifs", []):
        motif_id = str(motif["motif_id"])
        motif["gates"]["predictive"] = predictive_status
        motif["gates"]["random_adapter_max_stat"] = random_by_motif.get(motif_id, "NOT_RUN")
        motif["gates"]["causal"] = intervention_status
        motif["gates"]["learning_qualified"] = learning_status == "PASS"
        motif["gates"]["craft_qualified"] = craft_status == "PASS"
        if (
            predictive_status == "PASS"
            and motif["gates"]["random_adapter_max_stat"] == "PASS"
            and intervention_status == "PASS"
        ):
            motif["evidence_class"] = "validated_predictive_null_resistant_causal"
            validated_ids.append(motif_id)
    core_gates = {
        "predictive": predictive_status,
        "random_adapter_max_stat": _status(random_null),
        "causal": intervention_status,
        "craft": craft_status,
        "learning": learning_status,
    }
    if not updated.get("motifs"):
        verdict = "NO_STABLE_MOTIFS"
    elif _status(random_null) == "NULL_DOMINATED":
        verdict = "NULL_DOMINATED"
    elif validated_ids:
        verdict = "MOTIF_CATALOG_VALIDATED"
    else:
        verdict = "DESCRIPTIVE_ONLY"
    updated["status"] = verdict
    updated["motif_count"] = len(updated.get("motifs", []))
    updated["case_count"] = len(updated.get("cases", []))
    updated["validated_motif_ids"] = validated_ids
    updated["human_evidence"] = {
        "craft_study": craft_status,
        "learning_study": learning_status,
        "synthetic_agent_smoke_is_human_evidence": False,
    }
    report = {
        "schema": "pixieology_etale_motif_final_report_v1",
        "verdict": verdict,
        "catalog_sha256_before_gate_aggregation": object_sha256(catalog),
        "catalog_sha256_after_gate_aggregation": object_sha256(updated),
        "motif_count": len(updated.get("motifs", [])),
        "validated_motif_ids": validated_ids,
        "gates": core_gates,
        "claim_boundary": (
            "MOTIF_CATALOG_VALIDATED requires held-out predictive increment, the registered random-adapter "
            "max-stat gate, and the registered intervention gate. Craft and learning qualifications are "
            "reported separately and never inferred from synthetic-agent runs."
        ),
    }
    return report, updated


def report_markdown(report: dict[str, Any]) -> str:
    gate_lines = "\n".join(
        f"- {name.replace('_', ' ')}: `{status}`"
        for name, status in report["gates"].items()
    )
    motifs = ", ".join(report["validated_motif_ids"]) or "none"
    return (
        "# Pixie étale motif search report\n\n"
        f"Verdict: **{report['verdict']}**\n\n"
        f"Validated motif IDs: {motifs}\n\n"
        "## Registered gates\n\n"
        f"{gate_lines}\n\n"
        "## Claim boundary\n\n"
        f"{report['claim_boundary']}\n"
    )


def write_report_bundle(
    output_root: Path,
    report: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, str]:
    output_root.mkdir(parents=True, exist_ok=True)
    report_path = output_root / "final_report.json"
    markdown_path = output_root / "final_report.md"
    catalog_path = output_root / "motif_catalog_gated.json"
    atomic_json(report_path, report)
    atomic_text(markdown_path, report_markdown(report))
    atomic_json(catalog_path, catalog)
    return {
        "report_json": str(report_path),
        "report_markdown": str(markdown_path),
        "catalog": str(catalog_path),
    }


def publish_catalog_js(catalog: dict[str, Any], output_path: Path) -> None:
    if catalog.get("schema") != "pixieology_etale_motif_catalog_v1":
        raise ValueError("invalid motif catalog schema")
    if catalog.get("status") not in {"DESCRIPTIVE_ONLY", "MOTIF_CATALOG_VALIDATED"}:
        raise ValueError("only held-out descriptive or validated catalogs may be published")
    if not catalog.get("motifs") or not catalog.get("cases"):
        raise ValueError("published catalogs require at least one motif and one activation-conditioned case")
    if catalog.get("evidence_provenance") != "registered_activation_capture":
        raise ValueError("published catalogs require registered activation-capture provenance")
    if any(case.get("coordinate_source") != "activation_conditioned_trained_counterfactual_on_base" for case in catalog["cases"]):
        raise ValueError("catalog contains a case without the registered activation-conditioned coordinate source")
    payload = json.dumps(catalog, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    source = (
        "(function (root, factory) {\n"
        "  const value = factory();\n"
        "  if (typeof module === \"object\" && module.exports) module.exports = value;\n"
        "  root.PixieEtaleMotifCatalogData = value;\n"
        "})(typeof globalThis !== \"undefined\" ? globalThis : this, function () {\n"
        "  \"use strict\";\n"
        f"  return Object.freeze({payload});\n"
        "});\n"
    )
    atomic_text(output_path, source)
