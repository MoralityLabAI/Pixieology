import json
from pathlib import Path
import struct

from pixie_etale_motifs.io import sha256_file
from pixie_etale_motifs.safetensors_raw import materialize_shards, read_header, shard_plan, verify_snapshot


def _write_fixture(path: Path):
    tensors = {
        "alpha": {"dtype": "U8", "shape": [5], "payload": b"abcde"},
        "beta": {"dtype": "U8", "shape": [7], "payload": b"1234567"},
        "gamma": {"dtype": "U8", "shape": [3], "payload": b"XYZ"},
    }
    offset = 0
    header = {"__metadata__": {"format": "pt"}}
    for name, value in tensors.items():
        payload = value["payload"]
        header[name] = {
            "dtype": value["dtype"],
            "shape": value["shape"],
            "data_offsets": [offset, offset + len(payload)],
        }
        offset += len(payload)
    encoded = json.dumps(header, separators=(",", ":")).encode("utf-8")
    encoded += b" " * ((-len(encoded)) % 8)
    with path.open("wb") as handle:
        handle.write(struct.pack("<Q", len(encoded)))
        handle.write(encoded)
        for value in tensors.values():
            handle.write(value["payload"])
    return tensors


def test_raw_sharder_preserves_tensor_payload_bytes(tmp_path):
    source = tmp_path / "model.safetensors"
    tensors = _write_fixture(source)
    plan = shard_plan(source, 10)
    assert plan["tensor_count"] == 3
    assert plan["shard_count"] == 2
    output = tmp_path / "sharded"
    manifest = materialize_shards(
        source,
        output,
        target_bytes=10,
        expected_source_sha256=sha256_file(source),
        protocol_sha256="protocol-fixture",
        block_size=2,
    )
    assert manifest["shard_count"] == 2
    verification = verify_snapshot(
        output,
        protocol_sha256="protocol-fixture",
        source_sha256=sha256_file(source),
    )
    assert verification["status"] == "PASS"
    index = json.loads((output / "model.safetensors.index.json").read_text(encoding="utf-8"))
    for name, expected in tensors.items():
        shard = output / index["weight_map"][name]
        data_start, _, entries = read_header(shard)
        entry = next(item for item in entries if item.name == name)
        with shard.open("rb") as handle:
            handle.seek(data_start + entry.start)
            assert handle.read(entry.size) == expected["payload"]


def test_raw_sharder_resumes_only_verified_markers(tmp_path):
    source = tmp_path / "model.safetensors"
    _write_fixture(source)
    output = tmp_path / "sharded"
    first = materialize_shards(
        source,
        output,
        target_bytes=8,
        expected_source_sha256=sha256_file(source),
        protocol_sha256="protocol-fixture",
    )
    second = materialize_shards(
        source,
        output,
        target_bytes=8,
        expected_source_sha256=sha256_file(source),
        protocol_sha256="protocol-fixture",
    )
    assert [item["shard_sha256"] for item in first["shards"]] == [
        item["shard_sha256"] for item in second["shards"]
    ]
