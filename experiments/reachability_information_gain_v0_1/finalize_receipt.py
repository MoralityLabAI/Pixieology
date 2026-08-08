"""Bind confirmation outputs and independent audit into one compact receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


summary_path = ROOT / "results_confirmation" / "summary.json"
stage_path = ROOT / "results_confirmation" / "stage_receipt.json"
contamination_path = ROOT / "results_confirmation" / "contamination_check.json"
preflight_path = ROOT / "review" / "preflight_confirmation" / "preflight.json"
audit_path = ROOT / "review" / "audit_confirmation" / "audit.json"
development_audit_path = ROOT / "review" / "audit" / "audit.json"
manifest_path = ROOT / "manifest_confirmation.yaml"

summary = read_json(summary_path)
stage = read_json(stage_path)
preflight = read_json(preflight_path)
audit = read_json(audit_path)
development_audit = read_json(development_audit_path)
contamination = read_json(contamination_path)

receipt = {
    "schema_version": "reachability_information_gain.final_receipt.v1",
    "experiment_id": "reachability-information-gain-confirmation-v0-2",
    "development_audit_action": development_audit["operational_decision"]["action"],
    "confirmation": {
        "seed": stage["seed"],
        "independent_items": summary["independent_items"],
        "preflight_status": preflight["status"],
        "preflight_release_blocking": preflight["release_blocking"],
        "task_result": summary["task_result"],
        "measurement_reliability": {
            "audit_grade": audit["measurement_reliability"]["grade"],
            "declared_limits_met": audit["measurement_reliability"]["meets_declared_limits"],
            "repeat_flip_rate": audit["measurement_reliability"]["repeat_flip_rate"],
            "position_sensitive_fraction": audit["measurement_reliability"]["position_sensitive_fraction"],
            "deterministic_coverage_rate": audit["measurement_reliability"]["deterministic_coverage_rate"],
            "passive_identity_leaks": summary["measurement_reliability"]["passive_identity_leaks"],
            "coordinate_invariance_fraction": summary["measurement_reliability"]["coordinate_invariance_fraction"],
        },
        "claim_support": audit["claim_support"]["status"],
        "audit_operational_action": audit["operational_decision"]["action"],
        "adjudication_queue_items": len(audit["adjudication_queue"]),
        "contamination_check_passed": contamination["passed"],
        "noise_robustness": summary["metric_robustness"]["noise_sweep"],
    },
    "artifact_sha256": {
        "manifest_confirmation.yaml": sha256(manifest_path),
        "stage_receipt.json": sha256(stage_path),
        "contamination_check.json": sha256(contamination_path),
        "summary.json": sha256(summary_path),
        "preflight.json": sha256(preflight_path),
        "audit.json": sha256(audit_path),
        "development_audit.json": sha256(development_audit_path),
    },
    "claim_boundary": "The experiment confirms strict information addition on exact synthetic linear systems. It does not establish neural-model controllability or human usability.",
    "next_model_gate": "Estimate local A and registered-intervention B, calibrate numerical-rank uncertainty on a development split, then test predicted endpoints on a sequestered intervention split.",
}

output = ROOT / "results_confirmation" / "final_receipt.json"
output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"output": str(output), "sha256": sha256(output)}))
