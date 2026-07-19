"""Read-only hardware and prerequisite inspection."""

from __future__ import annotations

import ctypes
import importlib.metadata
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from .config import ExperimentConfig, choose_profile
from .reporting import command_result, layout, utc_now, write_json


PACKAGES = ("torch", "transformers", "peft", "bitsandbytes", "accelerate", "safetensors", "PyYAML")


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _memory() -> dict[str, Any]:
    if os.name == "nt":
        value = MEMORYSTATUSEX()
        value.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
            return {
                "total_bytes": value.ullTotalPhys,
                "available_bytes": value.ullAvailPhys,
                "load_percent": value.dwMemoryLoad,
            }
    return {"total_bytes": None, "available_bytes": None, "load_percent": None}


def _gpu() -> dict[str, Any]:
    query = command_result([
        "nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version,compute_cap,temperature.gpu",
        "--format=csv,noheader,nounits",
    ])
    result: dict[str, Any] = {"nvidia_smi": query}
    if query["returncode"] == 0 and query["stdout"].strip():
        fields = [item.strip() for item in query["stdout"].splitlines()[0].split(",")]
        if len(fields) >= 6:
            result.update({
                "name": fields[0], "total_vram_mib": int(fields[1]),
                "free_vram_mib": int(fields[2]), "driver": fields[3],
                "compute_capability_reported": fields[4], "temperature_c": fields[5],
            })
    try:
        import torch
        result["torch"] = {
            "version": torch.__version__, "cuda_available": torch.cuda.is_available(),
            "cuda_runtime": torch.version.cuda,
            "device_count": torch.cuda.device_count(),
            "bf16_supported": bool(torch.cuda.is_available() and torch.cuda.is_bf16_supported()),
            "compute_capability": list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else None,
        }
    except Exception as exc:  # diagnostic must survive import failures
        result["torch"] = {"import_error": repr(exc), "cuda_available": False}
    return result


def inspect(config: ExperimentConfig) -> dict[str, Any]:
    paths = layout(config)
    disks: dict[str, Any] = {}
    for name, target in {
        "output_root": paths.root, "hf_home": paths.hf_home,
        "model_cache": paths.model_cache, "llama_cpp_root": paths.llama_cpp,
    }.items():
        target.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(target)
        disks[name] = {"path": str(target), "total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free}
    gpu = _gpu()
    total_vram = int(gpu.get("total_vram_mib", 0))
    packages = {}
    for name in PACKAGES:
        try:
            packages[name] = {"distribution_version": importlib.metadata.version(name)}
        except importlib.metadata.PackageNotFoundError:
            packages[name] = {"distribution_version": None}
    for distribution, module in (
        ("torch", "torch"), ("transformers", "transformers"), ("peft", "peft"),
        ("bitsandbytes", "bitsandbytes"), ("accelerate", "accelerate"),
        ("safetensors", "safetensors"), ("PyYAML", "yaml"),
    ):
        try:
            imported = __import__(module)
            packages[distribution]["module_version"] = getattr(imported, "__version__", None)
        except Exception as exc:
            packages[distribution]["import_error"] = repr(exc)
    report = {
        "schema_version": 1,
        "created_utc": utc_now(),
        "os": {"platform": platform.platform(), "release": platform.release(), "version": platform.version()},
        "python": {"version": sys.version, "executable": sys.executable},
        "cpu": {"logical_count": os.cpu_count(), "processor": platform.processor()},
        "memory": _memory(),
        "gpu": gpu,
        "cuda_toolkit": command_result(["nvcc", "--version"]),
        "build_tools": {
            "cmake": command_result(["cmake", "--version"]),
            "ninja": command_result(["ninja", "--version"]),
            "git": command_result(["git", "--version"]),
        },
        "packages": packages,
        "disks": disks,
        "selected_profile": {
            "sequence_length": choose_profile(total_vram)[0],
            "rank": choose_profile(total_vram)[1],
            "gradient_accumulation_steps": choose_profile(total_vram)[2],
        },
    }
    report["checks"] = {
        "rtx_3050_detected": "RTX 3050" in str(gpu.get("name", "")),
        "cuda_available": bool(gpu.get("torch", {}).get("cuda_available")),
        "disk_free_at_least_12gb": min(row["free_bytes"] for row in disks.values()) >= 12 * 1024**3,
        "python_311": sys.version_info[:2] == (3, 11),
    }
    write_json(paths.artifacts / "hardware.json", report)
    lines = [
        f"Created: {report['created_utc']}",
        f"OS: {report['os']['platform']}",
        f"Python: {sys.version.split()[0]} ({sys.executable})",
        f"GPU: {gpu.get('name', 'not detected')}",
        f"VRAM: {gpu.get('total_vram_mib', 'unknown')} MiB total / {gpu.get('free_vram_mib', 'unknown')} MiB free",
        f"Driver: {gpu.get('driver', 'unknown')}",
        f"Torch CUDA: {gpu.get('torch', {}).get('cuda_available', False)}",
        f"RAM: {report['memory'].get('total_bytes')}",
        f"Selected profile: {report['selected_profile']}",
        f"Checks: {report['checks']}",
    ]
    (paths.artifacts / "doctor.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
