"""Raw safetensors sharding without importing NumPy or PyTorch tensor loaders."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from typing import Any, BinaryIO, Iterable

from .io import atomic_json, sha256_file, utc_now


@dataclass(frozen=True)
class TensorEntry:
    name: str
    dtype: str
    shape: tuple[int, ...]
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start


def read_header(path: Path) -> tuple[int, dict[str, Any], list[TensorEntry]]:
    with path.open("rb") as handle:
        prefix = handle.read(8)
        if len(prefix) != 8:
            raise ValueError("safetensors file is shorter than its length prefix")
        header_length = struct.unpack("<Q", prefix)[0]
        if header_length <= 1 or header_length > path.stat().st_size - 8:
            raise ValueError("invalid safetensors header length")
        raw_header = handle.read(header_length)
    try:
        header = json.loads(raw_header.decode("utf-8").rstrip(" "))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid safetensors JSON header") from error
    data_start = 8 + header_length
    entries: list[TensorEntry] = []
    for name, metadata in header.items():
        if name == "__metadata__":
            continue
        offsets = metadata.get("data_offsets")
        if not isinstance(offsets, list) or len(offsets) != 2:
            raise ValueError(f"tensor {name} has invalid data offsets")
        start, end = int(offsets[0]), int(offsets[1])
        if start < 0 or end < start or data_start + end > path.stat().st_size:
            raise ValueError(f"tensor {name} exceeds safetensors payload")
        entries.append(
            TensorEntry(
                name=str(name),
                dtype=str(metadata["dtype"]),
                shape=tuple(int(value) for value in metadata["shape"]),
                start=start,
                end=end,
            )
        )
    ordered = sorted(entries, key=lambda entry: (entry.start, entry.end, entry.name))
    previous_end = 0
    for entry in ordered:
        if entry.start < previous_end:
            raise ValueError(f"tensor payloads overlap at {entry.name}")
        previous_end = entry.end
    return data_start, header, ordered


def plan_shards(entries: Iterable[TensorEntry], target_bytes: int) -> list[list[TensorEntry]]:
    if target_bytes <= 0:
        raise ValueError("target shard bytes must be positive")
    shards: list[list[TensorEntry]] = []
    current: list[TensorEntry] = []
    current_size = 0
    for entry in entries:
        if current and current_size + entry.size > target_bytes:
            shards.append(current)
            current = []
            current_size = 0
        current.append(entry)
        current_size += entry.size
        if entry.size > target_bytes:
            shards.append(current)
            current = []
            current_size = 0
    if current:
        shards.append(current)
    return shards


def shard_plan(path: Path, target_bytes: int) -> dict[str, Any]:
    data_start, _, entries = read_header(path)
    shards = plan_shards(entries, target_bytes)
    return {
        "schema": "pixieology_raw_safetensors_shard_plan_v1",
        "source": str(path),
        "source_sha256": "not_computed_header_only",
        "source_size_bytes": path.stat().st_size,
        "data_start": data_start,
        "target_shard_bytes": target_bytes,
        "tensor_count": len(entries),
        "shard_count": len(shards),
        "shards": [
            {
                "index": index,
                "tensor_count": len(shard),
                "payload_bytes": sum(entry.size for entry in shard),
                "atomic_overflow": any(entry.size > target_bytes for entry in shard),
                "tensors": [entry.name for entry in shard],
            }
            for index, shard in enumerate(shards, start=1)
        ],
    }


def _encoded_header(entries: list[TensorEntry], metadata: dict[str, str] | None) -> bytes:
    offset = 0
    header: dict[str, Any] = {}
    if metadata:
        header["__metadata__"] = metadata
    for entry in entries:
        header[entry.name] = {
            "dtype": entry.dtype,
            "shape": list(entry.shape),
            "data_offsets": [offset, offset + entry.size],
        }
        offset += entry.size
    raw = json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    padding = (-len(raw)) % 8
    return raw + b" " * padding


def _copy_range(
    source: BinaryIO,
    destination: BinaryIO,
    *,
    offset: int,
    length: int,
    block_size: int,
) -> str:
    source.seek(offset)
    remaining = length
    digest = hashlib.sha256()
    while remaining:
        block = source.read(min(block_size, remaining))
        if not block:
            raise OSError("unexpected EOF while copying tensor payload")
        destination.write(block)
        digest.update(block)
        remaining -= len(block)
    return digest.hexdigest()


def materialize_shards(
    source_path: Path,
    output_root: Path,
    *,
    target_bytes: int,
    expected_source_sha256: str,
    protocol_sha256: str,
    block_size: int = 8 * 1024 * 1024,
) -> dict[str, Any]:
    source_hash = sha256_file(source_path)
    if source_hash != expected_source_sha256:
        raise ValueError("source checkpoint hash differs from frozen protocol")
    data_start, source_header, entries = read_header(source_path)
    shards = plan_shards(entries, target_bytes)
    output_root.mkdir(parents=True, exist_ok=True)
    weight_map: dict[str, str] = {}
    shard_receipts: list[dict[str, Any]] = []
    with source_path.open("rb") as source:
        for index, shard in enumerate(shards, start=1):
            filename = f"model-{index:05d}-of-{len(shards):05d}.safetensors"
            destination = output_root / filename
            marker = output_root / f"{filename}.complete.json"
            if marker.is_file() and destination.is_file():
                existing = json.loads(marker.read_text(encoding="utf-8"))
                if (
                    existing.get("protocol_sha256") == protocol_sha256
                    and existing.get("source_sha256") == source_hash
                    and existing.get("shard_sha256") == sha256_file(destination)
                    and existing.get("tensors") == [entry.name for entry in shard]
                ):
                    shard_receipts.append(existing)
                    weight_map.update({entry.name: filename for entry in shard})
                    continue
            header = _encoded_header(
                shard,
                {"format": str(source_header.get("__metadata__", {}).get("format", "pt"))},
            )
            descriptor, temporary_name = tempfile.mkstemp(prefix=f".{filename}.", suffix=".tmp", dir=output_root)
            temporary = Path(temporary_name)
            tensor_hashes: dict[str, str] = {}
            try:
                with os.fdopen(descriptor, "wb") as destination_handle:
                    destination_handle.write(struct.pack("<Q", len(header)))
                    destination_handle.write(header)
                    for entry in shard:
                        tensor_hashes[entry.name] = _copy_range(
                            source,
                            destination_handle,
                            offset=data_start + entry.start,
                            length=entry.size,
                            block_size=block_size,
                        )
                    destination_handle.flush()
                    os.fsync(destination_handle.fileno())
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
            destination_data_start, _, destination_entries = read_header(destination)
            destination_by_name = {entry.name: entry for entry in destination_entries}
            with destination.open("rb") as destination_handle:
                for entry in shard:
                    copied = destination_by_name[entry.name]
                    digest = hashlib.sha256()
                    destination_handle.seek(destination_data_start + copied.start)
                    remaining = copied.size
                    while remaining:
                        block = destination_handle.read(min(block_size, remaining))
                        if not block:
                            raise OSError("unexpected EOF while verifying destination tensor")
                        digest.update(block)
                        remaining -= len(block)
                    if digest.hexdigest() != tensor_hashes[entry.name]:
                        raise ValueError(f"raw tensor verification failed for {entry.name}")
            receipt = {
                "schema": "pixieology_raw_safetensors_shard_receipt_v1",
                "index": index,
                "count": len(shards),
                "filename": filename,
                "protocol_sha256": protocol_sha256,
                "source_sha256": source_hash,
                "shard_sha256": sha256_file(destination),
                "tensors": [entry.name for entry in shard],
                "tensor_raw_sha256": tensor_hashes,
                "payload_bytes": sum(entry.size for entry in shard),
                "completed_utc": utc_now(),
            }
            atomic_json(marker, receipt)
            shard_receipts.append(receipt)
            weight_map.update({entry.name: filename for entry in shard})
    index = {
        "metadata": {"total_size": sum(entry.size for entry in entries)},
        "weight_map": weight_map,
    }
    atomic_json(output_root / "model.safetensors.index.json", index)
    manifest = {
        "schema": "pixieology_raw_safetensors_snapshot_v1",
        "protocol_sha256": protocol_sha256,
        "source_sha256": source_hash,
        "source": str(source_path),
        "tensor_count": len(entries),
        "shard_count": len(shards),
        "shards": shard_receipts,
        "index_sha256": sha256_file(output_root / "model.safetensors.index.json"),
        "completed_utc": utc_now(),
    }
    atomic_json(output_root / "snapshot.complete.json", manifest)
    return manifest


def verify_snapshot(
    output_root: Path,
    *,
    protocol_sha256: str,
    source_sha256: str,
    rehash_shards: bool = True,
) -> dict[str, Any]:
    marker_path = output_root / "snapshot.complete.json"
    if not marker_path.is_file():
        raise FileNotFoundError(f"missing sharded snapshot marker {marker_path}")
    manifest = json.loads(marker_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "pixieology_raw_safetensors_snapshot_v1":
        raise ValueError("invalid sharded snapshot schema")
    if manifest.get("protocol_sha256") != protocol_sha256:
        raise ValueError("sharded snapshot belongs to another protocol")
    if manifest.get("source_sha256") != source_sha256:
        raise ValueError("sharded snapshot source hash differs from the frozen model")
    index_path = output_root / "model.safetensors.index.json"
    if not index_path.is_file() or sha256_file(index_path) != manifest.get("index_sha256"):
        raise ValueError("sharded snapshot index hash mismatch")
    checked = 0
    for receipt in manifest.get("shards", []):
        shard_path = output_root / str(receipt["filename"])
        marker = shard_path.with_suffix(shard_path.suffix + ".complete.json")
        if not shard_path.is_file() or not marker.is_file():
            raise ValueError(f"incomplete sharded snapshot artifact {shard_path.name}")
        marker_value = json.loads(marker.read_text(encoding="utf-8"))
        if marker_value != receipt:
            raise ValueError(f"shard marker differs from snapshot manifest for {shard_path.name}")
        if rehash_shards and sha256_file(shard_path) != receipt.get("shard_sha256"):
            raise ValueError(f"shard hash mismatch for {shard_path.name}")
        checked += 1
    if checked != int(manifest.get("shard_count", -1)):
        raise ValueError("sharded snapshot count mismatch")
    return {
        "schema": "pixieology_raw_safetensors_snapshot_verification_v1",
        "status": "PASS",
        "shard_count": checked,
        "rehash_shards": rehash_shards,
        "protocol_sha256": protocol_sha256,
        "source_sha256": source_sha256,
    }
