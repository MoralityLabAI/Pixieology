"""Exact certificate for the observatory's action-sensitive control lens.

The arithmetic that determines reachability is rational/integer. Floating-point
samples are emitted only for drawing the certified reachable sets.
"""

from __future__ import annotations

from fractions import Fraction
import math


Matrix = list[list[Fraction]]


def as_fraction_matrix(values: list[list[int]]) -> Matrix:
    return [[Fraction(value) for value in row] for row in values]


def identity(size: int) -> Matrix:
    return [[Fraction(int(i == j)) for j in range(size)] for i in range(size)]


def transpose(matrix: Matrix) -> Matrix:
    return [list(column) for column in zip(*matrix)]


def multiply(left: Matrix, right: Matrix) -> Matrix:
    return [
        [sum((left[i][k] * right[k][j] for k in range(len(right))), Fraction(0)) for j in range(len(right[0]))]
        for i in range(len(left))
    ]


def power(matrix: Matrix, exponent: int) -> Matrix:
    result = identity(len(matrix))
    for _ in range(exponent):
        result = multiply(result, matrix)
    return result


def hstack(columns: list[Matrix]) -> Matrix:
    return [[entry for column in columns for entry in column[row]] for row in range(len(columns[0]))]


def rank(matrix: Matrix) -> int:
    work = [row[:] for row in matrix]
    rows = len(work)
    columns = len(work[0]) if rows else 0
    pivot_row = 0
    for column in range(columns):
        pivot = next((row for row in range(pivot_row, rows) if work[row][column] != 0), None)
        if pivot is None:
            continue
        work[pivot_row], work[pivot] = work[pivot], work[pivot_row]
        scale = work[pivot_row][column]
        work[pivot_row] = [value / scale for value in work[pivot_row]]
        for row in range(rows):
            if row == pivot_row:
                continue
            factor = work[row][column]
            if factor:
                work[row] = [a - factor * b for a, b in zip(work[row], work[pivot_row])]
        pivot_row += 1
        if pivot_row == rows:
            break
    return pivot_row


def determinant_2x2(matrix: Matrix) -> Fraction:
    return matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]


def reachability_matrix(a: Matrix, b: Matrix, horizon: int) -> Matrix:
    return hstack([multiply(power(a, step), b) for step in range(horizon)])


def gramian(reachability: Matrix) -> Matrix:
    return multiply(reachability, transpose(reachability))


def vector_step(matrix: Matrix, vector: list[Fraction]) -> list[Fraction]:
    return [sum((row[j] * vector[j] for j in range(len(vector))), Fraction(0)) for row in matrix]


def json_number(value: Fraction) -> int | str:
    return value.numerator if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def json_matrix(matrix: Matrix) -> list[list[int | str]]:
    return [[json_number(value) for value in row] for row in matrix]


def reachable_samples(reachability: Matrix, count: int = 49) -> list[dict[str, float]]:
    samples = []
    for index in range(count):
        theta = 2 * math.pi * index / (count - 1)
        controls = [math.cos(theta), math.sin(theta)]
        endpoint = [sum(float(row[j]) * controls[j] for j in range(2)) for row in reachability]
        samples.append({"x": round(endpoint[0], 6), "y": round(endpoint[1], 6)})
    return samples


def system_certificate(system_id: str, label: str, a_values: list[list[int]], b_values: list[list[int]]) -> dict:
    a = as_fraction_matrix(a_values)
    b = as_fraction_matrix(b_values)
    horizon = 2
    controllability = reachability_matrix(a, b, horizon)
    w = gramian(controllability)
    x = [Fraction(1), Fraction(1)]
    passive = []
    for t in range(3):
        passive.append({"t": t, "x": [json_number(value) for value in x]})
        x = vector_step(a, x)
    certificate_rank = rank(controllability)
    return {
        "id": system_id,
        "label": label,
        "A": a_values,
        "B": b_values,
        "horizon": horizon,
        "passive_trajectory": passive,
        "reachability_matrix": json_matrix(controllability),
        "gramian": json_matrix(w),
        "reachability_rank": certificate_rank,
        "fully_controllable": certificate_rank == len(a),
        "gramian_determinant": json_number(determinant_2x2(w)),
        "reachable_boundary": reachable_samples(controllability),
    }


def build_certificate() -> dict:
    a = [[1, 0], [0, 2]]
    axis = system_certificate("axis_actuator", "Axis-only actuator", a, [[1], [0]])
    coupled = system_certificate("coupled_actuator", "Coupled actuator", a, [[1], [1]])
    passive_equal = axis["passive_trajectory"] == coupled["passive_trajectory"] and axis["A"] == coupled["A"]
    ranks_distinct = axis["reachability_rank"] != coupled["reachability_rank"]
    return {
        "schema_version": "tegmark_mechinterp_observatory.control_certificate.v1",
        "theorem_ids": ["finite_horizon_gramian_rank", "conditional_information_monotonicity", "strict_passive_control_witness"],
        "state_dimension": 2,
        "action_dimension": 1,
        "horizon": 2,
        "systems": [axis, coupled],
        "exact_claims": {
            "passive_views_identical": passive_equal,
            "control_signatures_distinct": ranks_distinct,
            "axis_reachable_dimension": axis["reachability_rank"],
            "coupled_reachable_dimension": coupled["reachability_rank"],
            "uniform_prior_information_gain_bits": 1 if passive_equal and ranks_distinct else 0,
            "information_identity": "I(M;P,R) - I(M;P) = I(M;R|P) >= 0",
        },
        "proof_checks": {
            "axis_W_equals_CCT": axis["gramian"] == [[2, 0], [0, 0]],
            "coupled_W_equals_CCT": coupled["gramian"] == [[2, 3], [3, 5]],
            "axis_rank_is_one": axis["reachability_rank"] == 1,
            "coupled_rank_is_two": coupled["reachability_rank"] == 2,
            "passive_equality": passive_equal,
            "strict_information_witness": passive_equal and ranks_distinct,
        },
        "claim_boundary": "Exact theorem and witness for the synthetic linearized systems only. Applying the certificate to a neural model requires measured local A and intervention Jacobian B.",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build_certificate(), indent=2))
