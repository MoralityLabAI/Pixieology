"""Filtration, graph diagnostics, persistence bands, and motif descriptors."""

from __future__ import annotations

from collections import defaultdict
import itertools
from typing import Any, Iterable, Sequence

import numpy as np


def pair_ids(module_ids: Sequence[str]) -> list[tuple[str, str]]:
    return [(str(left), str(right)) for left, right in itertools.combinations(module_ids, 2)]


def build_distance_prefixes(
    coordinates: np.ndarray,
    module_ids: Sequence[str],
) -> dict[str, np.ndarray]:
    values = np.asarray(coordinates, dtype=np.float64)
    if values.ndim != 3 or values.shape[1] != len(module_ids) or values.shape[2] != 3:
        raise ValueError("coordinates must have shape (layers, modules, 3)")
    if not np.all(np.isfinite(values)):
        raise ValueError("coordinates must be finite")
    result: dict[str, np.ndarray] = {}
    for left_index, right_index in itertools.combinations(range(len(module_ids)), 2):
        squared = np.sum((values[:, left_index, :] - values[:, right_index, :]) ** 2, axis=1)
        result[f"{module_ids[left_index]}|{module_ids[right_index]}"] = np.concatenate(
            [np.zeros(1, dtype=np.float64), np.cumsum(squared)]
        )
    return result


def window_distance(prefix: np.ndarray, center: int, radius: int, layer_count: int) -> float:
    lower = max(0, int(center) - int(radius))
    upper = min(int(layer_count) - 1, int(center) + int(radius))
    count = upper - lower + 1
    squared = float(prefix[upper + 1] - prefix[lower])
    return float(np.sqrt(max(0.0, squared) / (count * 3)))


def distance_curves(
    coordinates: np.ndarray,
    module_ids: Sequence[str],
    radius: int,
) -> dict[str, list[float]]:
    prefixes = build_distance_prefixes(coordinates, module_ids)
    layer_count = int(np.asarray(coordinates).shape[0])
    return {
        pair_id: [window_distance(prefix, layer, radius, layer_count) for layer in range(layer_count)]
        for pair_id, prefix in prefixes.items()
    }


def _component_partition(module_ids: Sequence[str], edges: Iterable[tuple[str, str]]) -> list[list[str]]:
    adjacency: dict[str, set[str]] = {str(module_id): set() for module_id in module_ids}
    for left, right in edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    components: list[list[str]] = []
    unseen = set(adjacency)
    while unseen:
        start = min(unseen)
        stack = [start]
        component: list[str] = []
        unseen.remove(start)
        while stack:
            node = stack.pop()
            component.append(node)
            for neighbor in sorted(adjacency[node], reverse=True):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component))
    return sorted(components, key=lambda group: (group[0], len(group)))


def tarjan_diagnostics(nodes: Sequence[str], edges: Iterable[tuple[str, str]]) -> dict[str, Any]:
    adjacency: dict[str, set[str]] = {str(node): set() for node in nodes}
    for left, right in edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    discovery: dict[str, int] = {}
    low: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    bridges: list[str] = []
    articulations: set[str] = set()
    clock = 0

    def visit(node: str) -> None:
        nonlocal clock
        clock += 1
        discovery[node] = low[node] = clock
        children = 0
        for neighbor in sorted(adjacency[node]):
            if neighbor not in discovery:
                parent[neighbor] = node
                children += 1
                visit(neighbor)
                low[node] = min(low[node], low[neighbor])
                if low[neighbor] > discovery[node]:
                    bridges.append("|".join(sorted((node, neighbor))))
                if parent.get(node) is None and children > 1:
                    articulations.add(node)
                if parent.get(node) is not None and low[neighbor] >= discovery[node]:
                    articulations.add(node)
            elif neighbor != parent.get(node):
                low[node] = min(low[node], discovery[neighbor])

    for node in sorted(adjacency):
        if node not in discovery:
            parent[node] = None
            visit(node)
    return {
        "bridges": sorted(set(bridges)),
        "articulation_vertices": sorted(articulations),
        "bridge_status": "none" if not bridges else "present",
        "two_edge_connected": len(nodes) > 1 and not bridges,
    }


def minimum_spanning_tree(module_ids: Sequence[str], distances: dict[str, float]) -> list[dict[str, Any]]:
    parent = {str(node): str(node) for node in module_ids}

    def root(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    edges: list[dict[str, Any]] = []
    for edge_id, distance in sorted(distances.items(), key=lambda item: (item[1], item[0])):
        left, right = edge_id.split("|", 1)
        left_root, right_root = root(left), root(right)
        if left_root == right_root:
            continue
        parent[left_root] = right_root
        edges.append({"id": edge_id, "a": left, "b": right, "birth_epsilon": float(distance)})
        if len(edges) == len(module_ids) - 1:
            break
    return edges


def graph_at_cut(
    module_ids: Sequence[str],
    distances: dict[str, float],
    epsilon: float,
) -> dict[str, Any]:
    direct = [
        tuple(edge_id.split("|", 1))
        for edge_id, distance in sorted(distances.items())
        if float(distance) <= float(epsilon)
    ]
    components = _component_partition(module_ids, direct)
    component_receipts: list[dict[str, Any]] = []
    for component in components:
        possible = list(itertools.combinations(component, 2))
        component_edges = [edge for edge in direct if edge[0] in component and edge[1] in component]
        pair_distances = [
            float(distances["|".join(pair)])
            if "|".join(pair) in distances
            else float(distances["|".join(reversed(pair))])
            for pair in possible
        ]
        chain_excess = max(0.0, max(pair_distances, default=0.0) - float(epsilon))
        tarjan = tarjan_diagnostics(component, component_edges)
        component_receipts.append(
            {
                "members": component,
                "direct_edge_ids": ["|".join(edge) for edge in component_edges],
                "clique": len(component_edges) == len(possible),
                "chain_excess": chain_excess,
                **tarjan,
            }
        )
    return {
        "epsilon": float(epsilon),
        "direct_edge_ids": ["|".join(edge) for edge in direct],
        "component_count": len(components),
        "components": component_receipts,
    }


def _bands(
    layers: Sequence[int],
    curves: dict[str, list[float]],
    epsilon: float,
) -> list[dict[str, Any]]:
    bands: list[dict[str, Any]] = []
    for edge_id, curve in sorted(curves.items()):
        start: int | None = None
        values: list[float] = []
        for index, distance in enumerate(curve):
            admitted = distance <= epsilon
            if admitted and start is None:
                start = index
            if admitted:
                values.append(float(distance))
            if start is not None and (not admitted or index == len(curve) - 1):
                end = index if admitted and index == len(curve) - 1 else index - 1
                left, right = edge_id.split("|", 1)
                bands.append(
                    {
                        "id": f"{edge_id}:{layers[start]}-{layers[end]}@{epsilon:.2f}",
                        "a": left,
                        "b": right,
                        "start_layer": int(layers[start]),
                        "end_layer": int(layers[end]),
                        "layer_count": end - start + 1,
                        "min_distance": min(values),
                        "max_distance": max(values),
                    }
                )
                start = None
                values = []
    return bands


def _transitions(layers: Sequence[int], snapshots: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    transitions: list[dict[str, Any]] = []
    for index in range(1, len(snapshots)):
        before = set(snapshots[index - 1]["direct_edge_ids"])
        after = set(snapshots[index]["direct_edge_ids"])
        added, removed = sorted(after - before), sorted(before - after)
        if not added and not removed:
            continue
        previous_count = int(snapshots[index - 1]["component_count"])
        current_count = int(snapshots[index]["component_count"])
        kind = (
            "merge" if current_count < previous_count
            else "split" if current_count > previous_count
            else "rewire" if added and removed
            else "reinforce" if added
            else "relax"
        )
        transitions.append(
            {
                "layer": int(layers[index]),
                "kind": kind,
                "added": added,
                "removed": removed,
                "component_count_before": previous_count,
                "component_count_after": current_count,
            }
        )
    return transitions


def build_form_receipt(
    *,
    input_row: dict[str, Any],
    coordinates: np.ndarray,
    module_ids: Sequence[str],
    radii: Sequence[int] = (1, 2, 4),
    epsilons: Sequence[float] = tuple(index / 10 for index in range(1, 10)),
    condition: str = "trained_counterfactual_on_base",
    metric: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    values = np.asarray(coordinates, dtype=np.float64)
    layers = list(range(values.shape[0]))
    radius_receipts: dict[str, Any] = {}
    for radius in radii:
        curves = distance_curves(values, module_ids, int(radius))
        layer_receipts: list[dict[str, Any]] = []
        snapshots_by_cut: dict[str, list[dict[str, Any]]] = {f"{epsilon:.2f}": [] for epsilon in epsilons}
        for layer_index, layer in enumerate(layers):
            distances = {edge_id: float(curve[layer_index]) for edge_id, curve in curves.items()}
            cuts = {}
            for epsilon in epsilons:
                snapshot = graph_at_cut(module_ids, distances, float(epsilon))
                snapshots_by_cut[f"{epsilon:.2f}"].append(snapshot)
                cuts[f"{epsilon:.2f}"] = snapshot
            layer_receipts.append(
                {
                    "layer": layer,
                    "edge_births": distances,
                    "dendrogram_mst": minimum_spanning_tree(module_ids, distances),
                    "cuts": cuts,
                }
            )
        filtration = {}
        for epsilon in epsilons:
            key = f"{epsilon:.2f}"
            filtration[key] = {
                "bands": _bands(layers, curves, float(epsilon)),
                "transitions": _transitions(layers, snapshots_by_cut[key]),
            }
        radius_receipts[str(radius)] = {
            "radius": int(radius),
            "layers": layer_receipts,
            "filtration": filtration,
        }
    return {
        "schema": "pixieology_etale_form_v1",
        "input": {
            key: input_row.get(key)
            for key in ("id", "semantic_group_id", "family", "variant", "split", "outcome_eligible")
        },
        "condition": condition,
        "module_ids": list(module_ids),
        "layer_count": int(values.shape[0]),
        "coordinates": values.tolist(),
        "metric": metric or {
            "id": "globally_normalized_activation_xyz_rms_v1",
            "window_dependent_normalization": False,
            "epsilon_is_confidence_interval": False,
        },
        "radii": radius_receipts,
        "monodromy": {"available": False, "reason": "ordered depth W is an interval with no closed base path"},
        "spin": {"available": False, "reason": "no preregistered closed context cycle in this experiment"},
        "provenance": provenance or {},
    }


def form_descriptor(receipt: dict[str, Any]) -> tuple[list[str], np.ndarray]:
    if receipt.get("schema") != "pixieology_etale_form_v1":
        raise ValueError("invalid form receipt schema")
    names: list[str] = []
    values: list[float] = []

    def add(name: str, value: float) -> None:
        names.append(name)
        values.append(float(value))

    for radius_key in sorted(receipt["radii"], key=int):
        radius = receipt["radii"][radius_key]
        layers = radius["layers"]
        edge_ids = sorted(layers[0]["edge_births"])
        matrix = np.asarray(
            [[float(layer["edge_births"][edge_id]) for edge_id in edge_ids] for layer in layers],
            dtype=np.float64,
        )
        flat = matrix.reshape(-1)
        for label, statistic in (
            ("mean", np.mean(flat)),
            ("std", np.std(flat)),
            ("min", np.min(flat)),
            ("q10", np.quantile(flat, 0.10)),
            ("q25", np.quantile(flat, 0.25)),
            ("median", np.quantile(flat, 0.50)),
            ("q75", np.quantile(flat, 0.75)),
            ("q90", np.quantile(flat, 0.90)),
            ("max", np.max(flat)),
            ("mean_total_variation", np.mean(np.sum(np.abs(np.diff(matrix, axis=0)), axis=0))),
        ):
            add(f"r{radius_key}.distance.{label}", float(statistic))
        mst_births = np.asarray(
            [edge["birth_epsilon"] for layer in layers for edge in layer["dendrogram_mst"]],
            dtype=np.float64,
        )
        add(f"r{radius_key}.mst.mean_birth", float(np.mean(mst_births)))
        add(f"r{radius_key}.mst.max_birth", float(np.max(mst_births)))
        for epsilon_key in sorted(radius["filtration"], key=float):
            snapshots = [layer["cuts"][epsilon_key] for layer in layers]
            components = [component for snapshot in snapshots for component in snapshot["components"] if len(component["members"]) > 1]
            add(f"r{radius_key}.e{epsilon_key}.mean_component_count", np.mean([item["component_count"] for item in snapshots]))
            add(
                f"r{radius_key}.e{epsilon_key}.chain_fraction",
                np.mean([not item["clique"] for item in components]) if components else 0.0,
            )
            add(
                f"r{radius_key}.e{epsilon_key}.mean_chain_excess",
                np.mean([item["chain_excess"] for item in components]) if components else 0.0,
            )
            add(
                f"r{radius_key}.e{epsilon_key}.bridge_free_fraction",
                np.mean([item["bridge_status"] == "none" for item in components]) if components else 0.0,
            )
            add(
                f"r{radius_key}.e{epsilon_key}.mean_bridge_count",
                np.mean([len(item["bridges"]) for item in components]) if components else 0.0,
            )
            filtration = radius["filtration"][epsilon_key]
            transitions = filtration["transitions"]
            denominator = max(1, len(layers) - 1)
            for kind in ("merge", "split", "rewire", "reinforce", "relax"):
                add(
                    f"r{radius_key}.e{epsilon_key}.transition.{kind}",
                    sum(item["kind"] == kind for item in transitions) / denominator,
                )
            bands = filtration["bands"]
            add(
                f"r{radius_key}.e{epsilon_key}.mean_band_fraction",
                np.mean([item["layer_count"] / len(layers) for item in bands]) if bands else 0.0,
            )
    return names, np.asarray(values, dtype=np.float64)
