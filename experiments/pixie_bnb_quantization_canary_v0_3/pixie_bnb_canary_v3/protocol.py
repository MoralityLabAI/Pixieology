"""Protocol, job, runtime, and implementation integrity checks."""

from __future__ import annotations

import copy
import hashlib
from importlib import metadata, util
import json
from pathlib import Path
import platform
import subprocess
from typing import Any


PROTOCOL_SCHEMA = "pixie_bnb_quantization_canary_protocol_v3"
PROTOCOL_LOCK_SCHEMA = "pixie_bnb_quantization_canary_protocol_lock_v3"
JOB_SCHEMA = "pixie_bnb_quantization_canary_job_v3"


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


def job_sha256(job: dict[str, Any]) -> str:
    value = copy.deepcopy(job)
    value.setdefault("authorization", {})["job_sha256"] = None
    return object_sha256(value)


def validate_job(job: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    if job.get("schema") != JOB_SCHEMA:
        raise ValueError("invalid quantization canary job schema")
    if job.get("status") != "PROPOSED":
        raise ValueError("quantization canary job must remain proposed")
    if job.get("job_id") != "diagnose-bnb4bit-c10-boundary-host-v0_3_1":
        raise ValueError("unexpected quantization canary job ID")
    canary = protocol["canary"]
    if int(job.get("seed", -1)) != int(canary["seed"]):
        raise ValueError("job seed differs from protocol")
    if int(job.get("case_count", -1)) != len(canary["cases"]):
        raise ValueError("job case count differs from protocol")
    sweep = next(case for case in canary["cases"] if case["kind"] == "resident_sweep")
    if int(job.get("sweep_layers", -1)) != int(sweep["layers"]):
        raise ValueError("job sweep layer count differs from protocol")
    if int(job.get("sweep_projections_per_layer", -1)) != len(sweep["projections"]):
        raise ValueError("job sweep projection count differs from protocol")
    if int(job.get("checkpoint_every_operations", -1)) != 1:
        raise ValueError("job must checkpoint every operation")
    if job.get("model_loading") is not False or job.get("adapter_loading") is not False:
        raise ValueError("diagnostic job cannot load a model or adapter")
    if job.get("synthetic_weights_only") is not True:
        raise ValueError("diagnostic job must use synthetic weights only")
    if job.get("caps") != protocol["resources"]["canary_requested_not_authorized"]:
        raise ValueError("job caps differ from protocol")
    if job.get("gpu_guard") != protocol["resources"]["gpu"]:
        raise ValueError("job GPU guard differs from protocol")
    authorization = job.get("authorization", {})
    if authorization.get("required") is not True:
        raise ValueError("explicit authorization must be required")
    if authorization.get("automatic_authorization") is not False:
        raise ValueError("automatic authorization must remain disabled")
    if authorization.get("job_sha256") != job_sha256(job):
        raise ValueError("job hash mismatch")
    return job


def load_job(experiment_root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    value = json.loads((experiment_root / "proposed_job.json").read_text(encoding="utf-8"))
    return validate_job(value, protocol)


def output_root(repo_root: Path, protocol: dict[str, Any]) -> Path:
    root = (repo_root / str(protocol["output"]["relative_root"])).resolve()
    if repo_root.resolve() not in root.parents:
        raise ValueError("canary output root must remain inside the repository data root")
    return root


def _package_root(distribution: str) -> Path | None:
    spec = util.find_spec(distribution)
    if spec is None or spec.origin is None:
        return None
    return Path(spec.origin).resolve().parent


def _nvidia_profile() -> dict[str, Any]:
    command = [
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total,compute_cap",
        "--format=csv,noheader,nounits",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if completed.returncode != 0 or len(lines) != 1:
        return {"available": False, "error": completed.stderr.strip()}
    fields = [field.strip() for field in lines[0].split(",")]
    if len(fields) != 4:
        return {"available": False, "error": "ambiguous nvidia-smi profile"}
    return {
        "available": True,
        "gpu_name": fields[0],
        "nvidia_driver": fields[1],
        "gpu_memory_total_mib": int(fields[2]),
        "gpu_compute_capability": fields[3],
    }


def verify_protocol_shape(protocol: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if protocol.get("status") != "STAGED_NOT_AUTHORIZED":
        errors.append("protocol status must remain STAGED_NOT_AUTHORIZED")
    expected_caps = {"ram_mb": 2048, "cpu_pct": 50, "io_mb_s": 50, "timeout_seconds": 600}
    if protocol.get("resources", {}).get("canary_requested_not_authorized") != expected_caps:
        errors.append("canary caps must remain 2048/50/50/600")
    expected_gpu = {
        "maximum_existing_memory_mib": 32,
        "maximum_peak_memory_mib": 1800,
        "maximum_existing_utilization_pct": 0,
        "require_no_unapproved_compute_applications": True,
        "allowed_preexisting_compute_application": {
            "maximum_count": 1,
            "executable_basename": "ChatGPT.exe",
            "required_path_suffix": "\\app\\ChatGPT.exe",
            "used_memory_may_be_unavailable": True,
        },
    }
    if protocol.get("resources", {}).get("gpu") != expected_gpu:
        errors.append("GPU guard differs from the registered 32 MiB idle host exception")
    canary = protocol.get("canary", {})
    if canary.get("seed") != 1729 or canary.get("checkpoint_every_operations") != 1:
        errors.append("seed and checkpoint cadence differ from the registered plan")
    cases = canary.get("cases", [])
    if [case.get("kind") for case in cases] != [
        "functional",
        "params4bit",
        "linear4bit_forward",
        "resident_sweep",
    ]:
        errors.append("canary cases differ from the registered diagnostic order")
    if cases:
        sweep = cases[-1]
        if sweep.get("layers") != 28 or len(sweep.get("projections", [])) != 7:
            errors.append("resident sweep must match 28 layers and seven projections")
    return errors


def protocol_lock_checks(experiment_root: Path, protocol: dict[str, Any]) -> dict[str, bool]:
    lock_path = experiment_root / "protocol.lock.json"
    if not lock_path.is_file():
        return {"protocol_lock_present": False}
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {
        "protocol_lock_present": True,
        "protocol_lock_schema": lock.get("schema") == PROTOCOL_LOCK_SCHEMA,
        "protocol_lock_protocol": lock.get("protocol_sha256") == protocol_hash(experiment_root),
    }
    for relative, expected in lock.get("files", {}).items():
        path = (experiment_root / str(relative)).resolve()
        checks[f"protocol_lock:{relative}"] = path.is_file() and sha256_file(path) == expected
    checks["protocol_lock_has_files"] = bool(lock.get("files"))
    return checks


def verify(repo_root: Path, experiment_root: Path) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    runtime = protocol["runtime"]
    shape_errors = verify_protocol_shape(protocol)
    checks: dict[str, Any] = {
        "protocol_shape": not shape_errors,
        "protocol_shape_errors": shape_errors,
        "python_version": platform.python_version() == runtime["python"],
    }
    for distribution, expected in (
        ("torch", runtime["torch_distribution"]),
        ("bitsandbytes", runtime["bitsandbytes"]),
    ):
        try:
            checks[f"software:{distribution}"] = metadata.version(distribution) == expected
        except metadata.PackageNotFoundError:
            checks[f"software:{distribution}"] = False
    torch_root = _package_root("torch")
    bnb_root = _package_root("bitsandbytes")
    c10 = None if torch_root is None else torch_root / "lib" / "c10.dll"
    bnb_cuda = None if bnb_root is None else bnb_root / "libbitsandbytes_cuda121.dll"
    checks["c10_dll"] = (
        c10 is not None and c10.is_file() and sha256_file(c10) == runtime["c10_dll_sha256"]
    )
    checks["bitsandbytes_cuda121_dll"] = (
        bnb_cuda is not None
        and bnb_cuda.is_file()
        and sha256_file(bnb_cuda) == runtime["bitsandbytes_cuda121_dll_sha256"]
    )
    launcher = protocol["bounded_launcher"]
    wrapper = (experiment_root / launcher["underlying_job_wrapper"]).resolve()
    cleanup = (experiment_root / launcher["cleanup"]).resolve()
    checks["job_wrapper"] = (
        wrapper.is_file() and sha256_file(wrapper) == launcher["underlying_job_wrapper_sha256"]
    )
    checks["cleanup_script"] = (
        cleanup.is_file() and sha256_file(cleanup) == launcher["cleanup_sha256"]
    )
    gpu = _nvidia_profile()
    checks["nvidia_profile"] = gpu.get("available") is True and all(
        gpu.get(key) == runtime[key]
        for key in (
            "gpu_name",
            "nvidia_driver",
            "gpu_memory_total_mib",
            "gpu_compute_capability",
        )
    )
    lock_checks = protocol_lock_checks(experiment_root, protocol)
    checks["implementation_lock"] = all(lock_checks.values())
    checks["implementation_lock_checks"] = lock_checks
    try:
        job = load_job(experiment_root, protocol)
        checks["job"] = True
        checks["job_sha256"] = job_sha256(job) == job["authorization"]["job_sha256"]
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as error:
        job = {}
        checks["job"] = False
        checks["job_error"] = f"{type(error).__name__}: {error}"
    boolean_checks = [value for value in checks.values() if isinstance(value, bool)]
    return {
        "schema": "pixie_bnb_quantization_canary_verification_v3",
        "ok": all(boolean_checks),
        "checks": checks,
        "job": job,
        "runtime_profile": gpu,
        "output_root": str(output_root(repo_root, protocol)),
    }
