"""Blind, deterministic topology clustering and frozen motif assignment."""

from __future__ import annotations

import itertools
from typing import Any, Sequence

import numpy as np

from .graph import form_descriptor


def _feature_matrix(receipts: Sequence[dict[str, Any]]) -> tuple[list[str], np.ndarray]:
    names: list[str] | None = None
    rows: list[np.ndarray] = []
    for receipt in receipts:
        row_names, row = form_descriptor(receipt)
        if names is None:
            names = row_names
        elif row_names != names:
            raise ValueError("form descriptors use inconsistent feature contracts")
        rows.append(row)
    if not rows:
        raise ValueError("motif mining requires form receipts")
    return names or [], np.stack(rows)


def _standardize(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.mean(values, axis=0)
    scale = np.std(values, axis=0)
    scale = np.where(scale < 1e-12, 1.0, scale)
    return (values - mean) / scale, mean, scale


def _ward_labels(values: np.ndarray, k: int) -> np.ndarray:
    if k < 1 or k > len(values):
        raise ValueError("invalid Ward cluster count")
    clusters: dict[int, list[int]] = {index: [index] for index in range(len(values))}
    means: dict[int, np.ndarray] = {index: values[index].copy() for index in range(len(values))}
    sizes: dict[int, int] = {index: 1 for index in range(len(values))}
    next_id = len(values)
    while len(clusters) > k:
        best: tuple[float, int, int] | None = None
        ids = sorted(clusters)
        for left_offset, left in enumerate(ids):
            for right in ids[left_offset + 1 :]:
                delta = means[left] - means[right]
                cost = sizes[left] * sizes[right] / (sizes[left] + sizes[right]) * float(delta @ delta)
                candidate = (cost, left, right)
                if best is None or candidate < best:
                    best = candidate
        assert best is not None
        _, left, right = best
        combined = clusters.pop(left) + clusters.pop(right)
        combined_size = sizes.pop(left) + sizes.pop(right)
        means.pop(left)
        means.pop(right)
        combined_mean = np.mean(values[combined], axis=0)
        clusters[next_id] = combined
        means[next_id] = combined_mean
        sizes[next_id] = combined_size
        next_id += 1
    ordered = sorted(clusters.values(), key=lambda members: min(members))
    labels = np.empty(len(values), dtype=np.int16)
    for label, members in enumerate(ordered):
        labels[members] = label
    return labels


def _silhouette(values: np.ndarray, labels: np.ndarray) -> float:
    if len(set(labels.tolist())) < 2:
        return -1.0
    distances = np.linalg.norm(values[:, None, :] - values[None, :, :], axis=2)
    scores: list[float] = []
    for index, label in enumerate(labels):
        same = np.where(labels == label)[0]
        same = same[same != index]
        a = float(np.mean(distances[index, same])) if same.size else 0.0
        alternatives = [
            float(np.mean(distances[index, np.where(labels == other)[0]]))
            for other in sorted(set(labels.tolist()))
            if other != label
        ]
        b = min(alternatives)
        denominator = max(a, b)
        scores.append(0.0 if denominator <= 1e-12 else (b - a) / denominator)
    return float(np.mean(scores))


def _subsample_stability(
    values: np.ndarray,
    labels: np.ndarray,
    groups: Sequence[str],
    k: int,
    *,
    replicates: int,
    seed: int,
) -> float:
    unique_groups = sorted(set(groups))
    if len(unique_groups) < 4:
        return 0.0
    rng = np.random.default_rng(seed)
    original_sets = [set(np.where(labels == label)[0].tolist()) for label in sorted(set(labels.tolist()))]
    replicate_scores: list[float] = []
    take = max(k * 2, int(np.ceil(len(unique_groups) * 0.80)))
    take = min(take, len(unique_groups))
    for _ in range(replicates):
        selected_groups = set(rng.choice(unique_groups, size=take, replace=False).tolist())
        selected = np.asarray([index for index, group in enumerate(groups) if group in selected_groups], dtype=np.int64)
        if len(selected) < k:
            continue
        sublabels = _ward_labels(values[selected], k)
        sub_sets = [
            set(selected[np.where(sublabels == label)[0]].tolist())
            for label in sorted(set(sublabels.tolist()))
        ]
        per_cluster = []
        selected_set = set(selected.tolist())
        for original in original_sets:
            visible = original & selected_set
            if not visible:
                continue
            best = max(
                (len(visible & candidate) / len(visible | candidate) for candidate in sub_sets if visible | candidate),
                default=0.0,
            )
            per_cluster.append(best)
        if per_cluster:
            replicate_scores.append(float(np.mean(per_cluster)))
    return float(np.mean(replicate_scores)) if replicate_scores else 0.0


def _centroid_and_medoid(values: np.ndarray, members: np.ndarray) -> tuple[np.ndarray, int, np.ndarray]:
    centroid = np.mean(values[members], axis=0)
    distances = np.linalg.norm(values[members] - centroid, axis=1)
    medoid = int(members[int(np.argmin(distances))])
    return centroid, medoid, distances


def fit_motif_model(
    receipts: Sequence[dict[str, Any]],
    *,
    k_values: Sequence[int] = tuple(range(2, 9)),
    silhouette_floor: float = 0.25,
    stability_floor: float = 0.70,
    minimum_semantic_groups: int = 8,
    stability_replicates: int = 64,
    seed: int = 2026072302,
) -> dict[str, Any]:
    if any(receipt.get("input", {}).get("split") != "discovery" for receipt in receipts):
        raise ValueError("motif fitting may consume discovery receipts only")
    feature_names, raw = _feature_matrix(receipts)
    standardized, mean, scale = _standardize(raw)
    groups = [str(receipt["input"]["semantic_group_id"]) for receipt in receipts]
    candidates: list[dict[str, Any]] = []
    selected: tuple[int, np.ndarray, list[int]] | None = None
    for k in k_values:
        if k >= len(receipts):
            continue
        labels = _ward_labels(standardized, int(k))
        silhouette = _silhouette(standardized, labels)
        stability = _subsample_stability(
            standardized,
            labels,
            groups,
            int(k),
            replicates=stability_replicates,
            seed=seed + int(k),
        )
        retained_labels = [
            label
            for label in sorted(set(labels.tolist()))
            if len({groups[index] for index in np.where(labels == label)[0]}) >= minimum_semantic_groups
        ]
        candidates.append(
            {
                "k": int(k),
                "silhouette": silhouette,
                "bootstrap_subsample_stability": stability,
                "retained_cluster_count": len(retained_labels),
            }
        )
        if (
            selected is None
            and silhouette >= silhouette_floor
            and stability >= stability_floor
            and len(retained_labels) >= 2
        ):
            selected = (int(k), labels, retained_labels)
    base = {
        "schema": "pixieology_etale_motif_model_v1",
        "fit_split": "discovery",
        "feature_names": feature_names,
        "standardization": {"mean": mean.tolist(), "scale": scale.tolist()},
        "selection": {
            "k_values": list(k_values),
            "silhouette_floor": silhouette_floor,
            "stability_floor": stability_floor,
            "minimum_semantic_groups": minimum_semantic_groups,
            "stability_replicates": stability_replicates,
            "seed": seed,
            "candidates": candidates,
        },
    }
    if selected is None:
        return {**base, "status": "NO_STABLE_MOTIFS", "motifs": []}
    chosen_k, labels, retained_labels = selected
    provisional: list[dict[str, Any]] = []
    for cluster_label in retained_labels:
        members = np.where(labels == cluster_label)[0]
        centroid, medoid, member_distances = _centroid_and_medoid(standardized, members)
        provisional.append(
            {
                "cluster_label": int(cluster_label),
                "members": members,
                "centroid": centroid,
                "medoid": medoid,
                "assignment_radius": float(np.quantile(member_distances, 0.95)),
                "sort_key": str(receipts[medoid]["input"]["id"]),
            }
        )
    motifs: list[dict[str, Any]] = []
    for motif_index, item in enumerate(sorted(provisional, key=lambda value: value["sort_key"]), start=1):
        members = item["members"]
        motifs.append(
            {
                "motif_id": f"M{motif_index:02d}",
                "cluster_label": item["cluster_label"],
                "centroid": item["centroid"].tolist(),
                "assignment_radius": max(item["assignment_radius"], 1e-9),
                "medoid_input_id": receipts[item["medoid"]]["input"]["id"],
                "discovery_input_ids": [receipts[index]["input"]["id"] for index in members],
                "semantic_group_count": len({groups[index] for index in members}),
                "evidence_class": "discovery_candidate",
                "human_label": None,
            }
        )
    return {
        **base,
        "status": "CANDIDATES_FROZEN",
        "selected_k": chosen_k,
        "motifs": motifs,
    }


def assign_motifs(receipts: Sequence[dict[str, Any]], model: dict[str, Any]) -> list[dict[str, Any]]:
    if model.get("schema") != "pixieology_etale_motif_model_v1":
        raise ValueError("invalid motif model schema")
    feature_names, raw = _feature_matrix(receipts)
    if feature_names != model["feature_names"]:
        raise ValueError("motif model feature contract mismatch")
    mean = np.asarray(model["standardization"]["mean"], dtype=np.float64)
    scale = np.asarray(model["standardization"]["scale"], dtype=np.float64)
    standardized = (raw - mean) / scale
    assignments: list[dict[str, Any]] = []
    motifs = model.get("motifs", [])
    for receipt, row in zip(receipts, standardized):
        distances = [
            (motif["motif_id"], float(np.linalg.norm(row - np.asarray(motif["centroid"], dtype=np.float64))), float(motif["assignment_radius"]))
            for motif in motifs
        ]
        nearest = min(distances, key=lambda item: (item[1], item[0])) if distances else None
        assigned = nearest is not None and nearest[1] <= nearest[2]
        assignments.append(
            {
                "schema": "pixieology_etale_motif_assignment_v1",
                "input_id": receipt["input"]["id"],
                "semantic_group_id": receipt["input"]["semantic_group_id"],
                "family": receipt["input"]["family"],
                "variant": receipt["input"]["variant"],
                "split": receipt["input"]["split"],
                "motif_id": nearest[0] if assigned else None,
                "status": "assigned" if assigned else "unassigned",
                "distance": None if nearest is None else nearest[1],
                "assignment_radius": None if nearest is None else nearest[2],
                "all_distances": {motif_id: distance for motif_id, distance, _ in distances},
            }
        )
    return assignments
