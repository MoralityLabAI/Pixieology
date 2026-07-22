from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import torch
from safetensors.torch import save_file

from pixie_holonomy5d_v03.sharding import ShardingError, plan_shards, prepare_sharded_snapshot, verify_sharded_snapshot


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
    source = tmp_path / "source"
    output = tmp_path / "sharded"
    source.mkdir()
    save_file(
        {
            "a": torch.arange(16, dtype=torch.float32),
            "b": torch.arange(24, dtype=torch.float16).reshape(6, 4),
            "c": torch.arange(8, dtype=torch.int64),
        },
        source / "model.safetensors",
        metadata={"format": "pt"},
    )
    (source / "config.json").write_text('{"model_type":"fixture"}\n', encoding="utf-8")
    protocol = {
        "model": {
            "weights_file": "model.safetensors",
            "weights_sha256": _hash(source / "model.safetensors"),
            "support_files": {"config.json": _hash(source / "config.json")},
        },
        "sharding": {
            "method": "deterministic_safetensors_tensor_shards_v1",
            "target_shard_bytes": 80,
            "atomic_tensor_overflow_allowed": True,
        },
    }
    return source, output, protocol


def test_plan_uses_tensor_boundaries_and_stable_order(tmp_path: Path) -> None:
    source, _, _ = _fixture(tmp_path)
    plan = plan_shards(source / "model.safetensors", 80)
    assert [[item["name"] for item in shard] for shard in plan] == [["a"], ["b"], ["c"]]


def test_prepare_is_verified_and_idempotent(tmp_path: Path) -> None:
    source, output, protocol = _fixture(tmp_path)
    first = prepare_sharded_snapshot(source, output, protocol, "protocol")
    second = prepare_sharded_snapshot(source, output, protocol, "protocol")
    assert first["tensor_count"] == 3
    assert first["shard_count"] == 3
    assert first == second
    assert verify_sharded_snapshot(output, protocol_hash="protocol", source_hash=protocol["model"]["weights_sha256"])


def test_tampered_shard_fails_closed(tmp_path: Path) -> None:
    source, output, protocol = _fixture(tmp_path)
    manifest = prepare_sharded_snapshot(source, output, protocol, "protocol")
    shard = output / manifest["shards"][0]["shard"]
    shard.write_bytes(shard.read_bytes() + b"tamper")
    with pytest.raises(ShardingError, match="file mismatch"):
        verify_sharded_snapshot(output, protocol_hash="protocol", source_hash=protocol["model"]["weights_sha256"])
