import itertools

import numpy as np

from pixie_etale_motifs.geometry import (
    apply_global_scaler,
    compact_update_svd,
    fit_global_scaler,
    response_coordinates,
)
from pixie_etale_motifs.graph import (
    build_distance_prefixes,
    build_form_receipt,
    form_descriptor,
    graph_at_cut,
    window_distance,
)


MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def test_compact_svd_matches_materialized_update_and_response_energy():
    rng = np.random.default_rng(17)
    a = rng.normal(size=(4, 11))
    b = rng.normal(size=(13, 4))
    scale = 1.7
    compact = compact_update_svd(a, b, scale)
    materialized = scale * b @ a
    expected = np.linalg.svd(materialized, compute_uv=False)
    assert np.allclose(compact.singular_values, expected[: compact.effective_rank])
    x = rng.normal(size=11)
    base = rng.normal(size=13)
    coordinates = response_coordinates(x, base, compact)
    assert np.isclose(np.expm1(coordinates[0]) * np.linalg.norm(base), np.linalg.norm(materialized @ x))
    assert 0.0 < coordinates[1] <= 1.0
    assert 0.0 < coordinates[2] <= 1.0


def test_global_scaler_is_window_invariant_and_clipped():
    values = np.arange(90, dtype=np.float64).reshape(10, 3, 3)
    scaler = fit_global_scaler(values, lower_quantile=0.0, upper_quantile=1.0)
    first = apply_global_scaler(values, scaler)
    second = apply_global_scaler(values[2:7], scaler)
    assert np.allclose(first[2:7], second)
    assert np.min(first) == 0.0
    assert np.max(first) == 1.0
    assert scaler.to_dict()["window_dependent"] is False


def test_prefix_window_distances_equal_brute_force():
    rng = np.random.default_rng(21)
    coordinates = rng.random((28, 7, 3))
    prefixes = build_distance_prefixes(coordinates, MODULES)
    for left_index, right_index in itertools.combinations(range(7), 2):
        edge_id = f"{MODULES[left_index]}|{MODULES[right_index]}"
        for center in (0, 5, 13, 27):
            for radius in (1, 2, 4):
                lower, upper = max(0, center - radius), min(27, center + radius)
                brute = np.sqrt(np.mean((coordinates[lower : upper + 1, left_index] - coordinates[lower : upper + 1, right_index]) ** 2))
                assert np.isclose(window_distance(prefixes[edge_id], center, radius, 28), brute)


def test_chain_excess_and_tarjan_distinguish_chain_from_robust_clique():
    modules = ["a", "b", "c"]
    chain = graph_at_cut(modules, {"a|b": 0.1, "a|c": 0.3, "b|c": 0.1}, 0.2)
    component = chain["components"][0]
    assert component["members"] == modules
    assert component["clique"] is False
    assert np.isclose(component["chain_excess"], 0.1)
    assert component["bridges"] == ["a|b", "b|c"]
    assert component["articulation_vertices"] == ["b"]

    clique = graph_at_cut(modules, {"a|b": 0.1, "a|c": 0.1, "b|c": 0.1}, 0.2)
    robust = clique["components"][0]
    assert robust["clique"] is True
    assert robust["chain_excess"] == 0.0
    assert robust["bridge_status"] == "none"
    assert robust["two_edge_connected"] is True


def test_form_receipt_exposes_full_filtration_and_fixed_descriptor():
    rng = np.random.default_rng(22)
    coordinates = rng.random((28, 7, 3))
    receipt = build_form_receipt(
        input_row={
            "id": "fixture",
            "semantic_group_id": "fixture-group",
            "family": "fixture",
            "variant": "canonical",
            "split": "discovery",
            "outcome_eligible": True,
        },
        coordinates=coordinates,
        module_ids=MODULES,
    )
    assert receipt["spin"]["available"] is False
    assert receipt["monodromy"]["available"] is False
    assert set(receipt["radii"]) == {"1", "2", "4"}
    assert len(receipt["radii"]["2"]["layers"][0]["edge_births"]) == 21
    assert len(receipt["radii"]["2"]["layers"][0]["dendrogram_mst"]) == 6
    names, descriptor = form_descriptor(receipt)
    assert len(names) == len(descriptor)
    assert len(names) > 300
    assert np.all(np.isfinite(descriptor))
