"""CPU-only synthetic separation for the staged instrument."""

from __future__ import annotations

import math

import numpy as np

from .geometry import (
    fit_pca,
    five_d_trajectory,
    loop_receipt,
    polar_transport,
    rank1_support_test,
    reframe_loop,
    spectral_time,
)


def _line(angle: float) -> np.ndarray:
    return np.asarray([[math.cos(angle)], [math.sin(angle)]], dtype=np.float64)


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    residual = float(np.sum((y_true - y_pred) ** 2))
    total = float(np.sum((y_true - y_true.mean()) ** 2))
    return 1.0 - residual / total


def _ridge_predict(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, penalty: float = 0.1) -> np.ndarray:
    mean = train_x.mean(axis=0)
    scale = train_x.std(axis=0)
    scale[scale < 1e-9] = 1.0
    x = (train_x - mean) / scale
    test = (test_x - mean) / scale
    design = np.column_stack([np.ones(len(x)), x])
    test_design = np.column_stack([np.ones(len(test)), test])
    regularizer = np.eye(design.shape[1]) * penalty
    regularizer[0, 0] = 0
    weights = np.linalg.solve(design.T @ design + regularizer, design.T @ train_y)
    return test_design @ weights


def run_smoke(seed: int = 2026072101) -> dict[str, object]:
    flat_bases = [_line(0.0) for _ in range(4)]
    frustrated_bases = [_line(value) for value in (0.0, math.pi / 4, math.pi / 2, 3 * math.pi / 4)]

    def edges(bases: list[np.ndarray]):
        return [polar_transport(bases[index], bases[(index + 1) % len(bases)]) for index in range(len(bases))]

    flat_edges = edges(flat_bases)
    frustrated_edges = edges(frustrated_bases)
    flat = loop_receipt(flat_edges)
    frustrated = loop_receipt(frustrated_edges)

    rng = np.random.default_rng(seed)
    gauge_categories = []
    for _ in range(256):
        gauges = [np.asarray([[rng.choice([-1.0, 1.0])]]) for _ in range(4)]
        gauge_categories.append(loop_receipt(reframe_loop(frustrated_edges, gauges)).category)

    class_a = rng.normal(-1.25, 0.28, size=(32, 12))
    class_b = rng.normal(1.25, 0.28, size=(32, 12))
    support = rank1_support_test(
        np.vstack([class_a, class_b]),
        ["a"] * len(class_a) + ["b"] * len(class_b),
        bootstrap_replicates=64,
        permutation_replicates=64,
        seed=seed + 1,
        required_margin=0.02,
    )

    samples = rng.normal(size=(48, 10)) @ np.diag([3.0, 2.0, 1.2, 0.8, 0.5, 0.3, 0.2, 0.1, 0.05, 0.02])
    center, basis, singular = fit_pca(samples, 8)
    times = spectral_time(singular)
    trajectory = five_d_trajectory(samples[0] - center, basis, singular, np.eye(8))

    count = 320
    features = rng.normal(size=(count, 6))
    features[:, 3] = rng.uniform(0, 1, size=count)
    features[:, 4] = rng.choice([-1.0, 1.0], size=count)
    features[:, 5] = rng.integers(0, 2, size=count)
    outcome = features[:, :3] @ np.asarray([0.7, -0.45, 0.3]) + 1.1 * features[:, 3] + 0.9 * features[:, 4] + 0.8 * features[:, 5] + rng.normal(0, 0.18, size=count)
    train = np.arange(count) % 5 != 0
    test = ~train
    base_prediction = _ridge_predict(features[train, :3], outcome[train], features[test, :3])
    full_prediction = _ridge_predict(features[train], outcome[train], features[test])
    base_r2 = _r2(outcome[test], base_prediction)
    full_r2 = _r2(outcome[test], full_prediction)

    checks = {
        "flat_forced_positive": flat.category == "forced_positive" and flat.determinant > 0,
        "frustrated_live": frustrated.category == "frustrated" and frustrated.determinant < 0 and abs(frustrated.angle_budget_radians - math.pi) < 1e-10,
        "gauge_invariant": set(gauge_categories) == {"frustrated"},
        "support_gate_live": support.passed,
        "spectral_time_monotone": bool(np.all(np.diff(times) >= 0) and abs(times[-1] - 1.0) < 1e-12),
        "trajectory_is_five_dimensional": len(trajectory) == 8 and set(trajectory[0]) == {"x", "y", "z", "t", "s"},
        "predictive_ablation_separates": full_r2 - base_r2 >= 0.05,
    }
    return {
        "schema": "pixie_5d_holonomy_smoke_v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "seed": seed,
        "checks": checks,
        "flat_loop": flat.to_dict(),
        "frustrated_loop": frustrated.to_dict(),
        "support": support.__dict__,
        "spectral_time": times.tolist(),
        "prediction": {"xyz_r2": base_r2, "full_r2": full_r2, "increment": full_r2 - base_r2},
    }
