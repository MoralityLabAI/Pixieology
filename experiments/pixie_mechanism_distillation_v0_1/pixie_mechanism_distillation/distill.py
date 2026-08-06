"""Discrete transition-program extraction and held-out evaluation."""

from __future__ import annotations

from collections import Counter, defaultdict
import math
from typing import Any

from .io_utils import object_sha256
from .kmeans import fit_codebook, nearest, squared_distance


TRACE_SCHEMA = "pixieology_mechanism_trace_v1"
PROGRAM_SCHEMA = "pixieology_distilled_mechanism_v1"


def validate_traces(rows: list[dict[str, Any]], expected_split: str | None = None) -> None:
    if not rows:
        raise ValueError("trace set is empty")
    dimensions = None
    family = rows[0].get("task_family_id")
    candidate = rows[0].get("candidate")
    for row in rows:
        if row.get("schema") != TRACE_SCHEMA:
            raise ValueError("invalid mechanism trace schema")
        if row.get("task_family_id") != family or row.get("candidate") != candidate:
            raise ValueError("trace set mixes task families or candidates")
        if expected_split is not None and row.get("split") != expected_split:
            raise ValueError(f"expected {expected_split} traces")
        if not row.get("steps"):
            raise ValueError("trace has no steps")
        for step in row["steps"]:
            activation = step.get("activation")
            next_activation = step.get("next_activation")
            if not isinstance(activation, list) or not isinstance(next_activation, list):
                raise ValueError("trace step is missing activation vectors")
            dimensions = dimensions or len(activation)
            if dimensions < 1 or len(activation) != dimensions or len(next_activation) != dimensions:
                raise ValueError("trace activation dimensions differ")
            if not step.get("input_symbol") or not step.get("output_symbol"):
                raise ValueError("trace step is missing symbolic observations")


def _vectors(rows: list[dict[str, Any]]) -> list[list[float]]:
    return [
        [float(value) for value in vector]
        for row in rows
        for step in row["steps"]
        for vector in (step["activation"], step["next_activation"])
    ]


def _majority(counter: Counter) -> Any:
    return min(counter, key=lambda item: (-counter[item], str(item)))


def _fit_table(rows: list[dict[str, Any]], codebook: dict[str, Any]) -> list[dict[str, Any]]:
    counts: dict[tuple[int, str], Counter] = defaultdict(Counter)
    for row in rows:
        for step in row["steps"]:
            state = nearest(codebook["centers"], step["activation"])
            next_state = nearest(codebook["centers"], step["next_activation"])
            counts[(state, str(step["input_symbol"]))][
                (next_state, str(step["output_symbol"]))
            ] += 1
    table = []
    for (state, input_symbol), counter in sorted(counts.items()):
        next_state, output_symbol = _majority(counter)
        table.append({
            "state": state,
            "input_symbol": input_symbol,
            "next_state": next_state,
            "output_symbol": output_symbol,
            "support": sum(counter.values()),
            "purity": counter[(next_state, output_symbol)] / sum(counter.values()),
        })
    return table


def _table_lookup(program: dict[str, Any]) -> dict[tuple[int, str], dict[str, Any]]:
    return {(row["state"], row["input_symbol"]): row for row in program["transition_table"]}


def _sparse_invariant(codebook: dict[str, Any], maximum_dimensions: int) -> dict[str, Any]:
    centers = codebook["centers"]
    dimension_count = codebook["dimensions"]
    mean = [sum(center[index] for center in centers) / len(centers) for index in range(dimension_count)]
    ranked = sorted(
        range(dimension_count),
        key=lambda index: (-sum((center[index] - mean[index]) ** 2 for center in centers), index),
    )
    selected: list[int] = []
    minimum_separation = 0.25
    for dimension in ranked:
        selected.append(dimension)
        signatures = {
            tuple(round(center[index], 3) for index in selected)
            for center in centers
        }
        pairwise_separations = [
            squared_distance(
                [centers[left][index] for index in selected],
                [centers[right][index] for index in selected],
            )
            for left in range(len(centers))
            for right in range(left + 1, len(centers))
        ]
        robustly_unique = (
            len(signatures) == len(centers)
            and (not pairwise_separations or min(pairwise_separations) >= minimum_separation)
        )
        if robustly_unique or len(selected) >= maximum_dimensions:
            break
    return {
        "method": "sparse_centroid_signature_v1",
        "selected_dimensions": selected,
        "maximum_dimensions": maximum_dimensions,
        "minimum_squared_state_separation": minimum_separation,
        "unique_state_signatures": len({
            tuple(round(center[index], 3) for index in selected)
            for center in centers
        }),
    }


def _description_bits(codebook: dict[str, Any], table: list[dict[str, Any]]) -> float:
    state_bits = max(1, math.ceil(math.log2(max(2, codebook["state_count"]))))
    output_count = len({row["output_symbol"] for row in table})
    output_bits = max(1, math.ceil(math.log2(max(2, output_count))))
    centroid_bits = codebook["state_count"] * codebook["dimensions"] * 16
    transition_bits = len(table) * (state_bits * 2 + output_bits + 8)
    return float(centroid_bits + transition_bits)


def evaluate_program(program: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    validate_traces(rows)
    if program.get("schema") != PROGRAM_SCHEMA:
        raise ValueError("invalid distilled program schema")
    lookup = _table_lookup(program)
    centers = program["codebook"]["centers"]
    sparse_dimensions = program["sparse_invariant"]["selected_dimensions"]
    total = 0
    correct = 0
    output_correct = 0
    task_correct = 0
    invariant_correct = 0
    missing = 0
    for row in rows:
        row_task_correct = True
        for step in row["steps"]:
            total += 1
            state = nearest(centers, step["activation"])
            observed_next = nearest(centers, step["next_activation"])
            transition = lookup.get((state, str(step["input_symbol"])))
            if transition is None:
                missing += 1
                row_task_correct = False
            else:
                output_match = transition["output_symbol"] == step["output_symbol"]
                next_match = transition["next_state"] == observed_next
                output_correct += int(output_match)
                correct += int(output_match and next_match)
                row_task_correct = row_task_correct and (
                    step["output_symbol"] == step.get("oracle_output_symbol", step["output_symbol"])
                )
            sparse_state = min(
                range(len(centers)),
                key=lambda index: (
                    squared_distance(
                        [centers[index][dimension] for dimension in sparse_dimensions],
                        [step["activation"][dimension] for dimension in sparse_dimensions],
                    ),
                    index,
                ),
            )
            invariant_correct += int(sparse_state == state)
        task_correct += int(row_task_correct)
    return {
        "schema": "pixieology_mechanism_program_evaluation_v1",
        "task_family_id": rows[0]["task_family_id"],
        "candidate": rows[0]["candidate"],
        "split": rows[0]["split"],
        "step_count": total,
        "case_count": len(rows),
        "heldout_program_fidelity": correct / total,
        "output_fidelity": output_correct / total,
        "task_accuracy": task_correct / len(rows),
        "sparse_invariant_agreement": invariant_correct / total,
        "missing_transition_rate": missing / total,
    }


def distill_program(
    discovery_rows: list[dict[str, Any]],
    *,
    state_counts: list[int] | None = None,
    discovery_fidelity_floor: float = 0.98,
    maximum_sparse_dimensions: int = 3,
) -> dict[str, Any]:
    validate_traces(discovery_rows, "discovery")
    state_counts = state_counts or list(range(1, 9))
    vectors = _vectors(discovery_rows)
    candidates = []
    for state_count in state_counts:
        try:
            codebook = fit_codebook(vectors, state_count)
        except ValueError:
            continue
        table = _fit_table(discovery_rows, codebook)
        program = {
            "schema": PROGRAM_SCHEMA,
            "task_family_id": discovery_rows[0]["task_family_id"],
            "candidate": discovery_rows[0]["candidate"],
            "evidence_class": discovery_rows[0]["coordinate_source"],
            "codebook": codebook,
            "transition_table": table,
            "sparse_invariant": _sparse_invariant(codebook, maximum_sparse_dimensions),
            "description_length_bits": _description_bits(codebook, table),
        }
        evaluation = evaluate_program(program, discovery_rows)
        program["discovery_evaluation"] = evaluation
        candidates.append(program)
    if not candidates:
        raise ValueError("no codebook candidates could be fitted")
    qualified = [
        program for program in candidates
        if program["discovery_evaluation"]["heldout_program_fidelity"] >= discovery_fidelity_floor
    ]
    selected = min(
        qualified or candidates,
        key=lambda program: (
            program["codebook"]["state_count"] if qualified else -program["discovery_evaluation"]["heldout_program_fidelity"],
            program["description_length_bits"],
            program["codebook"]["state_count"],
        ),
    )
    selected = dict(selected)
    selected["selection"] = {
        "candidate_state_counts": state_counts,
        "discovery_fidelity_floor": discovery_fidelity_floor,
        "qualified_state_counts": [program["codebook"]["state_count"] for program in qualified],
        "rule": "smallest_qualified_k_else_maximum_fidelity_then_description",
    }
    selected["program_sha256"] = object_sha256(selected)
    return selected
