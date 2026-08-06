"""Post-training finite-state task-family generator."""

from __future__ import annotations

import random
from typing import Any

from .io_utils import object_sha256


FAMILY_SCHEMA = "pixieology_mechanism_task_family_v1"
CASE_SCHEMA = "pixieology_mechanism_task_case_v1"


def _reachable(table: dict[str, dict[str, dict[str, Any]]], inputs: list[str]) -> bool:
    seen = {"S0"}
    frontier = ["S0"]
    while frontier:
        state = frontier.pop()
        for symbol in inputs:
            target = table[state][symbol]["next_state"]
            if target not in seen:
                seen.add(target)
                frontier.append(target)
    return len(seen) == len(table)


def generate_families(seed: int = 2026080601, count: int = 32) -> list[dict[str, Any]]:
    if count < 1:
        raise ValueError("family count must be positive")
    rng = random.Random(seed)
    families = []
    for family_index in range(count):
        state_count = 3 + (family_index % 4)
        input_count = 2 + (family_index % 3)
        output_count = 2 + ((family_index // 3) % 2)
        states = [f"S{index}" for index in range(state_count)]
        inputs = [f"I{index}" for index in range(input_count)]
        outputs = [f"O{index}" for index in range(output_count)]
        table: dict[str, dict[str, dict[str, str]]] = {}
        for state_index, state in enumerate(states):
            table[state] = {}
            for input_index, symbol in enumerate(inputs):
                if input_index == 0:
                    next_state = states[(state_index + 1) % state_count]
                else:
                    next_state = rng.choice(states)
                output = outputs[(states.index(next_state) + input_index + family_index) % output_count]
                table[state][symbol] = {"next_state": next_state, "output_symbol": output}
        if not _reachable(table, inputs):
            raise AssertionError("generated family is not reachable")
        family = {
            "schema": FAMILY_SCHEMA,
            "task_family_id": f"fsm-{family_index:02d}",
            "generator_seed": seed,
            "initial_state": "S0",
            "states": states,
            "input_symbols": inputs,
            "output_symbols": outputs,
            "transition_table": table,
            "independent_unit": True,
        }
        family["family_sha256"] = object_sha256(family)
        families.append(family)
    return families


def _trajectory(family: dict[str, Any], sequence: list[str]) -> list[dict[str, str]]:
    state = family["initial_state"]
    trajectory = []
    for step_index, symbol in enumerate(sequence):
        transition = family["transition_table"][state][symbol]
        next_state = transition["next_state"]
        trajectory.append({
            "step": step_index,
            "state_before": state,
            "input_symbol": symbol,
            "next_state": next_state,
            "oracle_output_symbol": transition["output_symbol"],
        })
        state = next_state
    return trajectory


def _prompt(family: dict[str, Any], sequence: list[str]) -> str:
    rows = []
    for state in family["states"]:
        for symbol in family["input_symbols"]:
            transition = family["transition_table"][state][symbol]
            rows.append(
                f"{state}+{symbol}->{transition['next_state']}/{transition['output_symbol']}"
            )
    return (
        "Apply this finite-state machine exactly. Start at S0. "
        f"Table: {'; '.join(rows)}. Inputs: {' '.join(sequence)}. "
        "Return only the output symbol emitted by the final transition."
    )


def build_task_cases(
    *,
    family_seed: int = 2026080601,
    case_seed: int = 2026080602,
    family_count: int = 32,
    discovery_per_family: int = 8,
    held_out_per_family: int = 8,
    intervention_per_family: int = 4,
) -> list[dict[str, Any]]:
    families = generate_families(family_seed, family_count)
    rows = []
    split_counts = {
        "discovery": discovery_per_family,
        "held_out": held_out_per_family,
        "intervention": intervention_per_family,
    }
    for family_index, family in enumerate(families):
        for split_index, (split, count) in enumerate(split_counts.items()):
            rng = random.Random(case_seed + family_index * 1009 + split_index * 100_003)
            for row_index in range(count):
                length = 6 + (row_index % 5)
                sequence = [rng.choice(family["input_symbols"]) for _ in range(length)]
                for symbol_index, symbol in enumerate(family["input_symbols"]):
                    if symbol_index < len(sequence):
                        sequence[symbol_index] = symbol
                trajectory = _trajectory(family, sequence)
                row = {
                    "schema": CASE_SCHEMA,
                    "case_id": f"{family['task_family_id']}-{split}-{row_index:02d}",
                    "task_family_id": family["task_family_id"],
                    "family_sha256": family["family_sha256"],
                    "split": split,
                    "input_sequence": sequence,
                    "oracle_trajectory": trajectory,
                    "expected_completion": trajectory[-1]["oracle_output_symbol"],
                    "prompt": _prompt(family, sequence),
                    "outcome_eligible": split != "discovery",
                }
                row["case_sha256"] = object_sha256(row)
                rows.append(row)
    return rows


def validate_cases(rows: list[dict[str, Any]], family_count: int = 32) -> None:
    if not rows:
        raise ValueError("task case set is empty")
    identifiers = [row.get("case_id") for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate task case IDs")
    families = {row.get("task_family_id") for row in rows}
    if len(families) != family_count:
        raise ValueError(f"expected {family_count} task families, found {len(families)}")
    for row in rows:
        if row.get("schema") != CASE_SCHEMA:
            raise ValueError("invalid task case schema")
        if row.get("split") not in {"discovery", "held_out", "intervention"}:
            raise ValueError("invalid task split")
        value = dict(row)
        observed = value.pop("case_sha256", None)
        if observed != object_sha256(value):
            raise ValueError(f"task case hash mismatch for {row.get('case_id')}")
