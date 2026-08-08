"""Build deterministic, method-faithful synthetic fixtures for the observatory.

The fixture exercises UI and agent contracts. It is not a reproduction of any
paper and contains no measurements from Pixie, Qwen, or another trained model.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent


SOURCES = {
    "bimt": "https://arxiv.org/abs/2305.08746",
    "clock_pizza": "https://arxiv.org/abs/2306.17844",
    "hypernetwork": "https://arxiv.org/abs/2312.03051",
    "mips": "https://arxiv.org/abs/2402.05110",
    "sid": "https://arxiv.org/abs/2305.19525",
    "open_problems": "https://arxiv.org/abs/2501.16496",
}


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def bimt_fixture() -> dict:
    nodes = [
        {"id": "x0", "label": "x₀", "layer": 0, "x": 0.08, "y": 0.25},
        {"id": "x1", "label": "x₁", "layer": 0, "x": 0.08, "y": 0.75},
        {"id": "h0", "label": "h₀", "layer": 1, "x": 0.38, "y": 0.16},
        {"id": "h1", "label": "h₁", "layer": 1, "x": 0.38, "y": 0.42},
        {"id": "h2", "label": "h₂", "layer": 1, "x": 0.38, "y": 0.68},
        {"id": "h3", "label": "h₃", "layer": 1, "x": 0.38, "y": 0.90},
        {"id": "g0", "label": "g₀", "layer": 2, "x": 0.68, "y": 0.28},
        {"id": "g1", "label": "g₁", "layer": 2, "x": 0.68, "y": 0.72},
        {"id": "y", "label": "ŷ", "layer": 3, "x": 0.93, "y": 0.50},
    ]
    base_edges = [
        ("x0", "h0", 0.92, 0.16), ("x0", "h1", 0.71, 0.08),
        ("x1", "h2", -0.88, 0.14), ("x1", "h3", 0.68, 0.07),
        ("h0", "g0", 0.83, 0.22), ("h1", "g0", -0.62, 0.11),
        ("h2", "g1", 0.79, 0.19), ("h3", "g1", 0.58, 0.09),
        ("g0", "y", 0.91, 0.31), ("g1", "y", -0.86, 0.27),
    ]
    methods = [
        ("vanilla", "Vanilla", 0.0018, 10.9, 8),
        ("l1", "L1", 0.0024, 7.2, 5),
        ("l1_local", "L1 + local", 0.0027, 5.1, 3),
        ("l1_swap", "L1 + swap", 0.0025, 4.7, 2),
        ("bimt", "BIMT", 0.0031, 3.4, 0),
    ]
    out = []
    extra_pool = [
        ("x0", "h3", 0.19, 0.01), ("x1", "h0", -0.23, 0.02),
        ("h0", "g1", 0.17, 0.01), ("h2", "g0", -0.21, 0.02),
        ("h1", "g1", 0.13, 0.01), ("h3", "g0", 0.12, 0.01),
        ("x0", "h2", -0.15, 0.01), ("x1", "h1", 0.16, 0.01),
    ]
    for method_id, label, task_loss, wire_cost, n_extra in methods:
        edges = [
            {"source": a, "target": b, "weight": w, "ablation_delta": d}
            for a, b, w, d in base_edges
        ]
        edges.extend(
            {"source": a, "target": b, "weight": w, "ablation_delta": d}
            for a, b, w, d in extra_pool[:n_extra]
        )
        out.append({
            "id": method_id,
            "label": label,
            "task_loss": task_loss,
            "connection_cost": wire_cost,
            "active_edges": len(edges),
            "nodes": nodes,
            "edges": edges,
        })
    return {
        "methods": out,
        "note": "Synthetic ablation fixture: BIMT combines L1, geometry-weighted locality, and neuron swapping.",
    }


def clock_pizza_fixture() -> dict:
    widths = [32, 64, 128, 256]
    attention_rates = [0.0, 0.25, 0.5, 0.75, 1.0]
    cells = []
    for width in widths:
        boundary = 0.43 + 0.0015 * width
        for alpha in attention_rates:
            gap = alpha - boundary
            if abs(gap) <= 0.12:
                algorithm = "hybrid"
            elif gap < 0:
                algorithm = "pizza"
            else:
                algorithm = "clock"
            pizza_score = max(0.0, min(1.0, (boundary + 0.18 - alpha) / 0.36))
            cells.append({
                "width": width,
                "attention_rate": alpha,
                "algorithm": algorithm,
                "gradient_symmetricity": round(0.18 + 0.72 * pizza_score, 3),
                "distance_irrelevance_q": round(0.78 - 0.65 * pizza_score, 3),
                "circularity": round(0.91 + 0.04 * math.sin(width + alpha), 3),
                "validation_accuracy": round(0.997 + 0.002 * ((width // 32) % 2), 3),
            })
    return {
        "widths": widths,
        "attention_rates": attention_rates,
        "cells": cells,
        "threshold_note": "Synthetic classifier: high gradient symmetricity and low q indicate Pizza; high q indicates Clock.",
    }


def hypernetwork_fixture() -> dict:
    betas = [0.0001, 0.001, 0.01, 0.1]
    steps = [200, 800, 1600, 3200]
    cells = []
    for beta in betas:
        for step in steps:
            progress = math.log10(step) - 2.0
            compression = -math.log10(beta)
            if progress < 0.7:
                algorithm = "convexity"
            elif compression + progress > 4.7:
                algorithm = "double-sided"
            else:
                algorithm = "pudding"
            cells.append({
                "beta": beta,
                "step": step,
                "algorithm": algorithm,
                "double_sidedness": round(max(0.0, min(1.0, (compression + progress - 3.6) / 1.6)), 3),
                "strongest_connection": round(max(0.15, min(0.98, 0.25 + 0.15 * progress + 0.07 * compression)), 3),
                "seed_dependence": round(max(0.03, min(0.8, 0.62 - 0.11 * progress + 0.02 * compression)), 3),
            })
    generalization = []
    for input_dim in [2, 4, 8, 16]:
        for hidden_dim in [2, 4, 8, 16]:
            mismatch = abs(math.log2(input_dim) - math.log2(hidden_dim))
            generalization.append({
                "input_dim": input_dim,
                "hidden_dim": hidden_dim,
                "loss": round(0.004 + 0.009 * mismatch + (0.018 if hidden_dim < input_dim else 0.0), 4),
            })
    return {"betas": betas, "steps": steps, "cells": cells, "generalization": generalization}


def mips_fixture() -> dict:
    return {
        "cases": [
            {
                "id": "binary_addition",
                "label": "Binary addition",
                "status": "compiled",
                "state_points": [
                    {"x": -0.9, "y": -0.3, "code": "0"},
                    {"x": -0.75, "y": -0.22, "code": "0"},
                    {"x": 0.82, "y": 0.35, "code": "1"},
                    {"x": 0.96, "y": 0.27, "code": "1"},
                ],
                "integer_code": "carry ∈ {0, 1}",
                "transition_rows": [
                    {"carry": 0, "a": 0, "b": 0, "next": 0, "out": 0},
                    {"carry": 0, "a": 1, "b": 1, "next": 1, "out": 0},
                    {"carry": 1, "a": 0, "b": 1, "next": 1, "out": 0},
                    {"carry": 1, "a": 1, "b": 1, "next": 1, "out": 1},
                ],
                "symbolic_law": "out = carry ⊕ a ⊕ b; next = (carry + a + b > 1)",
                "python": "out = carry ^ a ^ b\ncarry = int(carry + a + b > 1)",
                "verification": "8 / 8 Boolean transitions",
                "stages": ["network", "simplify", "integer autoencoder", "FSM", "symbolic regression", "verify"],
            },
            {
                "id": "continuous_majority",
                "label": "Running majority",
                "status": "failed: continuous state",
                "state_points": [
                    {"x": -0.9, "y": -0.42, "code": "?"},
                    {"x": -0.5, "y": -0.20, "code": "?"},
                    {"x": 0.0, "y": 0.02, "code": "?"},
                    {"x": 0.5, "y": 0.22, "code": "?"},
                    {"x": 0.9, "y": 0.45, "code": "?"},
                ],
                "integer_code": "No stable finite lattice code",
                "transition_rows": [],
                "symbolic_law": "Unavailable",
                "python": "# stopped before code emission",
                "verification": "not run",
                "stages": ["network", "simplify", "integer autoencoder: failed", "FSM: unavailable", "symbolic regression: unavailable", "verify: unavailable"],
            },
        ]
    }


def harmonic_trajectories() -> list[dict]:
    trajectories = []
    for radius in [0.7, 1.0, 1.3]:
        points = []
        for i in range(25):
            t = i * math.pi / 6
            q = radius * math.cos(t)
            p = -radius * math.sin(t)
            points.append({"t": round(t, 3), "q": round(q, 4), "p": round(p, 4), "H": round(0.5 * (q*q + p*p), 6)})
        trajectories.append({"label": f"r={radius}", "points": points})
    return trajectories


def sid_fixture() -> dict:
    return {
        "systems": [
            {
                "id": "harmonic_oscillator",
                "label": "Harmonic oscillator",
                "dynamics": "q̇ = p, ṗ = −q",
                "basis": ["1", "q", "p", "q²", "qp", "p²"],
                "singular_values": [9.41, 6.2, 4.03, 2.14, 0.88, 0.00000002],
                "sparse_coefficients": [0, 0, 0, 0.5, 0, 0.5],
                "law": "H(q,p) = ½q² + ½p²",
                "nullity": 1,
                "independent_rank": 1,
                "max_residual": 0.00000002,
                "trajectories": harmonic_trajectories(),
            },
            {
                "id": "damped_oscillator",
                "label": "Damped oscillator (negative control)",
                "dynamics": "q̇ = p, ṗ = −q − 0.2p",
                "basis": ["1", "q", "p", "q²", "qp", "p²"],
                "singular_values": [9.51, 6.35, 4.14, 2.07, 0.91, 0.18],
                "sparse_coefficients": [0, 0, 0, 0, 0, 0],
                "law": "No invariant in the proposed basis",
                "nullity": 0,
                "independent_rank": 0,
                "max_residual": 0.18,
                "trajectories": [],
            },
        ]
    }


def open_problems_fixture() -> dict:
    goals = [
        ("monitor", "Monitoring", ["feature readout", "failure-case prediction", "held-out audit"]),
        ("control", "Control", ["causal intervention", "specificity control", "behavioral recovery", "competitive baseline"]),
        ("predict", "Prediction", ["pre-registered forecast", "novel distribution", "calibration", "competitive baseline"]),
        ("engineer", "Engineering", ["mechanism edit", "regression suite", "utility benchmark", "competitive baseline"]),
        ("microscope", "Microscope AI", ["latent structure", "human-checkable claim", "external validation", "scientific utility"]),
    ]
    return {
        "pipeline": ["decomposition", "description", "validation"],
        "goals": [{"id": i, "label": label, "evidence_route": route} for i, label, route in goals],
        "axes": [
            {"id": "depth", "label": "description depth", "value": 0.45},
            {"id": "extent", "label": "network extent", "value": 0.25},
            {"id": "distribution", "label": "task-distribution extent", "value": 0.35},
            {"id": "timing", "label": "during-training access", "value": 0.15},
        ],
        "validation_ladder": [
            "correlational fit", "counterfactual effect", "unusual-failure prediction",
            "component replacement", "ground-truth recovery", "downstream utility",
            "competitive real-task baseline",
        ],
    }


def build() -> dict:
    body = {
        "schema_version": "tegmark_mechinterp_observatory.v1",
        "evidence_class": "method_faithful_synthetic_fixture",
        "human_or_model_evidence": False,
        "claim_boundary": "Interaction and data-contract demonstration only; not a paper reproduction and not evidence about Pixie or Qwen.",
        "sources": SOURCES,
        "lenses": {
            "bimt": bimt_fixture(),
            "clock_pizza": clock_pizza_fixture(),
            "hypernetwork": hypernetwork_fixture(),
            "mips": mips_fixture(),
            "sid": sid_fixture(),
            "open_problems": open_problems_fixture(),
        },
    }
    body["fixture_sha256"] = hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
    return body


if __name__ == "__main__":
    data = build()
    pretty = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    (ROOT / "example_data.json").write_text(pretty, encoding="utf-8")
    (ROOT / "example_data.js").write_text(
        "window.TEGMARK_OBSERVATORY_DATA = " + pretty.rstrip() + ";\n",
        encoding="utf-8",
    )
    print(data["fixture_sha256"])
