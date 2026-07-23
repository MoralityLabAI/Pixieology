"""Protocol, job, and source-integrity checks for capture v0.2."""

from __future__ import annotations

import copy
import hashlib
from importlib import metadata, util
import json
from pathlib import Path
import sys
from typing import Any


PROTOCOL_SCHEMA = "pixie_etale_motif_capture_protocol_v2"
PROTOCOL_LOCK_SCHEMA = "pixie_etale_motif_capture_protocol_lock_v2"
JOB_SCHEMA = "pixie_etale_capture_job_v2"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def object_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def load_protocol(experiment_root: Path) -> dict[str, Any]:
    value = json.loads((experiment_root / "protocol.json").read_text(encoding="utf-8"))
    if value.get("schema") != PROTOCOL_SCHEMA:
        raise ValueError(f"protocol schema must be {PROTOCOL_SCHEMA}")
    return value


def protocol_hash(experiment_root: Path) -> str:
    return sha256_file(experiment_root / "protocol.json")


def source_root(experiment_root: Path, protocol: dict[str, Any]) -> Path:
    return (experiment_root / str(protocol["source_experiment"]["path"])).resolve()


def activate_source_imports(experiment_root: Path, protocol: dict[str, Any]) -> Path:
    root = source_root(experiment_root, protocol)
    text = str(root)
    if text not in sys.path:
        sys.path.insert(0, text)
    return root


def job_sha256(job: dict[str, Any]) -> str:
    value = copy.deepcopy(job)
    value.setdefault("authorization", {})["job_sha256"] = None
    return object_sha256(value)


def validate_job(job: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    if job.get("schema") != JOB_SCHEMA:
        raise ValueError("invalid capture v0.2 job schema")
    if job.get("status") != "PROPOSED":
        raise ValueError("capture v0.2 job must remain proposed before execution")
    if job.get("job_id") != "capture-pixie-canary-memory-optimized-v0_2":
        raise ValueError("unexpected capture v0.2 job ID")
    if job.get("source_protocol_sha256") != protocol["source_experiment"]["protocol_sha256"]:
        raise ValueError("job is bound to another source protocol")
    if job.get("source_corpus_sha256") != protocol["corpus"]["generated_sha256"]:
        raise ValueError("job is bound to another source corpus")
    if int(job.get("chunk_index", -1)) != int(protocol["corpus"]["target_chunk_index"]):
        raise ValueError("job chunk differs from the target canary chunk")
    if job.get("family") != protocol["corpus"]["target_family"]:
        raise ValueError("job family differs from the target canary family")
    if int(job.get("row_count", -1)) != int(protocol["corpus"]["chunk_rows"]):
        raise ValueError("job row count differs from the frozen chunk")
    if int(job.get("checkpoint_rows", -1)) != int(protocol["corpus"]["checkpoint_rows"]):
        raise ValueError("job checkpoint cadence differs from the frozen plan")
    if job.get("splits") != protocol["corpus"]["target_split_rows"]:
        raise ValueError("job split composition differs from the frozen plan")
    if job.get("loader_strategy") != protocol["loader"]["strategy"]:
        raise ValueError("job loader differs from the v0.2 protocol")
    if job.get("caps") != protocol["resources"]["capture_requested_not_authorized"]:
        raise ValueError("job caps differ from the v0.2 protocol")
    if job.get("gpu_guard") != protocol["resources"]["gpu"]:
        raise ValueError("job GPU guard differs from the v0.2 protocol")
    authorization = job.get("authorization", {})
    if authorization.get("required") is not True or authorization.get("automatic_authorization") is not False:
        raise ValueError("job authorization policy is not fail-closed")
    if authorization.get("job_sha256") != job_sha256(job):
        raise ValueError("job hash mismatch")
    return job


def load_job(experiment_root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    value = json.loads((experiment_root / "proposed_job.json").read_text(encoding="utf-8"))
    return validate_job(value, protocol)


def protocol_lock_checks(experiment_root: Path, protocol: dict[str, Any]) -> dict[str, bool]:
    lock_path = experiment_root / "protocol.lock.json"
    if not lock_path.is_file():
        return {"protocol_lock_present": False}
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {
        "protocol_lock_present": True,
        "protocol_lock_schema": lock.get("schema") == PROTOCOL_LOCK_SCHEMA,
        "protocol_lock_protocol": lock.get("protocol_sha256") == protocol_hash(experiment_root),
        "protocol_lock_source_protocol": (
            lock.get("source_protocol_sha256") == protocol["source_experiment"]["protocol_sha256"]
        ),
        "protocol_lock_source_implementation": (
            lock.get("source_implementation_lock_sha256")
            == protocol["source_experiment"]["implementation_lock_sha256"]
        ),
    }
    for relative, expected in lock.get("files", {}).items():
        path = (experiment_root / str(relative)).resolve()
        checks[f"protocol_lock:{relative}"] = path.is_file() and sha256_file(path) == expected
    for relative, expected in lock.get("source_files", {}).items():
        path = (experiment_root / str(relative)).resolve()
        checks[f"source_lock:{relative}"] = path.is_file() and sha256_file(path) == expected
    checks["protocol_lock_has_files"] = bool(lock.get("files"))
    checks["protocol_lock_has_source_files"] = bool(lock.get("source_files"))
    return checks


def _source_protocol_checks(experiment_root: Path, protocol: dict[str, Any]) -> dict[str, bool]:
    root = source_root(experiment_root, protocol)
    return {
        "source_protocol_present": (root / "protocol.json").is_file(),
        "source_protocol_hash": (
            (root / "protocol.json").is_file()
            and sha256_file(root / "protocol.json") == protocol["source_experiment"]["protocol_sha256"]
        ),
        "source_lock_present": (root / "protocol.lock.json").is_file(),
        "source_lock_hash": (
            (root / "protocol.lock.json").is_file()
            and sha256_file(root / "protocol.lock.json")
            == protocol["source_experiment"]["implementation_lock_sha256"]
        ),
    }


def verify_protocol_shape(protocol: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if protocol.get("status") != "STAGED_NOT_AUTHORIZED":
        errors.append("protocol status must remain STAGED_NOT_AUTHORIZED")
    expected_caps = {"ram_mb": 6144, "cpu_pct": 50, "io_mb_s": 250, "timeout_seconds": 1800}
    if protocol.get("resources", {}).get("capture_requested_not_authorized") != expected_caps:
        errors.append("capture caps must remain 6144/50/250/1800")
    expected_gpu = {
        "maximum_existing_memory_mib": 256,
        "maximum_peak_memory_mib": 3900,
        "require_no_compute_applications": True,
    }
    if protocol.get("resources", {}).get("gpu") != expected_gpu:
        errors.append("GPU guard differs from the registered v0.2 plan")
    loader = protocol.get("loader", {})
    required_loader = {
        "strategy": "sequential_safetensors_materialization_v2",
        "use_safetensors": True,
        "deactivate_async_load": True,
        "async_load_environment_variable": "HF_DEACTIVATE_ASYNC_LOAD",
        "defer_peft_import_until_base_loaded": True,
        "rehash_shards": True,
    }
    for key, expected in required_loader.items():
        if loader.get(key) != expected:
            errors.append(f"loader.{key} must be {expected!r}")
    corpus = protocol.get("corpus", {})
    if corpus.get("target_chunk_index") != 0 or corpus.get("target_family") != "pixie_canary":
        errors.append("v0.2 must remain bound to canary chunk 0")
    if corpus.get("checkpoint_rows") != 8:
        errors.append("capture must checkpoint every eight rows")
    return errors


def verify(
    repo_root: Path,
    experiment_root: Path,
    *,
    rehash_shards: bool = False,
) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    shape_errors = verify_protocol_shape(protocol)
    checks: dict[str, Any] = {
        "protocol_shape": not shape_errors,
        "protocol_shape_errors": shape_errors,
    }
    checks.update(_source_protocol_checks(experiment_root, protocol))
    for distribution, expected in protocol.get("software", {}).items():
        try:
            checks[f"software:{distribution}"] = metadata.version(distribution) == expected
        except metadata.PackageNotFoundError:
            checks[f"software:{distribution}"] = False
    transformers_spec = util.find_spec("transformers")
    core_loader = (
        None
        if transformers_spec is None or transformers_spec.origin is None
        else Path(transformers_spec.origin).resolve().parent / "core_model_loading.py"
    )
    if core_loader is not None and core_loader.is_file():
        core_text = core_loader.read_text(encoding="utf-8")
        checks["transformers_sequential_guard"] = (
            'is_env_variable_true("HF_DEACTIVATE_ASYNC_LOAD")' in core_text
            and "thread_pool = None" in core_text
        )
    else:
        checks["transformers_sequential_guard"] = False
    lock_checks = protocol_lock_checks(experiment_root, protocol)
    checks["implementation_lock"] = all(lock_checks.values())
    checks["implementation_lock_checks"] = lock_checks
    try:
        job = load_job(experiment_root, protocol)
        checks["job"] = True
        checks["job_sha256"] = job_sha256(job) == job["authorization"]["job_sha256"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        job = {}
        checks["job"] = False
        checks["job_error"] = f"{type(error).__name__}: {error}"
    if all(value for value in _source_protocol_checks(experiment_root, protocol).values()):
        activate_source_imports(experiment_root, protocol)
        from pixie_etale_motifs.protocol import (
            build_corpus_from_protocol,
            load_protocol as load_source_protocol,
            load_repo_config,
            resolve_config_path,
            verify_frozen_inputs,
        )
        from pixie_etale_motifs.safetensors_raw import verify_snapshot

        source = source_root(experiment_root, protocol)
        source_protocol = load_source_protocol(source)
        frozen = verify_frozen_inputs(repo_root, source, require_weights=False)
        checks["source_frozen_inputs"] = bool(frozen["ok"])
        checks["source_frozen_checks"] = frozen["checks"]
        rows = build_corpus_from_protocol(source_protocol)
        start = int(protocol["corpus"]["target_chunk_index"]) * int(protocol["corpus"]["chunk_rows"])
        selected = rows[start : start + int(protocol["corpus"]["chunk_rows"])]
        split_counts = {
            split: sum(row["split"] == split for row in selected)
            for split in ("discovery", "confirmation", "transfer")
        }
        checks["target_chunk_rows"] = len(selected) == int(protocol["corpus"]["chunk_rows"])
        checks["target_chunk_family"] = all(
            row["family"] == protocol["corpus"]["target_family"] for row in selected
        )
        checks["target_chunk_splits"] = split_counts == protocol["corpus"]["target_split_rows"]
        config = load_repo_config(repo_root)
        sharded = resolve_config_path(repo_root, config, "pixie_etale_motif_sharded_model_root")
        try:
            snapshot = verify_snapshot(
                sharded,
                protocol_sha256=protocol["source_experiment"]["protocol_sha256"],
                source_sha256=protocol["model"]["weights_sha256"],
                rehash_shards=rehash_shards,
            )
            checks["sharded_snapshot"] = snapshot["status"] == "PASS"
            checks["sharded_snapshot_receipt"] = snapshot
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as error:
            checks["sharded_snapshot"] = False
            checks["sharded_snapshot_error"] = f"{type(error).__name__}: {error}"
        output_root = resolve_config_path(repo_root, config, "pixie_etale_motif_output_root")
    else:
        frozen = {}
        sharded = Path()
        output_root = Path()
    boolean_checks = [value for value in checks.values() if isinstance(value, bool)]
    return {
        "schema": "pixie_etale_motif_capture_verification_v2",
        "ok": all(boolean_checks),
        "checks": checks,
        "job": job,
        "source": frozen,
        "sharded_root": str(sharded),
        "output_root": str(output_root),
    }
