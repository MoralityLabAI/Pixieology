"""Pure geometry for the Pixie 5D validation experiment.

The functions distinguish gauge-covariant rooted coordinates from
gauge-invariant loop receipts. They are instrument code, not evidence that a
supported representation object exists in Bonsai/Pixie.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class Transport:
    polar: np.ndarray
    singular_values: np.ndarray
    retention: float


@dataclass(frozen=True)
class LoopReceipt:
    rank: int
    determinant: float
    category: str
    angle_budget_radians: float | None
    frustration_margin_radians: float | None
    holonomy: np.ndarray

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["holonomy"] = self.holonomy.tolist()
        return value


@dataclass(frozen=True)
class SupportReceipt:
    point_retention: float
    bootstrap_q05: float
    permutation_q95: float
    null_margin: float
    passed: bool


def _as_matrix(value: np.ndarray, label: str) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.ndim != 2 or not np.all(np.isfinite(matrix)):
        raise ValueError(f"{label} must be a finite matrix")
    return matrix


def canonicalize_columns(basis: np.ndarray) -> np.ndarray:
    """Fix a deterministic display gauge without claiming it is intrinsic."""
    output = _as_matrix(basis, "basis").copy()
    for column in range(output.shape[1]):
        pivot = int(np.argmax(np.abs(output[:, column])))
        if output[pivot, column] < 0:
            output[:, column] *= -1
    return output


def fit_pca(samples: np.ndarray, rank: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    matrix = _as_matrix(samples, "samples")
    if matrix.shape[0] < 2:
        raise ValueError("at least two samples are required")
    if rank < 1 or rank > min(matrix.shape):
        raise ValueError("rank exceeds sample matrix dimensions")
    center = matrix.mean(axis=0)
    _, singular_values, right = np.linalg.svd(matrix - center, full_matrices=False)
    basis = canonicalize_columns(right[:rank].T)
    return center, basis, singular_values[:rank]


def spectral_time(singular_values: Sequence[float]) -> np.ndarray:
    values = np.asarray(singular_values, dtype=np.float64)
    if values.ndim != 1 or len(values) == 0 or np.any(values < 0) or not np.all(np.isfinite(values)):
        raise ValueError("singular values must be a non-empty non-negative vector")
    energy = values * values
    total = float(energy.sum())
    if total <= 0:
        raise ValueError("spectral time is undefined for a zero-energy spectrum")
    return np.cumsum(energy) / total


def polar_transport(source_basis: np.ndarray, target_basis: np.ndarray) -> Transport:
    source = _as_matrix(source_basis, "source_basis")
    target = _as_matrix(target_basis, "target_basis")
    if source.shape != target.shape:
        raise ValueError("transport bases must have identical shapes")
    overlap = target.T @ source
    left, singular, right_t = np.linalg.svd(overlap, full_matrices=False)
    polar = left @ right_t
    return Transport(polar=polar, singular_values=singular, retention=float(np.min(singular) ** 2))


def compose_holonomy(transports: Sequence[Transport]) -> np.ndarray:
    if not transports:
        raise ValueError("a loop requires at least one transport")
    rank = transports[0].polar.shape[0]
    result = np.eye(rank, dtype=np.float64)
    for edge in transports:
        if edge.polar.shape != (rank, rank):
            raise ValueError("loop transport ranks differ")
        result = edge.polar @ result
    return result


def loop_receipt(transports: Sequence[Transport], tolerance: float = 1e-10) -> LoopReceipt:
    holonomy = compose_holonomy(transports)
    rank = holonomy.shape[0]
    determinant = float(np.linalg.det(holonomy))
    if rank == 1:
        angle_budget = float(sum(math.acos(math.sqrt(max(0.0, min(1.0, edge.retention)))) for edge in transports))
        margin = math.pi - angle_budget
        negative = determinant < 0
        live = angle_budget >= math.pi - tolerance
        if negative and not live:
            category = "integrity_fail_negative_below_liveness"
        elif negative:
            category = "frustrated"
        elif live:
            category = "live_positive"
        else:
            category = "forced_positive"
        return LoopReceipt(rank, determinant, category, angle_budget, margin, holonomy)
    category = "orientation_reversing" if determinant < 0 else "orientation_preserving"
    return LoopReceipt(rank, determinant, category, None, None, holonomy)


def reframe_loop(transports: Sequence[Transport], gauges: Sequence[np.ndarray]) -> list[Transport]:
    if len(gauges) != len(transports):
        raise ValueError("one node gauge is required per loop edge")
    output: list[Transport] = []
    for index, edge in enumerate(transports):
        source_gauge = _as_matrix(gauges[index], "source_gauge")
        target_gauge = _as_matrix(gauges[(index + 1) % len(gauges)], "target_gauge")
        polar = target_gauge.T @ edge.polar @ source_gauge
        output.append(Transport(polar, edge.singular_values.copy(), edge.retention))
    return output


def five_d_trajectory(
    centered_delta: np.ndarray,
    basis: np.ndarray,
    singular_values: Sequence[float],
    root_to_node_transport: np.ndarray,
) -> list[dict[str, float]]:
    vector = np.asarray(centered_delta, dtype=np.float64)
    local_basis = _as_matrix(basis, "basis")
    root_to_node = _as_matrix(root_to_node_transport, "root_to_node_transport")
    if vector.shape != (local_basis.shape[0],) or root_to_node.shape != (local_basis.shape[1], local_basis.shape[1]):
        raise ValueError("5D trajectory shapes are inconsistent")
    local = local_basis.T @ vector
    rooted = root_to_node.T @ local
    times = spectral_time(singular_values)
    spin = 1.0 if np.linalg.det(root_to_node) >= 0 else -1.0
    points: list[dict[str, float]] = []
    for mode, time in enumerate(times, start=1):
        active = rooted.copy()
        active[mode:] = 0.0
        xyz = np.zeros(3, dtype=np.float64)
        xyz[: min(3, len(active))] = active[:3]
        points.append({"x": float(xyz[0]), "y": float(xyz[1]), "z": float(xyz[2]), "t": float(time), "s": spin})
    return points


def _direction(samples: np.ndarray, labels: np.ndarray) -> np.ndarray | None:
    classes = np.unique(labels)
    if len(classes) != 2:
        raise ValueError("rank-one support requires exactly two classes")
    vector = samples[labels == classes[1]].mean(axis=0) - samples[labels == classes[0]].mean(axis=0)
    norm = float(np.linalg.norm(vector))
    return None if norm <= 1e-12 else vector / norm


def rank1_support_test(
    samples: np.ndarray,
    labels: Sequence[str],
    *,
    bootstrap_replicates: int,
    permutation_replicates: int,
    seed: int,
    required_margin: float,
) -> SupportReceipt:
    matrix = _as_matrix(samples, "samples")
    label_array = np.asarray(labels)
    if len(label_array) != len(matrix):
        raise ValueError("labels and samples differ in length")
    classes = np.unique(label_array)
    if len(classes) != 2:
        raise ValueError("support test requires exactly two classes")
    halves: list[np.ndarray] = []
    for parity in (0, 1):
        indices = np.concatenate([np.where(label_array == item)[0][parity::2] for item in classes])
        halves.append(np.sort(indices))
    if min(map(len, halves)) < 4:
        raise ValueError("each cross-fit half needs at least four samples")
    first = _direction(matrix[halves[0]], label_array[halves[0]])
    second = _direction(matrix[halves[1]], label_array[halves[1]])
    point = 0.0 if first is None or second is None else float((first @ second) ** 2)
    rng = np.random.default_rng(seed)
    boot: list[float] = []
    null: list[float] = []
    for _ in range(bootstrap_replicates):
        directions = []
        for half in halves:
            selected = []
            for item in classes:
                pool = half[label_array[half] == item]
                selected.extend(rng.choice(pool, size=len(pool), replace=True).tolist())
            selected_array = np.asarray(selected, dtype=np.int64)
            directions.append(_direction(matrix[selected_array], label_array[selected_array]))
        boot.append(0.0 if any(item is None for item in directions) else float((directions[0] @ directions[1]) ** 2))
    for _ in range(permutation_replicates):
        directions = []
        for half in halves:
            shuffled = label_array[half].copy()
            rng.shuffle(shuffled)
            directions.append(_direction(matrix[half], shuffled))
        null.append(0.0 if any(item is None for item in directions) else float((directions[0] @ directions[1]) ** 2))
    q05 = float(np.quantile(boot, 0.05))
    q95 = float(np.quantile(null, 0.95))
    margin = q05 - q95
    return SupportReceipt(point, q05, q95, margin, margin > required_margin)
