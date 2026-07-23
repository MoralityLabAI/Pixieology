"""Deterministic synthetic NF4 canary with per-operation checkpoints."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import gc
import json
import math
import os
from pathlib import Path
import time
import traceback
from typing import Any

from .authorization import validate_authorization
from .protocol import (
    job_sha256,
    load_job,
    load_protocol,
    output_root,
    protocol_hash,
    sha256_file,
    verify,
)


class CanaryV3Error(RuntimeError):
    """The diagnostic could not finish inside its registered contract."""


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        handle.write("\n")
        handle.flush()


def _read_json_receipt(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _process_private_bytes() -> int | None:
    if os.name != "nt":
        return None

    class ProcessMemoryCountersEx(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    if not ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        return None
    return int(counters.PrivateUsage)


def _runtime_receipt(torch: Any, bnb: Any) -> dict[str, Any]:
    properties = torch.cuda.get_device_properties(0)
    return {
        "python": ".".join(str(value) for value in tuple(__import__("sys").version_info[:3])),
        "torch_runtime": str(torch.__version__),
        "torch_cuda": str(torch.version.cuda),
        "bitsandbytes": str(bnb.__version__),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_device_count": int(torch.cuda.device_count()),
        "gpu_name": str(properties.name),
        "gpu_compute_capability": f"{properties.major}.{properties.minor}",
        "gpu_memory_total_mib": int(round(properties.total_memory / (1024 * 1024))),
    }


def _memory_receipt(torch: Any) -> dict[str, Any]:
    return {
        "process_private_bytes": _process_private_bytes(),
        "cuda_allocated_bytes": int(torch.cuda.memory_allocated()),
        "cuda_reserved_bytes": int(torch.cuda.memory_reserved()),
        "cuda_max_allocated_bytes": int(torch.cuda.max_memory_allocated()),
        "cuda_max_reserved_bytes": int(torch.cuda.max_memory_reserved()),
    }


def _guard_gpu(torch: Any, maximum_peak_mib: int) -> None:
    observed = max(torch.cuda.max_memory_allocated(), torch.cuda.max_memory_reserved())
    if observed > int(maximum_peak_mib) * 1024 * 1024:
        raise CanaryV3Error(
            f"observed CUDA allocator peak {observed / (1024 * 1024):.2f} MiB "
            f"exceeds {maximum_peak_mib} MiB guard"
        )


def _checksum(torch: Any, tensor: Any) -> int:
    values = tensor.detach().view(torch.uint8).flatten()[:4096]
    return int(values.to(dtype=torch.int64).sum().item())


def _synthetic_weight(torch: Any, shape: list[int], generator: Any) -> Any:
    weight = torch.empty(tuple(int(value) for value in shape), dtype=torch.float16, device="cpu")
    with torch.no_grad():
        weight.uniform_(-0.02, 0.02, generator=generator)
    return weight


def _checkpoint(
    path: Path,
    events: Path,
    torch: Any,
    *,
    run_id: str,
    attempt_id: str,
    completed_operations: int,
    operation: dict[str, Any],
    resident_parameter_count: int,
) -> dict[str, Any]:
    torch.cuda.synchronize()
    receipt = {
        "schema": "pixie_bnb_quantization_canary_checkpoint_v3",
        "run_id": run_id,
        "attempt_id": attempt_id,
        "completed_operations": completed_operations,
        "last_operation": operation,
        "resident_parameter_count": resident_parameter_count,
        "memory": _memory_receipt(torch),
        "utc": _utc_now(),
    }
    _atomic_json(path, receipt)
    _append_jsonl(events, {"event": "operation_complete", **receipt})
    return receipt


def _run_functional(
    torch: Any,
    bnb: Any,
    case: dict[str, Any],
    generator: Any,
) -> dict[str, Any]:
    weight_cpu = _synthetic_weight(torch, case["shape"], generator)
    source_bytes = int(weight_cpu.numel() * weight_cpu.element_size())
    weight_cuda = weight_cpu.to("cuda")
    del weight_cpu
    quantized, quant_state = bnb.functional.quantize_4bit(
        weight_cuda.contiguous(),
        blocksize=64,
        compress_statistics=True,
        quant_type="nf4",
        quant_storage=torch.uint8,
    )
    torch.cuda.synchronize()
    receipt = {
        "case_id": case["case_id"],
        "kind": case["kind"],
        "shape": case["shape"],
        "source_bytes": source_bytes,
        "quantized_bytes": int(quantized.numel() * quantized.element_size()),
        "checksum": _checksum(torch, quantized),
    }
    del quant_state, quantized, weight_cuda
    torch.cuda.empty_cache()
    return receipt


def _run_params4bit(
    torch: Any,
    bnb: Any,
    case: dict[str, Any],
    generator: Any,
) -> dict[str, Any]:
    weight_cpu = _synthetic_weight(torch, case["shape"], generator)
    source_bytes = int(weight_cpu.numel() * weight_cpu.element_size())
    weight_cuda = weight_cpu.to("cuda")
    del weight_cpu
    parameter = bnb.nn.Params4bit(
        weight_cuda,
        requires_grad=False,
        compress_statistics=True,
        quant_type="nf4",
        quant_storage=torch.uint8,
    ).to(weight_cuda.device)
    torch.cuda.synchronize()
    receipt = {
        "case_id": case["case_id"],
        "kind": case["kind"],
        "shape": case["shape"],
        "source_bytes": source_bytes,
        "quantized_bytes": int(parameter.data.numel() * parameter.data.element_size()),
        "checksum": _checksum(torch, parameter.data),
    }
    del parameter, weight_cuda
    torch.cuda.empty_cache()
    return receipt


def _run_linear_forward(
    torch: Any,
    bnb: Any,
    case: dict[str, Any],
    generator: Any,
) -> dict[str, Any]:
    output_features, input_features = (int(value) for value in case["shape"])
    layer = bnb.nn.Linear4bit(
        input_features,
        output_features,
        bias=False,
        compute_dtype=torch.float16,
        compress_statistics=True,
        quant_type="nf4",
        quant_storage=torch.uint8,
    )
    with torch.no_grad():
        layer.weight.data.uniform_(-0.02, 0.02, generator=generator)
    layer = layer.to("cuda").eval()
    input_cpu = torch.empty(
        (int(case["batch_tokens"]), input_features),
        dtype=torch.float16,
        device="cpu",
    )
    with torch.no_grad():
        input_cpu.uniform_(-0.1, 0.1, generator=generator)
        output = layer(input_cpu.to("cuda"))
    torch.cuda.synchronize()
    if not bool(torch.isfinite(output).all().item()):
        raise CanaryV3Error("Linear4bit forward produced non-finite output")
    receipt = {
        "case_id": case["case_id"],
        "kind": case["kind"],
        "shape": case["shape"],
        "output_shape": list(output.shape),
        "output_checksum_scaled": int(math.floor(float(output.float().sum().item()) * 1000)),
    }
    del output, input_cpu, layer
    torch.cuda.empty_cache()
    return receipt


def run_canary(
    repo_root: Path,
    experiment_root: Path,
    authorization_path: Path,
) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    job = load_job(experiment_root, protocol)
    verification = verify(repo_root, experiment_root)
    if not verification["ok"]:
        raise CanaryV3Error("pre-run verification failed")
    authorization = validate_authorization(
        authorization_path,
        experiment_root,
        protocol,
        job,
        require_active_wrapper=True,
    )
    run_root = output_root(repo_root, protocol) / "runs" / authorization.run_id
    run_root.mkdir(parents=True, exist_ok=True)
    events = run_root / "events.jsonl"
    checkpoint_path = run_root / "checkpoint.json"
    started = time.monotonic()
    _append_jsonl(
        events,
        {
            "event": "canary_started",
            "utc": _utc_now(),
            "run_id": authorization.run_id,
            "attempt_id": authorization.attempt_id,
            "job_id": job["job_id"],
            "job_sha256": job_sha256(job),
            "protocol_sha256": protocol_hash(experiment_root),
        },
    )

    import torch
    import bitsandbytes as bnb

    runtime = _runtime_receipt(torch, bnb)
    expected = protocol["runtime"]
    for key in (
        "python",
        "torch_runtime",
        "torch_cuda",
        "bitsandbytes",
        "gpu_name",
        "gpu_compute_capability",
        "gpu_memory_total_mib",
    ):
        if runtime.get(key) != expected[key]:
            raise CanaryV3Error(f"runtime {key} differs from protocol")
    if runtime["cuda_available"] is not True or runtime["cuda_device_count"] != 1:
        raise CanaryV3Error("canary requires one available CUDA device")
    _append_jsonl(events, {"event": "runtime_verified", "utc": _utc_now(), "runtime": runtime})
    torch.cuda.set_device(0)
    torch.cuda.reset_peak_memory_stats()
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(protocol["canary"]["seed"]))
    completed_operations = 0
    completed_cases: list[str] = []
    resident: list[Any] = []
    parameter: Any | None = None
    weight_cpu: Any | None = None
    weight_cuda: Any | None = None
    latest_checkpoint: dict[str, Any] | None = None
    failure: BaseException | None = None
    cleanup_receipt: dict[str, Any] = {"status": "NOT_RUN", "errors": []}
    try:
        for case in protocol["canary"]["cases"]:
            kind = case["kind"]
            if kind == "functional":
                operation = _run_functional(torch, bnb, case, generator)
                completed_operations += 1
                latest_checkpoint = _checkpoint(
                    checkpoint_path,
                    events,
                    torch,
                    run_id=authorization.run_id,
                    attempt_id=authorization.attempt_id,
                    completed_operations=completed_operations,
                    operation=operation,
                    resident_parameter_count=len(resident),
                )
            elif kind == "params4bit":
                operation = _run_params4bit(torch, bnb, case, generator)
                completed_operations += 1
                latest_checkpoint = _checkpoint(
                    checkpoint_path,
                    events,
                    torch,
                    run_id=authorization.run_id,
                    attempt_id=authorization.attempt_id,
                    completed_operations=completed_operations,
                    operation=operation,
                    resident_parameter_count=len(resident),
                )
            elif kind == "linear4bit_forward":
                operation = _run_linear_forward(torch, bnb, case, generator)
                completed_operations += 1
                latest_checkpoint = _checkpoint(
                    checkpoint_path,
                    events,
                    torch,
                    run_id=authorization.run_id,
                    attempt_id=authorization.attempt_id,
                    completed_operations=completed_operations,
                    operation=operation,
                    resident_parameter_count=len(resident),
                )
            elif kind == "resident_sweep":
                for layer_index in range(int(case["layers"])):
                    for projection in case["projections"]:
                        weight_cpu = _synthetic_weight(torch, projection["shape"], generator)
                        source_bytes = int(weight_cpu.numel() * weight_cpu.element_size())
                        weight_cuda = weight_cpu.to("cuda")
                        del weight_cpu
                        parameter = bnb.nn.Params4bit(
                            weight_cuda,
                            requires_grad=False,
                            compress_statistics=True,
                            quant_type="nf4",
                            quant_storage=torch.uint8,
                        ).to(weight_cuda.device)
                        del weight_cuda
                        resident.append(parameter)
                        completed_operations += 1
                        operation = {
                            "case_id": case["case_id"],
                            "kind": case["kind"],
                            "layer_index": layer_index,
                            "projection": projection["name"],
                            "shape": projection["shape"],
                            "source_bytes": source_bytes,
                            "quantized_bytes": int(
                                parameter.data.numel() * parameter.data.element_size()
                            ),
                            "checksum": _checksum(torch, parameter.data),
                        }
                        latest_checkpoint = _checkpoint(
                            checkpoint_path,
                            events,
                            torch,
                            run_id=authorization.run_id,
                            attempt_id=authorization.attempt_id,
                            completed_operations=completed_operations,
                            operation=operation,
                            resident_parameter_count=len(resident),
                        )
                        _guard_gpu(
                            torch,
                            int(protocol["resources"]["gpu"]["maximum_peak_memory_mib"]),
                        )
            else:
                raise CanaryV3Error(f"unsupported canary case {kind}")
            completed_cases.append(case["case_id"])
            _guard_gpu(torch, int(protocol["resources"]["gpu"]["maximum_peak_memory_mib"]))
        expected_operations = 3 + 28 * 7
        if completed_operations != expected_operations:
            raise CanaryV3Error(
                f"completed {completed_operations} operations; expected {expected_operations}"
            )
    except BaseException as error:
        failure = error
    finally:
        cleanup_receipt = {"status": "PASS", "errors": [], "started_utc": _utc_now()}
        resident.clear()
        parameter = None
        weight_cpu = None
        weight_cuda = None
        try:
            gc.collect()
        except BaseException as error:
            cleanup_receipt["errors"].append(f"gc:{type(error).__name__}:{error}")
        try:
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            if hasattr(torch.cuda, "ipc_collect"):
                torch.cuda.ipc_collect()
        except BaseException as error:
            cleanup_receipt["errors"].append(f"cuda:{type(error).__name__}:{error}")
        cleanup_receipt["ended_utc"] = _utc_now()
        cleanup_receipt["memory"] = _memory_receipt(torch)
        if cleanup_receipt["errors"]:
            cleanup_receipt["status"] = "FAIL"

    if failure is not None:
        abort = {
            "schema": "pixie_bnb_quantization_canary_abort_v3",
            "status": "ABORTED",
            "run_id": authorization.run_id,
            "attempt_id": authorization.attempt_id,
            "job_id": job["job_id"],
            "job_sha256": job_sha256(job),
            "error_type": type(failure).__name__,
            "error": str(failure),
            "traceback": "".join(traceback.format_exception(failure)),
            "completed_operations": completed_operations,
            "completed_cases": completed_cases,
            "latest_checkpoint": latest_checkpoint,
            "cleanup": cleanup_receipt,
            "wall_time_seconds": time.monotonic() - started,
            "utc": _utc_now(),
        }
        _atomic_json(run_root / "abort.json", abort)
        _append_jsonl(
            events,
            {
                "event": "canary_aborted",
                "utc": _utc_now(),
                "error_type": type(failure).__name__,
                "completed_operations": completed_operations,
            },
        )
        raise CanaryV3Error(f"canary aborted with receipt {run_root / 'abort.json'}") from failure

    status = "COMPLETE" if cleanup_receipt["status"] == "PASS" else "CLEANUP_FAILED"
    summary = {
        "schema": "pixie_bnb_quantization_canary_summary_v3",
        "status": status,
        "run_id": authorization.run_id,
        "attempt_id": authorization.attempt_id,
        "job_id": job["job_id"],
        "job_sha256": job_sha256(job),
        "runtime": runtime,
        "completed_operations": completed_operations,
        "completed_cases": completed_cases,
        "latest_checkpoint": latest_checkpoint,
        "cleanup": cleanup_receipt,
        "wall_time_seconds": time.monotonic() - started,
        "claim_boundary": protocol["claim_boundary"],
        "utc": _utc_now(),
    }
    _atomic_json(run_root / "summary.json", summary)
    _append_jsonl(events, {"event": "canary_complete", "utc": _utc_now(), "status": status})
    if status != "COMPLETE":
        raise CanaryV3Error("canary operations completed but Python cleanup failed")
    return summary


def finalize_execution(
    repo_root: Path,
    experiment_root: Path,
    resource_summary_path: Path,
    cleanup_summary_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    job = load_job(experiment_root, protocol)
    resource = _read_json_receipt(resource_summary_path)
    cleanup = _read_json_receipt(cleanup_summary_path)
    samples = list(resource.get("samples", []))
    ram_values = [
        float(sample.get("tree_private_bytes", 0)) / (1024 * 1024)
        for sample in samples
    ]
    run_id = str(resource.get("run_id", ""))
    attempt_id = str(resource.get("attempt_id", ""))
    run_root = output_root(repo_root, protocol) / "runs" / run_id
    python_artifact: Path | None = None
    python_value: dict[str, Any] | None = None
    for name in ("summary.json", "abort.json"):
        candidate = run_root / name
        if candidate.is_file():
            python_artifact = candidate
            python_value = _read_json_receipt(candidate)
            break
    checkpoint = run_root / "checkpoint.json"
    checkpoint_value = _read_json_receipt(checkpoint) if checkpoint.is_file() else {}
    peak_gpu_memory_mib = int(resource.get("peak_gpu_memory_mib") or 0)
    gpu_guard_pass = (
        peak_gpu_memory_mib
        <= int(protocol["resources"]["gpu"]["maximum_peak_memory_mib"])
    )
    status = (
        "COMPLETE"
        if resource.get("status") == "complete"
        and cleanup.get("status") == "PASS"
        and gpu_guard_pass
        and python_value is not None
        and python_value.get("status") == "COMPLETE"
        else "ABORTED"
    )
    receipt = {
        "schema": "pixie_bnb_quantization_canary_execution_summary_v3",
        "status": status,
        "job_id": job["job_id"],
        "job_sha256": job["authorization"]["job_sha256"],
        "run_id": run_id,
        "attempt_id": attempt_id,
        "abort_reason": (
            resource.get("abort_reason")
            if gpu_guard_pass
            else "peak_gpu_memory_guard_exceeded"
        ),
        "resource_status": resource.get("status"),
        "resource_exit_code": resource.get("exit_code"),
        "caps": resource.get("caps"),
        "peak_ram_mb": max(ram_values, default=0.0),
        "avg_ram_mb": sum(ram_values) / len(ram_values) if ram_values else 0.0,
        "peak_io_mb_s": resource.get("peak_io_mb_s"),
        "cpu_pct": resource.get("cpu_pct"),
        "peak_gpu_memory_mib_global": peak_gpu_memory_mib,
        "gpu_guard_pass": gpu_guard_pass,
        "cleanup_status": cleanup.get("status"),
        "lingering_owned_count": cleanup.get("lingering_owned_count"),
        "owned_gpu_processes": cleanup.get("owned_gpu_processes"),
        "steps_completed": checkpoint_value.get("completed_operations", 0),
        "last_operation": checkpoint_value.get("last_operation"),
        "python_artifact": None if python_artifact is None else str(python_artifact),
        "python_artifact_sha256": (
            None if python_artifact is None else sha256_file(python_artifact)
        ),
        "resource_summary": str(resource_summary_path),
        "resource_summary_sha256": sha256_file(resource_summary_path),
        "cleanup_summary": str(cleanup_summary_path),
        "cleanup_summary_sha256": sha256_file(cleanup_summary_path),
        "claim_boundary": protocol["claim_boundary"],
    }
    _atomic_json(output_path, receipt)
    return receipt
