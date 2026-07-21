from __future__ import annotations

import math

import numpy as np

from pixie_holonomy5d.analysis import _gauge_integrity
from pixie_holonomy5d.geometry import (
    fit_pca,
    five_d_trajectory,
    loop_receipt,
    polar_transport,
    rank1_support_test,
    reframe_loop,
    spectral_time,
)


def line(angle: float) -> np.ndarray:
    return np.asarray([[math.cos(angle)], [math.sin(angle)]], dtype=np.float64)


def edges(bases: list[np.ndarray]):
    return [polar_transport(bases[index], bases[(index + 1) % len(bases)]) for index in range(len(bases))]


def test_rank_one_liveness_distinguishes_forced_and_frustrated() -> None:
    flat = loop_receipt(edges([line(0.0)] * 4))
    frustrated_edges = edges([line(value) for value in (0.0, math.pi / 4, math.pi / 2, 3 * math.pi / 4)])
    frustrated = loop_receipt(frustrated_edges)
    assert flat.category == "forced_positive"
    assert flat.determinant == 1.0
    assert frustrated.category == "frustrated"
    assert frustrated.determinant == -1.0
    assert math.isclose(frustrated.angle_budget_radians or 0.0, math.pi, abs_tol=1e-12)


def test_loop_category_survives_node_gauge_reframings() -> None:
    original = edges([line(value) for value in (0.0, math.pi / 4, math.pi / 2, 3 * math.pi / 4)])
    rng = np.random.default_rng(71)
    for _ in range(256):
        gauges = [np.asarray([[rng.choice([-1.0, 1.0])]]) for _ in original]
        receipt = loop_receipt(reframe_loop(original, gauges))
        assert receipt.category == "frustrated"
        assert receipt.determinant == -1.0


def test_analysis_gauge_audit_tracks_rooted_spin_convention() -> None:
    original = edges([line(value) for value in (0.0, math.pi / 4, math.pi / 2, 3 * math.pi / 4)])
    receipt = _gauge_integrity(original, seed=77, replicates=64)
    assert receipt["passed"]
    assert receipt["loop_failures"] == 0
    assert receipt["rooted_spin_failures"] == 0


def test_spectral_time_and_five_d_trajectory_are_well_formed() -> None:
    rng = np.random.default_rng(9)
    samples = rng.normal(size=(32, 10)) @ np.diag([4.0, 3.0, 2.0, 1.0, 0.7, 0.5, 0.3, 0.2, 0.1, 0.05])
    center, basis, singular = fit_pca(samples, 8)
    times = spectral_time(singular)
    trajectory = five_d_trajectory(samples[0] - center, basis, singular, np.eye(8))
    assert np.all(np.diff(times) >= 0)
    assert times[-1] == 1.0
    assert len(trajectory) == 8
    assert set(trajectory[0]) == {"x", "y", "z", "t", "s"}
    assert all(point["s"] == 1.0 for point in trajectory)


def test_support_gate_separates_signal_from_permuted_null() -> None:
    rng = np.random.default_rng(17)
    left = rng.normal(-1.0, 0.25, size=(32, 9))
    right = rng.normal(1.0, 0.25, size=(32, 9))
    receipt = rank1_support_test(
        np.vstack([left, right]),
        ["canary"] * 32 + ["style"] * 32,
        bootstrap_replicates=128,
        permutation_replicates=128,
        seed=19,
        required_margin=0.02,
    )
    assert receipt.passed
    assert receipt.bootstrap_q05 > receipt.permutation_q95
