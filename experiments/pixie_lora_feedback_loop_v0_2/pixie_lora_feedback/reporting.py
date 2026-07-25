"""Feedback comparison and wrapper/cleanup receipt aggregation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from pixie_etale_motifs.io import atomic_json, sha256_file


def compile_feedback_report(
    evaluations: Sequence[dict[str, Any]],
    *,
    topology_receipts: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    base_receipts = [item for item in evaluations if item.get("condition") == "base_qwen_derived_1p7b"]
    pixie_receipts = [item for item in evaluations if item.get("condition") == "pixie_rank8"]
    if len(base_receipts) != 1 or len(pixie_receipts) != 1:
        return {
            "schema": "pixieology_lora_feedback_report_v1",
            "status": "INCOMPLETE",
            "reason": "exactly one base and one Pixie transfer evaluation are required",
        }
    base = base_receipts[0]
    pixie = pixie_receipts[0]
    topology_by_job = {str(item["job_id"]): item for item in topology_receipts}
    candidates = []
    candidate_receipts = sorted(
        (item for item in evaluations if item.get("condition") in {"tinylora", "qlora"}),
        key=lambda item: str(item["job_id"]),
    )
    for receipt in candidate_receipts:
        condition = str(receipt["condition"])
        log_likelihood_increment = float(receipt["mean_log_likelihood"]) - float(base["mean_log_likelihood"])
        exact_vs_base = float(receipt["exact_match_accuracy"]) - float(base["exact_match_accuracy"])
        exact_vs_pixie = float(receipt["exact_match_accuracy"]) - float(pixie["exact_match_accuracy"])
        behavior_promising = log_likelihood_increment >= 0.05 and exact_vs_base >= 0.0 and exact_vs_pixie >= -0.05
        topology = topology_by_job.get(str(receipt["job_id"]))
        topology_status = "NOT_RUN" if topology is None else str(topology.get("status", "INVALID"))
        adapter_parameter_count = int(receipt.get("adapter_parameter_count", 0))
        normalized_increment = (
            log_likelihood_increment / (adapter_parameter_count / 1_000_000)
            if adapter_parameter_count > 0
            else None
        )
        status = (
            "FEEDBACK_CANDIDATE"
            if behavior_promising and topology_status == "PASS"
            else "AWAITING_TOPOLOGY"
            if behavior_promising
            else "NO_BEHAVIORAL_GAIN"
        )
        candidates.append(
            {
                "job_id": receipt["job_id"],
                "method": condition,
                "adapter_parameter_count": adapter_parameter_count or None,
                "mean_log_likelihood_increment_over_base": log_likelihood_increment,
                "mean_log_likelihood_increment_per_million_adapter_parameters": normalized_increment,
                "exact_match_increment_over_base": exact_vs_base,
                "exact_match_increment_over_pixie": exact_vs_pixie,
                "behavior_promising": behavior_promising,
                "candidate_topology_status": topology_status,
                "status": status,
            }
        )
    if any(item["status"] == "FEEDBACK_CANDIDATE" for item in candidates):
        verdict = "FEEDBACK_CANDIDATE"
    elif any(item["status"] == "AWAITING_TOPOLOGY" for item in candidates):
        verdict = "AWAITING_CANDIDATE_TOPOLOGY"
    elif candidates:
        verdict = "NO_BEHAVIORAL_GAIN"
    else:
        verdict = "BASELINES_COMPLETE_AWAITING_CANDIDATES"
    return {
        "schema": "pixieology_lora_feedback_report_v1",
        "status": verdict,
        "reference": {
            "base": {
                "mean_log_likelihood": base["mean_log_likelihood"],
                "exact_match_accuracy": base["exact_match_accuracy"],
            },
            "pixie": {
                "mean_log_likelihood": pixie["mean_log_likelihood"],
                "exact_match_accuracy": pixie["exact_match_accuracy"],
            },
        },
        "candidates": candidates,
        "registered_behavior_gate": {
            "minimum_log_likelihood_increment_over_base": 0.05,
            "minimum_exact_match_increment_over_base": 0.0,
            "maximum_exact_match_regression_vs_pixie": 0.05,
        },
        "topology_only_is_success": False,
        "claim_boundary": (
            "Behavior-promising candidates remain incomplete until a separately captured activation-topology "
            "receipt passes. This report never treats topology alone as adapter success."
        ),
    }


def finalize_execution(
    *,
    job: dict[str, Any],
    resource_summary_path: Path,
    cleanup_summary_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    resource = json.loads(resource_summary_path.read_text(encoding="utf-8-sig"))
    cleanup = json.loads(cleanup_summary_path.read_text(encoding="utf-8-sig"))
    samples = resource.get("samples", [])
    private_values = [float(item.get("tree_private_bytes", 0)) for item in samples]
    receipt = {
        "schema": "pixieology_lora_feedback_execution_summary_v1",
        "job_id": job["job_id"],
        "job_sha256": job["authorization"]["job_sha256"],
        "status": (
            "COMPLETE"
            if resource.get("status") == "complete" and cleanup.get("status") == "PASS"
            else "ABORTED"
        ),
        "abort_reason": resource.get("abort_reason"),
        "caps": resource.get("caps"),
        "cap_mechanism": resource.get("cap_mechanism"),
        "peak_ram_mb": float(resource.get("peak_job_memory_bytes", 0)) / (1024 * 1024),
        "avg_ram_mb": float(np.mean(private_values)) / (1024 * 1024) if private_values else None,
        "peak_io_mb_s": None,
        "peak_io_measurement": "UNAVAILABLE_WRAPPER_ENFORCED_RATE_WITHOUT_THROUGHPUT_METER",
        "cpu_pct": None,
        "cpu_measurement": "UNAVAILABLE_WRAPPER_ENFORCED_HARD_CAP",
        "cpu_pct_ceiling": resource.get("caps", {}).get("cpu_percent"),
        "steps_completed": None,
        "peak_gpu_memory_mib": resource.get("peak_gpu_memory_mib"),
        "owned_pids": resource.get("owned_pids", []),
        "cleanup_status": cleanup.get("status"),
        "lingering_owned_count": cleanup.get("lingering_owned_count"),
        "owned_gpu_processes": cleanup.get("owned_gpu_processes", []),
        "resource_summary": str(resource_summary_path),
        "resource_summary_sha256": sha256_file(resource_summary_path),
        "cleanup_summary": str(cleanup_summary_path),
        "cleanup_summary_sha256": sha256_file(cleanup_summary_path),
    }
    atomic_json(output_path, receipt)
    return receipt
