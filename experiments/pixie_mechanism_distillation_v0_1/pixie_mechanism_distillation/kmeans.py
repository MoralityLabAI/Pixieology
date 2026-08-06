"""Dependency-free deterministic codebook fitting."""

from __future__ import annotations

import math
from typing import Iterable


Vector = list[float]


def squared_distance(left: Iterable[float], right: Iterable[float]) -> float:
    return sum((float(a) - float(b)) ** 2 for a, b in zip(left, right, strict=True))


def nearest(centers: list[Vector], vector: Vector) -> int:
    return min(range(len(centers)), key=lambda index: (squared_distance(centers[index], vector), index))


def _mean(vectors: list[Vector], dimensions: int) -> Vector:
    return [sum(vector[index] for vector in vectors) / len(vectors) for index in range(dimensions)]


def fit_codebook(vectors: list[Vector], k: int, max_iterations: int = 100) -> dict:
    if not vectors:
        raise ValueError("cannot fit an empty codebook")
    dimensions = len(vectors[0])
    if dimensions < 1 or any(len(vector) != dimensions for vector in vectors):
        raise ValueError("activation vectors require one fixed positive dimension")
    if k < 1 or k > len(vectors):
        raise ValueError("invalid codebook size")
    centers = [list(vectors[0])]
    while len(centers) < k:
        candidate = max(
            vectors,
            key=lambda vector: (
                min(squared_distance(center, vector) for center in centers),
                tuple(vector),
            ),
        )
        if any(squared_distance(candidate, center) == 0 for center in centers):
            break
        centers.append(list(candidate))
    if len(centers) != k:
        raise ValueError(f"requested {k} states but only {len(centers)} distinct vectors exist")
    assignments: list[int] = []
    for iteration in range(max_iterations):
        updated_assignments = [nearest(centers, vector) for vector in vectors]
        if updated_assignments == assignments:
            break
        assignments = updated_assignments
        updated_centers = []
        for center_index in range(k):
            members = [vector for vector, assignment in zip(vectors, assignments, strict=True) if assignment == center_index]
            updated_centers.append(_mean(members, dimensions) if members else centers[center_index])
        centers = updated_centers
    reconstruction_mse = sum(
        squared_distance(vector, centers[assignment])
        for vector, assignment in zip(vectors, assignments, strict=True)
    ) / (len(vectors) * dimensions)
    if not math.isfinite(reconstruction_mse):
        raise ValueError("non-finite codebook fit")
    return {
        "method": "deterministic_euclidean_kmeans_farthest_first_v1",
        "state_count": k,
        "dimensions": dimensions,
        "centers": centers,
        "reconstruction_mse": reconstruction_mse,
        "iterations": iteration + 1,
    }
