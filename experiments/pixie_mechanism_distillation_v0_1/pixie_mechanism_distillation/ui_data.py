"""Deterministic synthetic data package for the Mechanism Law Lab UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .compare import align_programs
from .distill import distill_program, evaluate_program
from .io_utils import atomic_json, atomic_text, object_sha256
from .synthetic import run_synthetic_smoke, synthetic_traces
from .tasks import generate_families


DATASET_SCHEMA = "pixieology_mechanism_law_lab_dataset_v1"
CANDIDATES = ("base_qwen_derived_1p7b", "pixie_rank8")


def _phase_program(
    discovery: list[dict[str, Any]],
    held_out: list[dict[str, Any]],
    state_count: int,
    protocol: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    try:
        program = distill_program(
            discovery,
            state_counts=[state_count],
            discovery_fidelity_floor=protocol["distillation"]["discovery_fidelity_floor"],
            maximum_sparse_dimensions=protocol["distillation"]["maximum_sparse_dimensions"],
        )
    except ValueError:
        return None
    return program, evaluate_program(program, held_out)


def _phase_row(
    program: dict[str, Any], evaluation: dict[str, Any], fidelity_floor: float
) -> dict[str, Any]:
    discovery_fidelity = program["discovery_evaluation"]["heldout_program_fidelity"]
    return {
        "state_count": program["codebook"]["state_count"],
        "qualified": discovery_fidelity >= fidelity_floor,
        "discovery_fidelity": discovery_fidelity,
        "heldout_fidelity": evaluation["heldout_program_fidelity"],
        "output_fidelity": evaluation["output_fidelity"],
        "sparse_invariant_agreement": evaluation["sparse_invariant_agreement"],
        "description_length_bits": program["description_length_bits"],
        "transition_table": program["transition_table"],
        "sparse_invariant": program["sparse_invariant"],
    }


def _selected_candidate(
    program: dict[str, Any], evaluation: dict[str, Any], comparison_side: dict[str, Any]
) -> dict[str, Any]:
    return {
        "candidate": program["candidate"],
        "selected_state_count": program["codebook"]["state_count"],
        "description_length_bits": program["description_length_bits"],
        "program_sha256": program["program_sha256"],
        "transition_table": program["transition_table"],
        "sparse_invariant": program["sparse_invariant"],
        "heldout_evaluation": evaluation,
        "causal": comparison_side["causal"],
        "gates": comparison_side["gates"],
    }


def build_law_lab_dataset(
    protocol: dict[str, Any], *, family_count: int = 4
) -> dict[str, Any]:
    """Build a small, deterministic UI dataset from synthetic fixtures only."""
    if family_count < 1 or family_count > 8:
        raise ValueError("law-lab example family_count must be between 1 and 8")

    smoke = run_synthetic_smoke(protocol, family_count)
    families_by_id = {
        row["task_family_id"]: row
        for row in generate_families(
            seed=protocol["seeds"]["task_families"], count=family_count
        )
    }
    traces = {
        candidate: synthetic_traces(
            candidate=candidate,
            family_count=family_count,
            seed=protocol["seeds"]["synthetic_smoke"],
        )
        for candidate in CANDIDATES
    }
    program_by_key = {
        (row["task_family_id"], row["candidate"]): row for row in smoke["programs"]
    }
    evaluation_by_key = {
        (row["task_family_id"], row["candidate"]): row
        for row in smoke["evaluations"]
    }
    comparison_by_family = {
        row["task_family_id"]: row for row in smoke["comparisons"]
    }
    intervention_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in smoke["interventions"]:
        intervention_by_key.setdefault(
            (row["task_family_id"], row["candidate"]), []
        ).append(row)

    family_rows = []
    fidelity_floor = protocol["distillation"]["discovery_fidelity_floor"]
    state_counts = protocol["distillation"]["candidate_state_counts"]
    for family_id in sorted(families_by_id):
        family = families_by_id[family_id]
        comparison = comparison_by_family[family_id]
        candidates: dict[str, Any] = {}
        full_phase_programs: dict[str, dict[int, dict[str, Any]]] = {}
        for candidate in CANDIDATES:
            selected_rows = [
                row for row in traces[candidate] if row["task_family_id"] == family_id
            ]
            discovery = [row for row in selected_rows if row["split"] == "discovery"]
            held_out = [row for row in selected_rows if row["split"] == "held_out"]
            phase_rows = []
            full_phase_programs[candidate] = {}
            for state_count in state_counts:
                fitted = _phase_program(discovery, held_out, state_count, protocol)
                if fitted is None:
                    continue
                program, evaluation = fitted
                full_phase_programs[candidate][state_count] = program
                phase_rows.append(_phase_row(program, evaluation, fidelity_floor))
            key = (family_id, candidate)
            side = "base" if candidate == CANDIDATES[0] else "pixie"
            candidates[candidate] = {
                **_selected_candidate(
                    program_by_key[key], evaluation_by_key[key], comparison[side]
                ),
                "phase_scan": phase_rows,
                "interventions": intervention_by_key.get(key, []),
            }

        common_counts = sorted(
            set(full_phase_programs[CANDIDATES[0]])
            & set(full_phase_programs[CANDIDATES[1]])
        )
        alignments = {
            str(state_count): align_programs(
                full_phase_programs[CANDIDATES[0]][state_count],
                full_phase_programs[CANDIDATES[1]][state_count],
            )
            for state_count in common_counts
        }
        family_rows.append({
            "task_family_id": family_id,
            "oracle_shape": {
                "state_count": len(family["states"]),
                "input_symbols": family["input_symbols"],
                "output_symbols": family["output_symbols"],
            },
            "complexity_values": common_counts,
            "default_complexity": max(
                candidates[candidate]["selected_state_count"]
                for candidate in CANDIDATES
            ),
            "candidates": candidates,
            "alignments_by_state_count": alignments,
            "comparison": {
                "winner": comparison["winner"],
                "description_length_reduction": comparison[
                    "description_length_reduction"
                ],
                "isomorphism_verdict": comparison["isomorphism_verdict"],
                "evidence_class": comparison["evidence_class"],
            },
        })

    dataset = {
        "schema": DATASET_SCHEMA,
        "experiment_id": protocol["experiment_id"],
        "generator": "sealed_synthetic_mechanism_fixture_v1",
        "seed": protocol["seeds"]["synthetic_smoke"],
        "evidence_class": "synthetic_implementation_fixture",
        "human_or_model_evidence": False,
        "claim_boundary": (
            "This example validates the Mechanism Law Lab interaction and data "
            "contracts only; it is not evidence about Qwen or Pixie internals."
        ),
        "design_lineage": [
            {
                "source": "Generating Interpretable Networks using Hypernetworks",
                "ui_move": "Treat state-count complexity as a phase scan, not a hidden tuning knob.",
            },
            {
                "source": "MIPS / Distilling Machine-Learned Algorithms into Code",
                "ui_move": "Make the executable transition law the primary inspection object.",
            },
            {
                "source": "The Clock and the Pizza",
                "ui_move": "Separate behavioral agreement from internal-mechanism agreement.",
            },
            {
                "source": "Sparse Invariants",
                "ui_move": "Expose the smallest activation coordinate set that identifies states.",
            },
        ],
        "thresholds": {
            "discovery_fidelity_floor": fidelity_floor,
            "minimum_heldout_program_fidelity": protocol["thresholds"][
                "minimum_heldout_program_fidelity"
            ],
            "minimum_isomorphism_fidelity": protocol["thresholds"][
                "minimum_isomorphism_fidelity"
            ],
        },
        "families": family_rows,
    }
    dataset["dataset_sha256"] = object_sha256(dataset)
    return dataset


def write_law_lab_dataset(output_root: Path, dataset: dict[str, Any]) -> None:
    """Write both machine-readable JSON and file://-safe browser data."""
    atomic_json(output_root / "example_data.json", dataset)
    payload = json.dumps(dataset, indent=2, sort_keys=True, ensure_ascii=False)
    source = (
        "(function (root, factory) {\n"
        "  const value = factory();\n"
        "  if (typeof module === \"object\" && module.exports) module.exports = value;\n"
        "  root.PixieMechanismLawLabData = value;\n"
        "})(typeof globalThis !== \"undefined\" ? globalThis : this, function () {\n"
        f"  return {payload};\n"
        "});\n"
    )
    atomic_text(output_root / "example_data.js", source)
