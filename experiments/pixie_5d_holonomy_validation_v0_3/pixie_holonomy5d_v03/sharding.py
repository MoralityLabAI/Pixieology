"""Deterministically rewrite one safetensors file into bounded verified shards."""

from __future__ import annotations

from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

from .protocol import sha256_file


class ShardingError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    os.close(descriptor)
    try:
        shutil.copyfile(source, temporary)
        with Path(temporary).open("r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _read_header(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        prefix = handle.read(8)
        if len(prefix) != 8:
            raise ShardingError(f"safetensors header is truncated: {path}")
        header_length = int.from_bytes(prefix, "little", signed=False)
        if header_length <= 0 or header_length > path.stat().st_size - 8:
            raise ShardingError(f"safetensors header length is invalid: {path}")
        try:
            header = json.loads(handle.read(header_length))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ShardingError(f"safetensors header JSON is invalid: {error}") from error
    if not isinstance(header, dict):
        raise ShardingError("safetensors header is not an object")
    return header


def plan_shards(source_weights: Path, maximum_shard_bytes: int) -> list[list[dict[str, Any]]]:
    """Plan stable tensor-boundary shards without loading tensor payloads."""
    if maximum_shard_bytes <= 0:
        raise ValueError("maximum_shard_bytes must be positive")
    header = _read_header(source_weights)
    tensors: list[dict[str, Any]] = []
    for name in sorted(key for key in header if key != "__metadata__"):
        entry = header[name]
        if not isinstance(entry, dict) or "data_offsets" not in entry:
            raise ShardingError(f"invalid tensor header: {name}")
        start, end = (int(value) for value in entry["data_offsets"])
        if start < 0 or end < start:
            raise ShardingError(f"invalid tensor offsets: {name}")
        tensors.append(
            {
                "name": name,
                "dtype": str(entry["dtype"]),
                "shape": [int(value) for value in entry["shape"]],
                "nbytes": end - start,
            }
        )
    if not tensors:
        raise ShardingError("source checkpoint contains no tensors")
    shards: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_bytes = 0
    for tensor in tensors:
        if current and current_bytes + tensor["nbytes"] > maximum_shard_bytes:
            shards.append(current)
            current = []
            current_bytes = 0
        current.append(tensor)
        current_bytes += int(tensor["nbytes"])
    if current:
        shards.append(current)
    return shards


def _tensor_sha256(tensor: Any) -> str:
    contiguous = tensor.detach().cpu().contiguous().view(__import__("torch").uint8).reshape(-1)
    digest = hashlib.sha256()
    digest.update(memoryview(contiguous.numpy()))
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _valid_shard_marker(
    marker_path: Path,
    shard_path: Path,
    *,
    protocol_hash: str,
    source_hash: str,
    expected_names: list[str],
) -> dict[str, Any] | None:
    value = _read_json(marker_path)
    if value is None or not shard_path.is_file():
        return None
    if (
        value.get("schema") != "pixie_safetensors_shard_v3"
        or value.get("protocol_sha256") != protocol_hash
        or value.get("source_weights_sha256") != source_hash
        or value.get("tensor_names") != expected_names
        or value.get("shard_sha256") != sha256_file(shard_path)
    ):
        return None
    tensors = value.get("tensors", {})
    return value if isinstance(tensors, dict) and sorted(tensors) == expected_names else None


def verify_sharded_snapshot(
    output_root: Path,
    *,
    protocol_hash: str,
    source_hash: str,
) -> dict[str, Any]:
    complete = _read_json(output_root / "sharded_snapshot.complete.json")
    manifest = _read_json(output_root / "sharding_manifest.json")
    if complete is None or manifest is None:
        raise ShardingError(f"sharded snapshot is incomplete: {output_root}")
    if (
        complete.get("schema") != "pixie_sharded_snapshot_complete_v3"
        or complete.get("protocol_sha256") != protocol_hash
        or complete.get("source_weights_sha256") != source_hash
        or manifest.get("protocol_sha256") != protocol_hash
        or manifest.get("source_weights_sha256") != source_hash
    ):
        raise ShardingError("sharded snapshot lineage differs from protocol")
    files = complete.get("files", {})
    if not isinstance(files, dict) or not files:
        raise ShardingError("sharded snapshot completion marker has no files")
    for relative, expected in files.items():
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ShardingError(f"unsafe completion-marker path: {relative}")
        path = output_root / candidate
        if not path.is_file() or sha256_file(path) != expected:
            raise ShardingError(f"sharded snapshot file mismatch: {path}")
    return manifest


def _quarantine_stale(output_root: Path) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = output_root.with_name(f"{output_root.name}.quarantine-{stamp}")
    output_root.replace(destination)


def prepare_sharded_snapshot(
    source_root: Path,
    output_root: Path,
    protocol: Mapping[str, Any],
    protocol_hash: str,
    event_callback: Any | None = None,
) -> dict[str, Any]:
    """Create or resume a byte-verified, tensor-boundary sharded snapshot."""
    from safetensors import safe_open
    from safetensors.torch import save_file

    source_weights = source_root / protocol["model"]["weights_file"]
    source_hash = protocol["model"]["weights_sha256"]
    if sha256_file(source_weights) != source_hash:
        raise ShardingError("source model.safetensors hash differs from protocol")
    if output_root.is_dir():
        try:
            return verify_sharded_snapshot(output_root, protocol_hash=protocol_hash, source_hash=source_hash)
        except ShardingError:
            build_state = _read_json(output_root / "build_state.json")
            if not build_state or build_state.get("protocol_sha256") != protocol_hash:
                _quarantine_stale(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    _atomic_json(
        output_root / "build_state.json",
        {
            "schema": "pixie_sharded_snapshot_build_v3",
            "protocol_sha256": protocol_hash,
            "source_weights_sha256": source_hash,
            "started_or_resumed_utc": _utc_now(),
        },
    )
    support_hashes: dict[str, str] = {}
    for name, expected in protocol["model"]["support_files"].items():
        source = source_root / name
        if sha256_file(source) != expected:
            raise ShardingError(f"source support file differs from protocol: {source}")
        destination = output_root / name
        if not destination.is_file() or sha256_file(destination) != expected:
            _atomic_copy(source, destination)
        support_hashes[name] = expected

    target = int(protocol["sharding"]["target_shard_bytes"])
    plans = plan_shards(source_weights, target)
    shard_count = len(plans)
    shard_receipts: list[dict[str, Any]] = []
    weight_map: dict[str, str] = {}
    for index, plan in enumerate(plans, start=1):
        shard_name = f"model-{index:05d}-of-{shard_count:05d}.safetensors"
        shard_path = output_root / shard_name
        marker_path = output_root / f"{shard_name}.complete.json"
        names = [str(item["name"]) for item in plan]
        receipt = _valid_shard_marker(
            marker_path,
            shard_path,
            protocol_hash=protocol_hash,
            source_hash=source_hash,
            expected_names=names,
        )
        if receipt is None:
            if shard_path.exists():
                shard_path.unlink()
            if marker_path.exists():
                marker_path.unlink()
            if event_callback:
                event_callback({"event": "shard_started", "index": index, "count": shard_count, "utc": _utc_now()})
            with safe_open(source_weights, framework="pt", device="cpu") as source:
                tensors = {name: source.get_tensor(name) for name in names}
                tensor_receipts = {
                    item["name"]: {
                        "dtype": item["dtype"],
                        "shape": item["shape"],
                        "nbytes": item["nbytes"],
                        "sha256": _tensor_sha256(tensors[item["name"]]),
                    }
                    for item in plan
                }
                temporary = output_root / f".{shard_name}.partial"
                save_file(tensors, temporary, metadata={"format": "pt"})
                with temporary.open("r+b") as handle:
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, shard_path)
                del tensors
            with safe_open(shard_path, framework="pt", device="cpu") as written:
                for item in plan:
                    name = item["name"]
                    tensor = written.get_tensor(name)
                    if list(tensor.shape) != item["shape"] or _tensor_sha256(tensor) != tensor_receipts[name]["sha256"]:
                        raise ShardingError(f"written tensor verification failed: {name}")
            receipt = {
                "schema": "pixie_safetensors_shard_v3",
                "protocol_sha256": protocol_hash,
                "source_weights_sha256": source_hash,
                "shard": shard_name,
                "shard_index": index,
                "shard_count": shard_count,
                "tensor_names": names,
                "tensors": tensor_receipts,
                "shard_sha256": sha256_file(shard_path),
                "completed_utc": _utc_now(),
            }
            _atomic_json(marker_path, receipt)
            if event_callback:
                event_callback({"event": "shard_complete", "index": index, "count": shard_count, "utc": _utc_now()})
            gc.collect()
        shard_receipts.append(receipt)
        for name in names:
            weight_map[name] = shard_name

    total_size = sum(int(item["nbytes"]) for plan in plans for item in plan)
    index_path = output_root / "model.safetensors.index.json"
    _atomic_json(index_path, {"metadata": {"total_size": total_size}, "weight_map": weight_map})
    manifest = {
        "schema": "pixie_sharding_manifest_v3",
        "protocol_sha256": protocol_hash,
        "source_weights_sha256": source_hash,
        "method": protocol["sharding"]["method"],
        "target_shard_bytes": target,
        "atomic_tensor_overflow_allowed": bool(protocol["sharding"]["atomic_tensor_overflow_allowed"]),
        "shard_count": shard_count,
        "tensor_count": len(weight_map),
        "total_tensor_bytes": total_size,
        "support_files": support_hashes,
        "shards": shard_receipts,
        "completed_utc": _utc_now(),
    }
    manifest_path = output_root / "sharding_manifest.json"
    _atomic_json(manifest_path, manifest)
    files = {
        **support_hashes,
        "model.safetensors.index.json": sha256_file(index_path),
        "sharding_manifest.json": sha256_file(manifest_path),
    }
    for receipt in shard_receipts:
        files[receipt["shard"]] = receipt["shard_sha256"]
        marker_name = f"{receipt['shard']}.complete.json"
        files[marker_name] = sha256_file(output_root / marker_name)
    _atomic_json(
        output_root / "sharded_snapshot.complete.json",
        {
            "schema": "pixie_sharded_snapshot_complete_v3",
            "protocol_sha256": protocol_hash,
            "source_weights_sha256": source_hash,
            "files": files,
            "completed_utc": _utc_now(),
        },
    )
    return verify_sharded_snapshot(output_root, protocol_hash=protocol_hash, source_hash=source_hash)
