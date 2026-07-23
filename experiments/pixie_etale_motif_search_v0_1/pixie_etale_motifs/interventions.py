"""Build registered selective-LoRA masking tasks from confirmed browser cases."""

from __future__ import annotations

from copy import deepcopy
import itertools
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .graph import build_form_receipt


def _mask_for_case(case: dict[str, Any]) -> dict[str, Any]:
    state = case["state"]
    receipt = build_form_receipt(
        input_row={
            "id": case["input_id"],
            "semantic_group_id": case["semantic_group_id"],
            "family": case["family"],
            "variant": case["variant"],
            "split": "confirmation",
            "outcome_eligible": True,
        },
        coordinates=np.asarray(case["coordinates"], dtype=np.float64),
        module_ids=case["module_ids"],
        radii=(int(state["chart_radius"]),),
        epsilons=(float(state["glue_tolerance"]),),
        condition="catalog_case_reconstruction",
    )
    radius = receipt["radii"][str(state["chart_radius"])]
    layer_receipt = radius["layers"][int(state["layer"])]
    cut = layer_receipt["cuts"][f"{float(state['glue_tolerance']):.2f}"]
    component = next(
        item for item in cut["components"]
        if str(state["module_id"]) in item["members"]
    )
    members = list(component["members"])
    bands = [
        band
        for band in radius["filtration"][f"{float(state['glue_tolerance']):.2f}"]["bands"]
        if band["a"] in members
        and band["b"] in members
        and band["start_layer"] <= int(state["layer"]) <= band["end_layer"]
    ]
    start = min((band["start_layer"] for band in bands), default=int(state["layer"]))
    end = max((band["end_layer"] for band in bands), default=int(state["layer"]))
    return {"module_ids": members, "start_layer": start, "end_layer": end}


def build_intervention_plan(
    catalog: dict[str, Any],
    *,
    outcome: str = "trained_minus_base_mean_log_likelihood",
) -> dict[str, Any]:
    if catalog.get("schema") != "pixieology_etale_motif_catalog_v1":
        raise ValueError("invalid motif catalog schema")
    if catalog.get("status") not in {"DESCRIPTIVE_ONLY", "MOTIF_CATALOG_VALIDATED"}:
        raise ValueError("interventions require a held-out descriptive catalog")
    tasks: list[dict[str, Any]] = []
    for case in catalog.get("cases", []):
        if not case.get("outcome_eligible", False):
            continue
        targeted = _mask_for_case(case)
        width = targeted["end_layer"] - targeted["start_layer"] + 1
        if targeted["end_layer"] + width < 28:
            adjacent_start = targeted["end_layer"] + 1
        else:
            adjacent_start = max(0, targeted["start_layer"] - width)
        adjacent = {
            "module_ids": targeted["module_ids"],
            "start_layer": adjacent_start,
            "end_layer": adjacent_start + width - 1,
        }
        tasks.append(
            {
                "task_id": f"intervene-{case['case_id']}",
                "unit_id": case["input_id"],
                "semantic_group_id": case["semantic_group_id"],
                "motif_id": case["motif_ids"][0],
                "outcome": outcome,
                "conditions": [
                    {"condition": "base", "mask": None},
                    {"condition": "full_adapter", "mask": None},
                    {"condition": "targeted_mask", "mask": targeted},
                    {"condition": "adjacent_band_mask", "mask": adjacent},
                    {
                        "condition": "energy_matched_mask",
                        "mask": None,
                        "selection_rule": (
                            "Choose a disjoint module-layer set with equal cardinality and the nearest total "
                            "registered raw LoRA-response energy; freeze the selection before outcomes are read."
                        ),
                    },
                ],
            }
        )
    return {
        "schema": "pixieology_etale_intervention_plan_v1",
        "catalog_status": catalog["status"],
        "task_count": len(tasks),
        "tasks": tasks,
        "mask_semantics": "Mask only the additive LoRA branch; preserve the frozen base linear path.",
        "execution_status": "NOT_RUN",
        "claim_boundary": (
            "This receipt registers tasks only. It is not intervention evidence until complete condition-level "
            "observations pass the intervention schema and the registered held-out gate."
        ),
    }


def _mask_cells(mask: dict[str, Any]) -> set[tuple[int, str]]:
    return {
        (layer, str(module_id))
        for layer in range(int(mask["start_layer"]), int(mask["end_layer"]) + 1)
        for module_id in mask["module_ids"]
    }


def _response_energy_for_inputs(
    capture_paths: Sequence[Path],
    input_ids: set[str],
    module_ids: Sequence[str],
) -> dict[str, np.ndarray]:
    energies: dict[str, np.ndarray] = {}
    for path in capture_paths:
        with np.load(path, allow_pickle=False) as archive:
            row_ids = archive["row_ids"].astype(str)
            for row_index, row_id in enumerate(row_ids):
                if row_id not in input_ids:
                    continue
                raw = np.asarray(archive["raw_coordinates"][row_index], dtype=np.float64)
                matrix = np.zeros((28, len(module_ids)), dtype=np.float64)
                for layer in range(28):
                    for module_index, module_id in enumerate(module_ids):
                        base_norm = float(archive[f"base_norm__{layer:02d}__{module_id}"][row_index])
                        response_norm = np.expm1(raw[layer, module_index, 0]) * (base_norm + 1e-8)
                        matrix[layer, module_index] = response_norm * response_norm
                energies[row_id] = matrix
    missing = sorted(input_ids - set(energies))
    if missing:
        raise ValueError(f"capture artifacts lack intervention inputs: {missing[:8]}")
    return energies


def resolve_energy_matched_masks(
    plan: dict[str, Any],
    capture_paths: Sequence[Path],
    module_ids: Sequence[str],
) -> dict[str, Any]:
    if plan.get("schema") != "pixieology_etale_intervention_plan_v1":
        raise ValueError("invalid intervention plan schema")
    resolved = deepcopy(plan)
    energy_by_input = _response_energy_for_inputs(
        capture_paths,
        {str(task["unit_id"]) for task in resolved["tasks"]},
        module_ids,
    )
    module_index = {str(module_id): index for index, module_id in enumerate(module_ids)}
    for task in resolved["tasks"]:
        targeted_condition = next(item for item in task["conditions"] if item["condition"] == "targeted_mask")
        matched_condition = next(item for item in task["conditions"] if item["condition"] == "energy_matched_mask")
        targeted = targeted_condition["mask"]
        width = int(targeted["end_layer"]) - int(targeted["start_layer"]) + 1
        module_count = len(targeted["module_ids"])
        targeted_cells = _mask_cells(targeted)
        energy = energy_by_input[str(task["unit_id"])]

        def total(mask: dict[str, Any]) -> float:
            return float(sum(energy[layer, module_index[module_id]] for layer, module_id in _mask_cells(mask)))

        target_energy = total(targeted)
        candidates: list[tuple[float, tuple[Any, ...], dict[str, Any], float]] = []
        for modules in itertools.combinations([str(item) for item in module_ids], module_count):
            for start in range(0, 29 - width):
                candidate = {
                    "module_ids": list(modules),
                    "start_layer": start,
                    "end_layer": start + width - 1,
                }
                if targeted_cells & _mask_cells(candidate):
                    continue
                candidate_energy = total(candidate)
                candidates.append(
                    (
                        abs(candidate_energy - target_energy),
                        (start, modules),
                        candidate,
                        candidate_energy,
                    )
                )
        if not candidates:
            raise ValueError(f"no disjoint energy-matched mask exists for {task['task_id']}")
        difference, _, matched, matched_energy = min(candidates, key=lambda item: (item[0], item[1]))
        matched_condition["mask"] = matched
        matched_condition["selection_receipt"] = {
            "metric": "raw_lora_response_squared_norm",
            "target_energy": target_energy,
            "matched_energy": matched_energy,
            "absolute_difference": difference,
            "selected_without_outcome_access": True,
        }
    resolved["execution_status"] = "READY"
    resolved["energy_matching"] = {
        "source": "registered_capture_raw_coordinates_and_base_output_norms",
        "outcomes_read_during_selection": False,
    }
    return resolved
