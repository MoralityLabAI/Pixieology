"""Deterministic, non-authorizing feedback-job proposals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from pixie_etale_motifs.graph import (
    build_distance_prefixes,
    graph_at_cut,
    window_distance,
)
from pixie_etale_motifs.io import atomic_text, object_sha256


JOB_SCHEMA = "pixieology_lora_feedback_job_v1"
QUEUE_SCHEMA = "pixieology_lora_feedback_queue_v1"
MODULE_IDS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def _base_job(
    *,
    condition: str,
    label: str,
    protocol_sha256: str,
    lock_sha256: str,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": JOB_SCHEMA,
        "job_id": f"evaluate-{condition}",
        "status": "PROPOSED",
        "job_type": "EVALUATE",
        "method": condition,
        "label": label,
        "hypothesis": "Establish the frozen transfer reference used by every candidate comparison.",
        "origin": None,
        "model": {
            "base_id": protocol["base_model"]["id"],
            "base_revision": protocol["base_model"]["revision"],
            "adapter": "none" if condition == "base_qwen_derived_1p7b" else "frozen_pixie_rank8",
        },
        "dataset": {
            "training_input_ids": [],
            "training_split": None,
            "forbidden_training_splits": ["confirmation", "transfer"],
            "evaluation_split": "transfer",
        },
        "adapter": None,
        "training": None,
        "resources": protocol["resources"]["training_requested_not_authorized"],
        "gpu_guard": protocol["resources"]["gpu"],
        "success_criteria": {
            "role": "reference_condition",
            "topology_only_is_success": False,
        },
        "authorization": {
            "required": True,
            "status": "NOT_AUTHORIZED",
            "job_sha256": None,
        },
        "protocol_sha256": protocol_sha256,
        "implementation_lock_sha256": lock_sha256,
    }


def _case_diagnostic(case: dict[str, Any]) -> dict[str, Any]:
    coordinates = np.asarray(case["coordinates"], dtype=np.float64)
    modules = [str(item) for item in case["module_ids"]]
    state = case["state"]
    radius = int(state["chart_radius"])
    layer = int(state["layer"])
    epsilon = float(state["glue_tolerance"])
    prefixes = build_distance_prefixes(coordinates, modules)
    distances = {
        edge_id: window_distance(prefix, layer, radius, coordinates.shape[0])
        for edge_id, prefix in prefixes.items()
    }
    snapshot = graph_at_cut(modules, distances, epsilon)
    component = next(
        item for item in snapshot["components"]
        if str(state["module_id"]) in item["members"]
    )
    return {
        "component": component,
        "lower_layer": max(0, layer - radius),
        "upper_layer": min(coordinates.shape[0] - 1, layer + radius),
        "epsilon": epsilon,
    }


def _selected_origins(catalog: dict[str, Any], maximum: int) -> list[dict[str, Any]]:
    candidates = []
    for case in catalog.get("cases", []):
        diagnostic = _case_diagnostic(case)
        component = diagnostic["component"]
        if len(component["members"]) < 2:
            continue
        candidates.append({"case": case, "diagnostic": diagnostic})
    if not candidates:
        return []
    robust = max(
        candidates,
        key=lambda item: (
            item["diagnostic"]["component"]["bridge_status"] == "none",
            item["diagnostic"]["component"]["clique"],
            len(item["diagnostic"]["component"]["members"]),
            -float(item["diagnostic"]["component"]["chain_excess"]),
            -float(item["case"]["assignment_distance"]),
        ),
    )
    selected = [{**robust, "selection_role": "robust_bridge_free"}]
    if maximum > 1:
        robust_motif = robust["case"]["motif_ids"][0]
        remaining = [
            item for item in candidates
            if item["case"]["motif_ids"][0] != robust_motif
        ] or [item for item in candidates if item["case"]["case_id"] != robust["case"]["case_id"]]
        if remaining:
            fragile = max(
                remaining,
                key=lambda item: (
                    not item["diagnostic"]["component"]["clique"],
                    item["diagnostic"]["component"]["bridge_status"] == "present",
                    float(item["diagnostic"]["component"]["chain_excess"]),
                    len(item["diagnostic"]["component"]["members"]),
                    -float(item["case"]["assignment_distance"]),
                ),
            )
            selected.append({**fragile, "selection_role": "fragile_chained"})
    return selected[:maximum]


def _training_ids(
    motif_id: str,
    model: dict[str, Any],
    corpus_rows: Sequence[dict[str, Any]],
) -> list[str]:
    motif = next((item for item in model.get("motifs", []) if item["motif_id"] == motif_id), None)
    if motif is None:
        return []
    by_id = {str(row["id"]): row for row in corpus_rows}
    return sorted(
        str(input_id)
        for input_id in motif.get("discovery_input_ids", [])
        if input_id in by_id
        and by_id[input_id]["split"] == "discovery"
        and by_id[input_id]["outcome_eligible"]
        and by_id[input_id]["expected_completion"] is not None
    )


def _candidate_job(
    *,
    method: str,
    origin: dict[str, Any],
    model: dict[str, Any],
    corpus_rows: Sequence[dict[str, Any]],
    protocol: dict[str, Any],
    protocol_sha256: str,
    lock_sha256: str,
) -> dict[str, Any]:
    case = origin["case"]
    diagnostic = origin["diagnostic"]
    role = str(origin["selection_role"])
    motif_id = str(case["motif_ids"][0])
    training_ids = _training_ids(motif_id, model, corpus_rows)
    template = protocol["training_templates"][method]
    if method == "tinylora":
        target_modules = list(diagnostic["component"]["members"])
        layers = list(range(diagnostic["lower_layer"], diagnostic["upper_layer"] + 1))
    else:
        target_modules = list(MODULE_IDS)
        layers = list(range(28))
    status = "PROPOSED" if len(training_ids) >= 2 else "BLOCKED_INSUFFICIENT_DISCOVERY_DATA"
    job = {
        "schema": JOB_SCHEMA,
        "job_id": f"train-{method}-{motif_id.lower()}-{role}",
        "status": status,
        "job_type": "TRAIN_ADAPTER",
        "method": method,
        "label": f"{method.upper()} · {motif_id} · {role.replace('_', ' ')}",
        "hypothesis": (
            f"A {method} update trained only on discovery members of {motif_id} will alter held-out "
            f"behavior in a way predicted by its {role} topology."
        ),
        "origin": {
            "motif_id": motif_id,
            "case_id": case["case_id"],
            "selection_role": role,
            "chart_state": case["state"],
            "component": diagnostic["component"],
        },
        "model": {
            "base_id": protocol["base_model"]["id"],
            "base_revision": protocol["base_model"]["revision"],
            "adapter_initialization": "fresh_zero_effect_lora_on_frozen_base",
        },
        "dataset": {
            "training_input_ids": training_ids,
            "training_input_ids_sha256": object_sha256(training_ids),
            "training_split": "discovery",
            "forbidden_training_splits": ["confirmation", "transfer"],
            "evaluation_split": "transfer",
        },
        "adapter": {
            "rank": int(template["rank"]),
            "alpha": int(template["alpha"]),
            "dropout": float(protocol["training_templates"]["shared"]["dropout"]),
            "target_modules": target_modules,
            "layers_to_transform": layers,
            "target_policy": template["target_policy"],
        },
        "training": {
            "sequence_length": int(template["sequence_length"]),
            "optimizer_steps": int(template["optimizer_steps"]),
            "gradient_accumulation_steps": int(template["gradient_accumulation_steps"]),
            "learning_rate": float(template["learning_rate"]),
            "weight_decay": float(protocol["training_templates"]["shared"]["weight_decay"]),
            "max_grad_norm": float(protocol["training_templates"]["shared"]["max_grad_norm"]),
            "checkpoint_steps": int(protocol["training_templates"]["shared"]["checkpoint_steps"]),
            "checkpoint_seconds": int(protocol["training_templates"]["shared"]["checkpoint_seconds"]),
            "maximum_checkpoints": int(protocol["training_templates"]["shared"]["maximum_checkpoints"]),
            "seed": int(protocol["seeds"]["training"]),
            "assistant_only_loss": True,
        },
        "resources": protocol["resources"]["training_requested_not_authorized"],
        "gpu_guard": protocol["resources"]["gpu"],
        "success_criteria": {
            "required_evidence": [
                "transfer_behavior_vs_base_and_pixie",
                "candidate_activation_topology_receipt",
                "capacity_reported_method_comparison",
            ],
            "topology_only_is_success": False,
            "confirmation_or_transfer_training_rows": 0,
        },
        "authorization": {
            "required": True,
            "status": "NOT_AUTHORIZED",
            "job_sha256": None,
        },
        "protocol_sha256": protocol_sha256,
        "implementation_lock_sha256": lock_sha256,
    }
    job["authorization"]["job_sha256"] = job_sha256(job)
    return job


def job_sha256(job: dict[str, Any]) -> str:
    value = json.loads(json.dumps(job))
    value.setdefault("authorization", {})["job_sha256"] = None
    return object_sha256(value)


def build_job_queue(
    *,
    protocol: dict[str, Any],
    protocol_sha256: str,
    implementation_lock_sha256: str,
    corpus_rows: Sequence[dict[str, Any]],
    catalog: dict[str, Any] | None = None,
    model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    jobs = [
        _base_job(
            condition="base_qwen_derived_1p7b",
            label=protocol["base_model"]["label"],
            protocol_sha256=protocol_sha256,
            lock_sha256=implementation_lock_sha256,
            protocol=protocol,
        ),
        _base_job(
            condition="pixie_rank8",
            label=protocol["pixie_adapter"]["label"],
            protocol_sha256=protocol_sha256,
            lock_sha256=implementation_lock_sha256,
            protocol=protocol,
        ),
    ]
    for job in jobs:
        job["authorization"]["job_sha256"] = job_sha256(job)
    training_slot_status = "BLOCKED_NO_CONFIRMED_CATALOG"
    selected_roles: list[dict[str, str]] = []
    if catalog is not None or model is not None:
        if catalog is None or model is None:
            raise ValueError("catalog and frozen motif model must be supplied together")
        if catalog.get("schema") != "pixieology_etale_motif_catalog_v1":
            raise ValueError("invalid motif catalog schema")
        if catalog.get("status") not in {"DESCRIPTIVE_ONLY", "MOTIF_CATALOG_VALIDATED"}:
            raise ValueError("feedback jobs require a held-out descriptive catalog")
        if catalog.get("evidence_provenance") != "registered_activation_capture":
            raise ValueError("feedback jobs require registered activation-capture provenance")
        if model.get("schema") != "pixieology_etale_motif_model_v1" or model.get("status") != "CANDIDATES_FROZEN":
            raise ValueError("feedback jobs require the frozen discovery motif model")
        origins = _selected_origins(catalog, int(protocol["comparison"]["maximum_motifs_per_cycle"]))
        for origin in origins:
            for method in ("tinylora", "qlora"):
                jobs.append(
                    _candidate_job(
                        method=method,
                        origin=origin,
                        model=model,
                        corpus_rows=corpus_rows,
                        protocol=protocol,
                        protocol_sha256=protocol_sha256,
                        lock_sha256=implementation_lock_sha256,
                    )
                )
            selected_roles.append({
                "selection_role": origin["selection_role"],
                "motif_id": origin["case"]["motif_ids"][0],
                "case_id": origin["case"]["case_id"],
            })
        training_slot_status = "PROPOSED" if origins else "BLOCKED_NO_ELIGIBLE_ORIGIN"
    queue = {
        "schema": QUEUE_SCHEMA,
        "status": "STAGED_NOT_AUTHORIZED",
        "protocol_sha256": protocol_sha256,
        "implementation_lock_sha256": implementation_lock_sha256,
        "job_count": len(jobs),
        "jobs": jobs,
        "training_slot_status": training_slot_status,
        "selected_origins": selected_roles,
        "automatic_authorization": False,
        "claim_boundary": protocol["claim_boundary"],
    }
    validate_queue(queue)
    return queue


def validate_job(job: dict[str, Any]) -> dict[str, Any]:
    if job.get("schema") != JOB_SCHEMA:
        raise ValueError("invalid feedback job schema")
    if job.get("status") not in {"PROPOSED", "BLOCKED_INSUFFICIENT_DISCOVERY_DATA", "AUTHORIZED", "RUNNING", "COMPLETE", "ABORTED", "REJECTED"}:
        raise ValueError("invalid feedback job status")
    if job.get("job_type") not in {"EVALUATE", "TRAIN_ADAPTER"}:
        raise ValueError("invalid feedback job type")
    if job.get("method") not in {"base_qwen_derived_1p7b", "pixie_rank8", "tinylora", "qlora"}:
        raise ValueError("invalid feedback method")
    if job.get("authorization", {}).get("job_sha256") != job_sha256(job):
        raise ValueError("feedback job hash mismatch")
    if job["resources"] != {"ram_mb": 2048, "cpu_pct": 50, "io_mb_s": 50, "timeout_seconds": 1800}:
        raise ValueError("feedback job differs from the default hard caps")
    if job["job_type"] == "TRAIN_ADAPTER":
        dataset = job["dataset"]
        if dataset.get("training_split") != "discovery":
            raise ValueError("feedback training must use discovery only")
        if set(dataset.get("forbidden_training_splits", [])) != {"confirmation", "transfer"}:
            raise ValueError("feedback job lacks held-out split guards")
    return job


def validate_queue(queue: dict[str, Any]) -> dict[str, Any]:
    if queue.get("schema") != QUEUE_SCHEMA:
        raise ValueError("invalid feedback queue schema")
    jobs = queue.get("jobs")
    if not isinstance(jobs, list) or int(queue.get("job_count", -1)) != len(jobs):
        raise ValueError("feedback queue count mismatch")
    identifiers = [str(job["job_id"]) for job in jobs]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("feedback queue contains duplicate job IDs")
    for job in jobs:
        validate_job(job)
    return queue


def publish_queue_js(queue: dict[str, Any], output_path: Path) -> None:
    validate_queue(queue)
    payload = json.dumps(queue, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    source = (
        "(function (root, factory) {\n"
        "  const value = factory();\n"
        "  if (typeof module === \"object\" && module.exports) module.exports = value;\n"
        "  root.PixieLoraFeedbackJobQueueData = value;\n"
        "})(typeof globalThis !== \"undefined\" ? globalThis : this, function () {\n"
        "  \"use strict\";\n"
        f"  return Object.freeze({payload});\n"
        "});\n"
    )
    atomic_text(output_path, source)
