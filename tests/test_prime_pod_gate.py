from __future__ import annotations

from types import SimpleNamespace

import pytest

from experiments.fae_tax_epistemics_v1 import prime_pod_gate as gate


def offer(
    *,
    cloud_id: str = "eligible",
    gpu_type: str = "A100_80GB",
    gpu_count: int = 1,
    gpu_memory: int = 81920,
    hourly: float = 3.0,
    is_spot: bool = False,
    disk: int = 100,
):
    return SimpleNamespace(
        cloud_id=cloud_id,
        gpu_type=gpu_type,
        gpu_count=gpu_count,
        gpu_memory=gpu_memory,
        provider="fixture",
        socket="SXM4",
        security="secure_cloud",
        country="US",
        data_center="test-1",
        stock_status="Available",
        prices=SimpleNamespace(price=hourly, is_variable=False),
        is_spot=is_spot,
        disk=SimpleNamespace(default_count=disk),
        vcpu=SimpleNamespace(default_count=16),
        memory=SimpleNamespace(default_count=128),
        images=["cuda_12_6_pytorch_2_7", "ubuntu_22_cuda_12"],
    )


def test_candidate_gate_enforces_gpu_memory_count_cost_and_disk():
    assert gate.candidate_from_offer(offer(), max_hourly_usd=5.0) is not None
    assert gate.candidate_from_offer(offer(gpu_count=2), max_hourly_usd=5.0) is None
    assert gate.candidate_from_offer(offer(gpu_memory=40960), max_hourly_usd=5.0) is None
    assert gate.candidate_from_offer(offer(hourly=5.01), max_hourly_usd=5.0) is None
    assert gate.candidate_from_offer(offer(disk=50), max_hourly_usd=5.0) is None


def test_candidate_order_prefers_on_demand_before_spot():
    availability = {
        "A100_80GB": [
            offer(cloud_id="spot", hourly=1.0, is_spot=True),
            offer(cloud_id="on-demand", hourly=3.0, is_spot=False),
        ]
    }
    rows = gate.eligible_candidates(availability, max_hourly_usd=5.0)
    assert [row.cloud_id for row in rows] == ["on-demand", "spot"]


def test_pod_config_has_price_and_restart_guards():
    candidate = gate.candidate_from_offer(offer(), max_hourly_usd=5.0)
    assert candidate is not None
    config = gate.pod_config(candidate, name="fae-tax")
    assert config["pod"]["gpuCount"] == 1
    assert config["pod"]["maxPrice"] == 3.0
    assert config["pod"]["autoRestart"] is False
    assert config["pod"]["image"] == "cuda_12_6_pytorch_2_7"
    with pytest.raises(gate.PrimeGateError):
        gate.pod_config(candidate, name="fae-tax", image="not-offered")


def test_variable_price_offer_is_rejected():
    variable = offer()
    variable.prices.is_variable = True
    assert gate.candidate_from_offer(variable, max_hourly_usd=5.0) is None


def test_study_limits_imply_five_dollar_hourly_ceiling():
    max_cost, max_hours = gate.study_limits(gate.DEFAULT_MANIFEST)
    assert max_cost == 40.0
    assert max_hours == 8.0
    assert max_cost / max_hours == 5.0
