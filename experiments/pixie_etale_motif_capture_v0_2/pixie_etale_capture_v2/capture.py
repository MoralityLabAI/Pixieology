"""Memory-optimized, resumable capture for the frozen canary chunk."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import gc
import json
import math
import os
from pathlib import Path
import time
from typing import Any

from .authorization import validate_authorization
from .protocol import (
    activate_source_imports,
    load_job,
    load_protocol,
    protocol_hash,
    sha256_file,
    source_root,
    verify,
)


class CaptureV2Error(RuntimeError):
    """The v0.2 capture cannot proceed without violating its contract."""


def _read_json_receipt(path: Path) -> dict[str, Any]:
    """Read Python- or Windows PowerShell-authored JSON receipts."""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _process_private_bytes() -> int | None:
    """Return current-process private commit without importing psutil."""
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
    if not ctypes.windll.psapi.GetProcessMemoryInfo(
        handle,
        ctypes.byref(counters),
        counters.cb,
    ):
        return None
    return int(counters.PrivateUsage)


def _loader_event(append_jsonl: Any, events: Path, phase: str, torch: Any | None = None) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "event": "loader_phase",
        "phase": phase,
        "utc": _utc_now(),
        "process_private_bytes": _process_private_bytes(),
        "hf_deactivate_async_load": os.environ.get("HF_DEACTIVATE_ASYNC_LOAD"),
    }
    if torch is not None and torch.cuda.is_available():
        receipt["cuda_allocated_bytes"] = int(torch.cuda.memory_allocated())
        receipt["cuda_reserved_bytes"] = int(torch.cuda.memory_reserved())
    append_jsonl(events, receipt)
    return receipt


def _model_load_kwargs(torch: Any, quantization: Any) -> dict[str, Any]:
    return {
        "local_files_only": True,
        "trust_remote_code": False,
        "device_map": {"": 0},
        "quantization_config": quantization,
        "dtype": torch.float16,
        "attn_implementation": "sdpa",
        "use_safetensors": True,
    }


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _cleanup(torch: Any | None) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "status": "PASS",
        "errors": [],
        "started_utc": _utc_now(),
    }
    gc.collect()
    if torch is not None and torch.cuda.is_available():
        for operation in (torch.cuda.synchronize, torch.cuda.empty_cache, torch.cuda.ipc_collect):
            try:
                operation()
            except Exception as error:
                receipt["errors"].append(f"{operation.__name__}: {type(error).__name__}: {error}")
        try:
            receipt["cuda_allocated_bytes"] = int(torch.cuda.memory_allocated())
            receipt["cuda_reserved_bytes"] = int(torch.cuda.memory_reserved())
        except Exception as error:
            receipt["errors"].append(f"memory_receipt: {type(error).__name__}: {error}")
    if receipt["errors"]:
        receipt["status"] = "CLEANUP_FAILED"
    receipt["ended_utc"] = _utc_now()
    return receipt


def _require_gpu_guard(torch: Any, maximum_mib: int) -> None:
    peak = int(torch.cuda.max_memory_reserved() // (1024 * 1024))
    if peak > maximum_mib:
        raise CaptureV2Error(f"peak reserved VRAM {peak} MiB exceeds frozen {maximum_mib} MiB guard")


def capture_canary_chunk(
    repo_root: Path,
    experiment_root: Path,
    authorization_path: Path,
) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    job = load_job(experiment_root, protocol)
    authorization = validate_authorization(
        authorization_path,
        experiment_root,
        protocol,
        job,
        require_active_wrapper=True,
    )
    frozen = verify(repo_root, experiment_root, rehash_shards=True)
    if not frozen["ok"]:
        raise CaptureV2Error(f"frozen v0.2 inputs failed: {frozen['checks']}")

    activate_source_imports(experiment_root, protocol)
    from pixie_etale_motifs.protocol import (
        build_corpus_from_protocol,
        load_protocol as load_source_protocol,
        load_repo_config,
        resolve_config_path,
    )
    from pixie_etale_motifs.io import append_jsonl, atomic_json, atomic_npz

    source_protocol = load_source_protocol(source_root(experiment_root, protocol))
    config = load_repo_config(repo_root)
    output_root = resolve_config_path(repo_root, config, "pixie_etale_motif_output_root")
    sharded_root = Path(frozen["sharded_root"])
    chunk_index = int(job["chunk_index"])
    chunk_rows = int(job["row_count"])
    start = chunk_index * chunk_rows
    rows = build_corpus_from_protocol(source_protocol)
    selected = rows[start : start + chunk_rows]
    if len(selected) != chunk_rows:
        raise CaptureV2Error("frozen canary chunk is incomplete")
    if any(row["family"] != job["family"] for row in selected):
        raise CaptureV2Error("frozen canary chunk contains another family")

    run_root = output_root / "capture_v0_2" / authorization.run_id / f"chunk_{chunk_index:02d}"
    run_root.mkdir(parents=True, exist_ok=True)
    events = run_root / "events.jsonl"
    append_jsonl(
        events,
        {
            "event": "capture_started",
            "utc": _utc_now(),
            "chunk_index": chunk_index,
            "job_id": job["job_id"],
            "job_sha256": job["authorization"]["job_sha256"],
            "capture_protocol_sha256": protocol_hash(experiment_root),
            "source_protocol_sha256": protocol["source_experiment"]["protocol_sha256"],
        },
    )
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "WANDB_DISABLED": "true",
            "TOKENIZERS_PARALLELISM": "false",
            "HF_DEACTIVATE_ASYNC_LOAD": "1",
        }
    )
    started = time.monotonic()
    torch = tokenizer = base = model = None
    np = None
    hooks: list[Any] = []
    active: dict[str, Any] = {}
    updates: dict[Any, Any] = {}
    modules: dict[Any, Any] = {}
    input_buffers = norm_buffers = raw_coordinates = None
    input_ids = attention_mask = labels = base_output = trained_output = None
    loader_receipts: list[dict[str, Any]] = []
    failure: BaseException | None = None
    summary: dict[str, Any] | None = None
    cleanup: dict[str, Any]
    try:
        import torch as torch_module
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        torch = torch_module
        if not torch.cuda.is_available():
            raise CaptureV2Error("CUDA is unavailable inside capped capture v0.2")
        torch.manual_seed(int(source_protocol["seeds"]["capture"]))
        torch.cuda.manual_seed_all(int(source_protocol["seeds"]["capture"]))
        torch.cuda.reset_peak_memory_stats()

        loader_receipts.append(_loader_event(append_jsonl, events, "imports_ready", torch))
        tokenizer = AutoTokenizer.from_pretrained(
            sharded_root,
            local_files_only=True,
            trust_remote_code=False,
        )
        loader_receipts.append(_loader_event(append_jsonl, events, "tokenizer_loaded", torch))
        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        base = AutoModelForCausalLM.from_pretrained(
            sharded_root,
            **_model_load_kwargs(torch, quantization),
        )
        base.config.use_cache = False
        gc.collect()
        loader_receipts.append(_loader_event(append_jsonl, events, "base_loaded", torch))
        _require_gpu_guard(torch, int(job["gpu_guard"]["maximum_peak_memory_mib"]))

        # PEFT is deliberately absent from the process until the quantized base is resident.
        from peft import PeftModel

        base_adapter = Path(frozen["source"]["adapter"])
        model = PeftModel.from_pretrained(
            base,
            base_adapter,
            adapter_name="trained",
            is_trainable=False,
        )
        model.eval()
        gc.collect()
        loader_receipts.append(_loader_event(append_jsonl, events, "adapter_attached", torch))
        _require_gpu_guard(torch, int(job["gpu_guard"]["maximum_peak_memory_mib"]))

        import numpy as numpy_module
        from pixie_etale_motifs.capture import (
            _encode_row,
            _mean_log_likelihood,
            _trained_updates,
        )
        from pixie_etale_motifs.geometry import response_coordinates

        np = numpy_module
        module_ids = list(source_protocol["module_ids"])
        updates, modules = _trained_updates(model, module_ids)
        append_jsonl(
            events,
            {
                "event": "model_ready",
                "utc": _utc_now(),
                "module_count": len(modules),
                "process_private_bytes": _process_private_bytes(),
            },
        )

        active = {"enabled": False, "prompt_index": -1, "inputs": {}, "base_norms": {}}
        for key, module in modules.items():
            def receive(
                _module: Any,
                arguments: tuple[Any, ...],
                output: Any,
                *,
                module_key: tuple[int, str] = key,
            ) -> None:
                if not active["enabled"]:
                    return
                prompt_index = int(active["prompt_index"])
                x = arguments[0][0, prompt_index, :].detach().float().cpu().numpy()
                y = output[0, prompt_index, :].detach().float().cpu().numpy()
                active["inputs"][module_key] = x
                active["base_norms"][module_key] = float(np.linalg.norm(y))

            hooks.append(module.register_forward_hook(receive))

        checkpoint_rows = int(job["checkpoint_rows"])
        completed_groups = 0
        for local_start in range(0, len(selected), checkpoint_rows):
            group = selected[local_start : local_start + checkpoint_rows]
            group_path = run_root / f"rows_{start + local_start:03d}_{start + local_start + len(group) - 1:03d}.npz"
            marker_path = group_path.with_suffix(".complete.json")
            if marker_path.is_file() and group_path.is_file():
                marker = json.loads(marker_path.read_text(encoding="utf-8"))
                if marker.get("artifact_sha256") == sha256_file(group_path):
                    completed_groups += 1
                    append_jsonl(
                        events,
                        {"event": "checkpoint_resumed", "utc": _utc_now(), "path": str(group_path)},
                    )
                    continue
            input_buffers = {key: [] for key in modules}
            norm_buffers = {key: [] for key in modules}
            raw_coordinates = []
            base_ll: list[float] = []
            trained_ll: list[float] = []
            token_counts: list[int] = []
            for row in group:
                encoded = _encode_row(
                    tokenizer,
                    row,
                    int(source_protocol["capture"]["maximum_sequence_length"]),
                )
                input_ids = torch.tensor([encoded["input_ids"]], dtype=torch.long, device="cuda:0")
                attention_mask = torch.ones_like(input_ids)
                labels = (
                    None
                    if encoded["labels"] is None
                    else torch.tensor([encoded["labels"]], dtype=torch.long, device="cuda:0")
                )
                active.update(
                    {
                        "enabled": True,
                        "prompt_index": encoded["prompt_index"],
                        "inputs": {},
                        "base_norms": {},
                    }
                )
                with model.disable_adapter(), torch.inference_mode():
                    base_output = model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        use_cache=False,
                        return_dict=True,
                    )
                active["enabled"] = False
                if set(active["inputs"]) != set(modules):
                    raise CaptureV2Error(f"module hooks were incomplete for {row['id']}")
                row_coordinates = np.zeros((28, len(module_ids), 3), dtype=np.float32)
                for layer in range(28):
                    for module_index, module_id in enumerate(module_ids):
                        key = (layer, module_id)
                        x = active["inputs"][key]
                        base_norm = active["base_norms"][key]
                        row_coordinates[layer, module_index] = response_coordinates(
                            x,
                            base_norm,
                            updates[key],
                        )
                        input_buffers[key].append(x.astype(np.float16))
                        norm_buffers[key].append(base_norm)
                model.set_adapter("trained")
                with torch.inference_mode():
                    trained_output = model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        use_cache=False,
                        return_dict=True,
                    )
                base_ll.append(_mean_log_likelihood(torch, base_output.logits, labels))
                trained_ll.append(_mean_log_likelihood(torch, trained_output.logits, labels))
                raw_coordinates.append(row_coordinates)
                token_counts.append(len(encoded["input_ids"]))
                del input_ids, attention_mask, labels, base_output, trained_output
                input_ids = attention_mask = labels = base_output = trained_output = None
                _require_gpu_guard(torch, int(job["gpu_guard"]["maximum_peak_memory_mib"]))
            arrays: dict[str, Any] = {
                "row_ids": np.asarray([row["id"] for row in group], dtype=np.str_),
                "semantic_group_ids": np.asarray(
                    [row["semantic_group_id"] for row in group],
                    dtype=np.str_,
                ),
                "families": np.asarray([row["family"] for row in group], dtype=np.str_),
                "variants": np.asarray([row["variant"] for row in group], dtype=np.str_),
                "splits": np.asarray([row["split"] for row in group], dtype=np.str_),
                "outcome_eligible": np.asarray(
                    [row["outcome_eligible"] for row in group],
                    dtype=np.bool_,
                ),
                "raw_coordinates": np.stack(raw_coordinates),
                "base_mean_log_likelihood": np.asarray(base_ll, dtype=np.float32),
                "trained_mean_log_likelihood": np.asarray(trained_ll, dtype=np.float32),
                "token_counts": np.asarray(token_counts, dtype=np.int16),
            }
            for key in sorted(modules):
                layer, module_id = key
                arrays[f"input__{layer:02d}__{module_id}"] = np.stack(input_buffers[key])
                arrays[f"base_norm__{layer:02d}__{module_id}"] = np.asarray(
                    norm_buffers[key],
                    dtype=np.float32,
                )
            atomic_npz(group_path, **arrays)
            marker = {
                "schema": "pixieology_etale_capture_checkpoint_v2",
                # Preserve downstream v0.1 geometry compatibility while adding loader provenance.
                "protocol_sha256": protocol["source_experiment"]["protocol_sha256"],
                "capture_protocol_sha256": protocol_hash(experiment_root),
                "job_sha256": job["authorization"]["job_sha256"],
                "chunk_index": chunk_index,
                "row_ids": [row["id"] for row in group],
                "artifact": str(group_path),
                "artifact_sha256": sha256_file(group_path),
                "completed_utc": _utc_now(),
            }
            atomic_json(marker_path, marker)
            completed_groups += 1
            append_jsonl(
                events,
                {
                    "event": "checkpoint_complete",
                    "utc": _utc_now(),
                    "rows": len(group),
                    "path": str(group_path),
                },
            )
        summary = {
            "schema": "pixieology_etale_capture_chunk_summary_v2",
            "status": "COMPLETE",
            "capture_protocol_sha256": protocol_hash(experiment_root),
            "source_protocol_sha256": protocol["source_experiment"]["protocol_sha256"],
            "job_id": job["job_id"],
            "job_sha256": job["authorization"]["job_sha256"],
            "run_id": authorization.run_id,
            "attempt_id": authorization.attempt_id,
            "chunk_index": chunk_index,
            "family": job["family"],
            "row_start": start,
            "row_count": len(selected),
            "checkpoint_count": completed_groups,
            "condition": source_protocol["controls"]["primary_geometry"],
            "live_trained_geometry": source_protocol["controls"]["live_trained_geometry"],
            "loader_strategy": protocol["loader"]["strategy"],
            "loader_receipts": loader_receipts,
            "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated()),
            "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved()),
            "wall_time_seconds_before_cleanup": time.monotonic() - started,
        }
    except BaseException as error:
        failure = error
    finally:
        for hook in hooks:
            try:
                hook.remove()
            except Exception:
                pass
        updates = modules = active = {}
        hooks = []
        input_buffers = norm_buffers = raw_coordinates = None
        input_ids = attention_mask = labels = base_output = trained_output = None
        model = tokenizer = base = np = None
        cleanup = _cleanup(torch)
    if failure is not None:
        abort = {
            "schema": "pixieology_etale_capture_abort_v2",
            "status": "ABORTED",
            "capture_protocol_sha256": protocol_hash(experiment_root),
            "source_protocol_sha256": protocol["source_experiment"]["protocol_sha256"],
            "job_id": job["job_id"],
            "job_sha256": job["authorization"]["job_sha256"],
            "run_id": authorization.run_id,
            "attempt_id": authorization.attempt_id,
            "chunk_index": chunk_index,
            "error_type": type(failure).__name__,
            "error": str(failure),
            "loader_receipts": loader_receipts,
            "cleanup": cleanup,
            "wall_time_seconds": time.monotonic() - started,
            "utc": _utc_now(),
        }
        atomic_json(run_root / "abort.json", abort)
        append_jsonl(
            events,
            {
                "event": "capture_aborted",
                "utc": _utc_now(),
                "error_type": type(failure).__name__,
            },
        )
        raise CaptureV2Error(f"capture v0.2 aborted with receipt {run_root / 'abort.json'}") from failure
    assert summary is not None
    summary["cleanup"] = cleanup
    summary["wall_time_seconds"] = time.monotonic() - started
    if cleanup["status"] != "PASS":
        summary["status"] = "CLEANUP_FAILED"
    atomic_json(run_root / "summary.json", summary)
    append_jsonl(
        events,
        {"event": "capture_complete", "utc": _utc_now(), "status": summary["status"]},
    )
    if summary["status"] != "COMPLETE":
        raise CaptureV2Error("capture v0.2 completed but cleanup failed")
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

    activate_source_imports(experiment_root, protocol)
    from pixie_etale_motifs.io import atomic_json
    from pixie_etale_motifs.protocol import load_repo_config, resolve_config_path

    output_root = resolve_config_path(repo_root, load_repo_config(repo_root), "pixie_etale_motif_output_root")
    capture_root = output_root / "capture_v0_2" / run_id / f"chunk_{int(job['chunk_index']):02d}"
    capture_summary = capture_root / "summary.json"
    capture_abort = capture_root / "abort.json"
    capture_value = None
    capture_artifact = None
    if capture_summary.is_file():
        capture_artifact = capture_summary
        capture_value = json.loads(capture_summary.read_text(encoding="utf-8"))
    elif capture_abort.is_file():
        capture_artifact = capture_abort
        capture_value = json.loads(capture_abort.read_text(encoding="utf-8"))
    status = (
        "COMPLETE"
        if resource.get("status") == "complete"
        and cleanup.get("status") == "PASS"
        and capture_value is not None
        and capture_value.get("status") == "COMPLETE"
        else "ABORTED"
    )
    receipt = {
        "schema": "pixie_etale_capture_execution_summary_v2",
        "status": status,
        "job_id": job["job_id"],
        "job_sha256": job["authorization"]["job_sha256"],
        "run_id": run_id,
        "attempt_id": attempt_id,
        "abort_reason": resource.get("abort_reason"),
        "resource_status": resource.get("status"),
        "resource_exit_code": resource.get("exit_code"),
        "caps": resource.get("caps"),
        "peak_ram_mb": max(ram_values, default=0.0),
        "avg_ram_mb": sum(ram_values) / len(ram_values) if ram_values else 0.0,
        "peak_gpu_memory_mib_global": resource.get("peak_gpu_memory_mib"),
        "cleanup_status": cleanup.get("status"),
        "lingering_owned_count": cleanup.get("lingering_owned_count"),
        "owned_gpu_processes": cleanup.get("owned_gpu_processes"),
        "capture_artifact": None if capture_artifact is None else str(capture_artifact),
        "capture_artifact_sha256": (
            None if capture_artifact is None else sha256_file(capture_artifact)
        ),
        "checkpoint_count": (
            None if capture_value is None else capture_value.get("checkpoint_count", 0)
        ),
        "resource_summary": str(resource_summary_path),
        "resource_summary_sha256": sha256_file(resource_summary_path),
        "cleanup_summary": str(cleanup_summary_path),
        "cleanup_summary_sha256": sha256_file(cleanup_summary_path),
        "claim_boundary": (
            "COMPLETE means bounded capture checkpoints exist; it is not a confirmed motif. "
            "ABORTED is valid operational evidence and makes no activation claim."
        ),
    }
    atomic_json(output_path, receipt)
    return receipt
