"""Build the deterministic synthetic fixture for Sheets, Loops, and Levers."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LAYERS = list(range(28))


TARGETS = [
    ("q_proj", "Query", "query", 18, [0, 0, 1], [1.6, 0.35, 0.0], 0.10),
    ("k_proj", "Key", "key", 32, [0, 1, 1], [1.4, 0.22, 0.0], 0.35),
    ("v_proj", "Value", "value", 48, [1, 0, 1], [1.8, 0.65, 0.12], 0.72),
    ("o_proj", "Output", "output", 64, [1, 1, 0], [1.7, 0.4, 0.0], 1.05),
    ("gate_proj", "Gate", "gate", 85, [0, 1, 0], [0.9, 0.12, 0.0], 1.42),
    ("up_proj", "Up", "up", 112, [1, 0, 0], [1.3, 0.3, 0.05], 1.78),
    ("down_proj", "Down", "down", 140, [1, 1, 1], [1.1, 0.18, 0.0], 2.12),
]


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def normalize(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector]


def rotation(axis: list[float], angle: float) -> list[list[float]]:
    x, y, z = normalize(axis)
    c, s, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
    return [
        [t*x*x+c, t*x*y-s*z, t*x*z+s*y],
        [t*x*y+s*z, t*y*y+c, t*y*z-s*x],
        [t*x*z-s*y, t*y*z+s*x, t*z*z+c],
    ]


def matmul(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [[sum(left[i][k] * right[k][j] for k in range(len(right))) for j in range(len(right[0]))] for i in range(len(left))]


def transpose(matrix: list[list[float]]) -> list[list[float]]:
    return [list(column) for column in zip(*matrix)]


def matvec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[index] * vector[index] for index in range(len(vector))) for row in matrix]


def frobenius(matrix: list[list[float]]) -> float:
    return math.sqrt(sum(value * value for row in matrix for value in row))


def rounded_matrix(matrix: list[list[float]]) -> list[list[float]]:
    return [[round(value, 6) for value in row] for row in matrix]


def raw_depth_coordinates(target_index: int, layer: int) -> list[float]:
    phase = layer / 27 * 2 * math.pi
    group = 0 if target_index < 2 else 1 if target_index < 4 else 2
    group_phase = [0.1, 1.6, 3.2][group]
    group_start = [0, 2, 4][group]
    group_size = [2, 2, 3][group]
    local_offset = (target_index - group_start) - (group_size - 1) / 2
    x = 0.52 * math.sin(phase + group_phase) + 0.55 * local_offset
    y = 0.48 * math.cos(phase * 0.72 + group_phase) + 0.40 * local_offset
    z = 0.36 * math.sin(phase * 1.35 + group_phase * 0.3) + 0.25 * local_offset
    return [x, y, z]


def depth_point(target_index: int, layer: int) -> dict:
    coordinates = raw_depth_coordinates(target_index, layer)

    # Method-faithful synthetic convergence bands: q/k, v/o, and gate/up/down.
    bands = [([0, 1], 9), ([2, 3], 16), ([4, 5, 6], 23)]
    for members, center in bands:
        if target_index not in members:
            continue
        closeness = 0.94 * math.exp(-((layer - center) / 2.8) ** 2)
        centroid = [
            sum(raw_depth_coordinates(member, layer)[axis] for member in members) / len(members)
            for axis in range(3)
        ]
        coordinates = [value * (1 - closeness) + centroid[axis] * closeness for axis, value in enumerate(coordinates)]
    return {"layer": layer, "x": round(coordinates[0], 6), "y": round(coordinates[1], 6), "z": round(coordinates[2], 6)}


def loop_points(offset: float) -> list[dict]:
    points = []
    for index in range(49):
        theta = index / 48 * 2 * math.pi
        radius = 1 + 0.13 * math.cos(3 * theta + offset)
        points.append({
            "phase": round(index / 48, 6),
            "x": round(radius * math.cos(theta), 6),
            "y": round(radius * math.sin(theta), 6),
            "z": round(0.34 * math.sin(2 * theta + offset), 6),
        })
    return points


def motif_fixture(index: int, target: tuple) -> dict:
    target_id, label, family, angle_degrees, axis, eigenvalues, offset = target
    axis = normalize(axis)
    angle = math.radians(angle_degrees)
    holonomy = rotation(axis, angle)
    local_rotation = rotation([0, 0, 1], offset)
    eigenvectors = [
        normalize(matvec(local_rotation, [1, 0, 0])),
        normalize(matvec(local_rotation, [0, 1, 0])),
        normalize(matvec(local_rotation, [0, 0, 1])),
    ]
    diagonal = [[eigenvalues[0], 0, 0], [0, eigenvalues[1], 0], [0, 0, eigenvalues[2]]]
    gramian = matmul(matmul(local_rotation, diagonal), transpose(local_rotation))
    returned = matmul(matmul(holonomy, gramian), transpose(holonomy))
    difference = [[returned[i][j] - gramian[i][j] for j in range(3)] for i in range(3)]
    coupling = frobenius(difference) / frobenius(gramian)
    association = normalize([math.cos(offset), math.sin(offset), 0.42 + 0.04 * index])
    returned_association = matvec(holonomy, association)
    association_return = sum(a * b for a, b in zip(association, returned_association))
    rank = sum(value > 1e-9 for value in eigenvalues)
    margin = 0 if eigenvalues[-1] == 0 else min(value for value in eigenvalues if value > 0) / max(eigenvalues)
    return {
        "id": target_id,
        "label": label,
        "family": family,
        "depth_points": [depth_point(index, layer) for layer in LAYERS],
        "loop_points": loop_points(offset),
        "holonomy": {
            "axis": [round(value, 6) for value in axis],
            "angle_degrees": angle_degrees,
            "matrix": rounded_matrix(holonomy),
            "association_return_cosine": round(association_return, 6),
        },
        "control": {
            "gramian": rounded_matrix(gramian),
            "eigenvalues": eigenvalues,
            "eigenvectors": [[round(value, 6) for value in vector] for vector in eigenvectors],
            "rank": rank,
            "normalized_margin": round(margin, 6),
            "holonomy_coupling": round(coupling, 6),
            "returned_gramian": rounded_matrix(returned),
        },
        "association": [round(value, 6) for value in association],
    }


def build() -> dict:
    body = {
        "schema_version": "sheets_loops_levers_essay.v1",
        "evidence_class": "method_faithful_synthetic_fixture",
        "claim_boundary": "The UI coordinates exact geometric objects on a deterministic synthetic fixture. It is not activation evidence, a neural controllability result, or a human-usability result.",
        "global_normalization": True,
        "depth_layers": LAYERS,
        "etale": {"epsilon": 0.22, "window_radius": 2, "base_topology": "closed interval [0,27]"},
        "time": {"base_topology": "closed phase loop S^1", "samples": 49},
        "confirmation": {
            "experiment": "../reachability_information_gain_v0_1/results_confirmation/final_receipt.json",
            "independent_pairs": 256,
            "passive_accuracy": 0.5,
            "certificate_accuracy": 1.0,
            "information_gain_bits": 1.0,
            "audit_action": "accept",
            "noise_requirement": "Measured B requires a singular-value margin and abstention state.",
        },
        "motifs": [motif_fixture(index, target) for index, target in enumerate(TARGETS)],
    }
    body["fixture_sha256"] = hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
    return body


if __name__ == "__main__":
    data = build()
    pretty = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    (ROOT / "fixture.json").write_text(pretty, encoding="utf-8")
    (ROOT / "fixture.js").write_text("window.SLL_FIXTURE = " + pretty.rstrip() + ";\n", encoding="utf-8")
    print(data["fixture_sha256"])
