"""Chunked context-3-only continuation bound to the verified v0.1 lineage."""

from __future__ import annotations

from datetime import datetime, timezone
import gc
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np

from .authorization import validate
from .protocol import load_protocol, load_repo_config, resolve_config_path, sha256_file
from .verify import verify


class ContinuationError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _legacy_modules(repo_root: Path):
    legacy_root = repo_root / "experiments" / "pixie_5d_holonomy_validation"
    if str(legacy_root) not in sys.path:
        sys.path.insert(0, str(legacy_root))
    from pixie_holonomy5d import capture as legacy_capture
    from pixie_holonomy5d.io import append_jsonl, atomic_json, atomic_npz

    return legacy_capture, append_jsonl, atomic_json, atomic_npz


def _artifact_key(path: Path, run_root: Path) -> str:
    return path.relative_to(run_root).as_posix()


def _chunk_paths(run_root: Path, start: int, end: int) -> tuple[list[Path], Path]:
    label = f"rows_{start:03d}_{end - 1:03d}"
    conditions = ("zero", "trained", "random_00")
    artifacts = [run_root / "chunks" / condition / f"context_03_{label}.npz" for condition in conditions]
    return artifacts, run_root / "chunks" / f"context_03_{label}.complete.json"


def _chunk_complete(marker: Path, artifacts: Sequence[Path], run_root: Path, protocol_hash: str) -> bool:
    if not marker.is_file() or any(not path.is_file() for path in artifacts):
        return False
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    actual = {_artifact_key(path, run_root): sha256_file(path) for path in artifacts}
    return (
        value.get("schema") == "pixie_5d_context3_chunk_v2"
        and value.get("protocol_sha256") == protocol_hash
        and value.get("artifacts") == actual
    )


def _final_complete(marker: Path, artifacts: Sequence[Path], run_root: Path, protocol_hash: str) -> bool:
    if not marker.is_file() or any(not path.is_file() for path in artifacts):
        return False
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    actual = {_artifact_key(path, run_root): sha256_file(path) for path in artifacts}
    return (
        value.get("schema") == "pixie_5d_context3_complete_v2"
        and value.get("protocol_sha256") == protocol_hash
        and value.get("rows") == 64
        and value.get("artifacts") == actual
    )


def _quarantine_partial(run_root: Path, artifacts: Sequence[Path], marker: Path) -> None:
    present = [path for path in [*artifacts, marker] if path.exists()]
    if not present:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = run_root / "quarantine" / stamp
    destination.mkdir(parents=True, exist_ok=False)
    for path in present:
        path.replace(destination / path.name)


def _package_versions() -> dict[str, str | None]:
    output: dict[str, str | None] = {}
    for name in ("torch", "transformers", "peft", "bitsandbytes", "numpy", "safetensors"):
        try:
            output[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            output[name] = None
    return output


def _layer_energy(receipts: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    import math
    import re

    squared: dict[str, float] = {}
    for receipt in receipts:
        match = re.search(r"(?:^|\.)layers\.(\d+)(?:\.|$)", str(receipt["module"]))
        if match is not None:
            layer = match.group(1)
            squared[layer] = squared.get(layer, 0.0) + float(receipt["target_effective_norm"]) ** 2
    return {key: math.sqrt(value) for key, value in sorted(squared.items(), key=lambda item: int(item[0]))}


def _assemble_context(
    run_root: Path,
    protocol: Mapping[str, Any],
    protocol_hash: str,
    atomic_json: Any,
    atomic_npz: Any,
) -> dict[str, str]:
    chunk_size = int(protocol["continuation"]["chunk_rows"])
    row_count = int(protocol["continuation"]["expected_rows"])
    conditions = ("zero", "trained", "random_00")
    final_paths = [run_root / condition / "context_03.npz" for condition in conditions]
    marker = run_root / "context_03.complete.json"
    if _final_complete(marker, final_paths, run_root, protocol_hash):
        return {_artifact_key(path, run_root): sha256_file(path) for path in final_paths}
    _quarantine_partial(run_root, final_paths, marker)
    for condition, final_path in zip(conditions, final_paths):
        chunks: list[dict[str, np.ndarray]] = []
        for start in range(0, row_count, chunk_size):
            end = min(row_count, start + chunk_size)
            paths, chunk_marker = _chunk_paths(run_root, start, end)
            if not _chunk_complete(chunk_marker, paths, run_root, protocol_hash):
                raise ContinuationError(f"cannot assemble incomplete chunk {start}:{end}")
            path = paths[conditions.index(condition)]
            with np.load(path, allow_pickle=False) as archive:
                chunks.append({name: archive[name].copy() for name in archive.files})
        row_fields = (
            "delta",
            "row_ids",
            "families",
            "splits",
            "token_counts",
            "supervised_token_counts",
            "base_mean_log_likelihood",
            "condition_mean_log_likelihood",
            "log_likelihood_gain",
        )
        arrays = {name: np.concatenate([chunk[name] for chunk in chunks], axis=0) for name in row_fields}
        arrays["layers"] = chunks[0]["layers"]
        arrays["context_index"] = chunks[0]["context_index"]
        if len(arrays["row_ids"]) != row_count or len(set(arrays["row_ids"].tolist())) != row_count:
            raise ContinuationError(f"assembled {condition} rows are missing or duplicated")
        atomic_npz(final_path, **arrays)
    artifacts = {_artifact_key(path, run_root): sha256_file(path) for path in final_paths}
    atomic_json(
        marker,
        {
            "schema": "pixie_5d_context3_complete_v2",
            "protocol_sha256": protocol_hash,
            "context_index": 3,
            "rows": row_count,
            "artifacts": artifacts,
            "reused_v01_artifacts": protocol["continuation"]["reused_artifacts"],
            "completed_utc": _utc_now(),
        },
    )
    return artifacts


def run_continuation(repo_root: Path, experiment_root: Path, authorization_path: Path) -> dict[str, Any]:
    protocol_path = experiment_root / "protocol.json"
    protocol = load_protocol(experiment_root)
    authorization = validate(
        authorization_path,
        protocol_path,
        protocol,
        require_active_wrapper=True,
    )
    verification = verify(repo_root, experiment_root)
    if not verification["ok"]:
        raise ContinuationError(f"frozen lineage verification failed: {verification['checks']}")
    legacy, append_jsonl, atomic_json, atomic_npz = _legacy_modules(repo_root)
    protocol_hash = sha256_file(protocol_path)
    config = load_repo_config(repo_root)
    output_root = resolve_config_path(repo_root, config, "pixie_5d_holonomy_v02_output_root")
    continuation_id = protocol["continuation"]["continuation_id"]
    run_root = output_root / "continuation" / continuation_id
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    if summary_path.is_file():
        previous = json.loads(summary_path.read_text(encoding="utf-8"))
        if previous.get("status") == "COMPLETE" and previous.get("protocol_sha256") == protocol_hash:
            return previous
        raise ContinuationError(f"non-reusable summary already exists: {summary_path}")

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["WANDB_DISABLED"] = "true"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    events_path = run_root / "events.jsonl"
    append_jsonl(
        events_path,
        {
            "event": "continuation_attempt_started",
            "attempt_id": authorization["attempt_id"],
            "protocol_sha256": protocol_hash,
            "utc": _utc_now(),
        },
    )
    started = time.monotonic()
    torch = tokenizer = model = base = None
    terminal: dict[str, Any] | None = None
    failure: BaseException | None = None
    try:
        import torch as torch_module
        from peft import PeftConfig, PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        torch = torch_module
        if not torch.cuda.is_available():
            raise ContinuationError("CUDA is unavailable inside the capped continuation")
        torch.manual_seed(int(protocol["seeds"]["root"]))
        torch.cuda.manual_seed_all(int(protocol["seeds"]["root"]))
        torch.cuda.reset_peak_memory_stats()
        model_path = Path(verification["model"])
        adapter_path = Path(verification["adapter"])
        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        base = AutoModelForCausalLM.from_pretrained(
            model_path,
            local_files_only=True,
            trust_remote_code=False,
            device_map={"": 0},
            quantization_config=quantization,
            torch_dtype=torch.float16,
            attn_implementation="sdpa",
        )
        base.config.use_cache = False
        model = PeftModel.from_pretrained(base, adapter_path, adapter_name="trained", is_trainable=False)
        model.eval()
        adapter_config = PeftConfig.from_pretrained(adapter_path)
        random_receipts = legacy.configure_norm_matched_random_adapter(
            model, adapter_config, int(protocol["seeds"]["random_adapter"])
        )
        append_jsonl(
            events_path,
            {"event": "model_loaded", "attempt_id": authorization["attempt_id"], "random_modules": len(random_receipts), "utc": _utc_now()},
        )

        train_path = repo_root / protocol["data"]["train_path"]
        eval_path = repo_root / protocol["data"]["eval_path"]
        train_rows = legacy._load_jsonl(train_path, "train")
        eval_rows = legacy._load_jsonl(eval_path, "eval")
        rows = train_rows + eval_rows
        expected_rows = int(protocol["continuation"]["expected_rows"])
        if len(rows) != expected_rows or set(row["id"] for row in train_rows) & set(row["id"] for row in eval_rows):
            raise ContinuationError("frozen row count or split disjointness failed")
        layers = [int(value) for value in protocol["layers"]]
        context_index = int(protocol["continuation"]["capture_context_index"])
        context_text = protocol["contexts"][context_index]
        chunk_size = int(protocol["continuation"]["chunk_rows"])
        conditions = ("zero", "trained", "random_00")
        chunks_complete = 0
        for start in range(0, len(rows), chunk_size):
            end = min(len(rows), start + chunk_size)
            artifact_paths, marker = _chunk_paths(run_root, start, end)
            if _chunk_complete(marker, artifact_paths, run_root, protocol_hash):
                chunks_complete += 1
                append_jsonl(events_path, {"event": "chunk_resumed", "start": start, "end": end, "utc": _utc_now()})
                continue
            _quarantine_partial(run_root, artifact_paths, marker)
            deltas: dict[str, list[np.ndarray]] = {name: [] for name in conditions}
            likelihoods: dict[str, list[float]] = {name: [] for name in conditions}
            baseline_likelihoods: list[float] = []
            token_counts: list[int] = []
            supervised_counts: list[int] = []
            for row in rows[start:end]:
                messages = legacy._render_context(row["messages"], str(context_text))
                encoded = legacy._encode_chat(tokenizer, messages, int(protocol["maximum_sequence_length"]))
                base_hidden, base_ll = legacy._forward_receipt(torch, model, encoded, layers, adapter_name=None)
                baseline_likelihoods.append(base_ll)
                token_counts.append(len(encoded["input_ids"]))
                supervised_counts.append(int(encoded["supervised_tokens"]))
                deltas["zero"].append(np.zeros_like(base_hidden, dtype=np.float32))
                likelihoods["zero"].append(base_ll)
                for condition in ("trained", "random_00"):
                    adapted_hidden, adapted_ll = legacy._forward_receipt(
                        torch, model, encoded, layers, adapter_name=condition
                    )
                    deltas[condition].append((adapted_hidden - base_hidden).astype(np.float32))
                    likelihoods[condition].append(adapted_ll)
            baseline = np.asarray(baseline_likelihoods, dtype=np.float32)
            chunk_rows = rows[start:end]
            for condition, artifact in zip(conditions, artifact_paths):
                current = np.asarray(likelihoods[condition], dtype=np.float32)
                atomic_npz(
                    artifact,
                    delta=np.stack(deltas[condition]).astype(np.float32),
                    row_ids=np.asarray([row["id"] for row in chunk_rows], dtype=np.str_),
                    families=np.asarray([row["kind"] for row in chunk_rows], dtype=np.str_),
                    splits=np.asarray([row["split"] for row in chunk_rows], dtype=np.str_),
                    layers=np.asarray(layers, dtype=np.int16),
                    context_index=np.asarray([context_index], dtype=np.int16),
                    token_counts=np.asarray(token_counts, dtype=np.int16),
                    supervised_token_counts=np.asarray(supervised_counts, dtype=np.int16),
                    base_mean_log_likelihood=baseline,
                    condition_mean_log_likelihood=current,
                    log_likelihood_gain=(current - baseline).astype(np.float32),
                )
            artifacts = {_artifact_key(path, run_root): sha256_file(path) for path in artifact_paths}
            atomic_json(
                marker,
                {
                    "schema": "pixie_5d_context3_chunk_v2",
                    "protocol_sha256": protocol_hash,
                    "start": start,
                    "end": end,
                    "row_ids": [row["id"] for row in chunk_rows],
                    "artifacts": artifacts,
                    "completed_utc": _utc_now(),
                },
            )
            chunks_complete += 1
            append_jsonl(events_path, {"event": "chunk_complete", "start": start, "end": end, "utc": _utc_now()})
            del deltas, likelihoods, baseline
            gc.collect()

        final_artifacts = _assemble_context(run_root, protocol, protocol_hash, atomic_json, atomic_npz)
        terminal = {
            "schema": "pixie_5d_context3_continuation_summary_v2",
            "status": "COMPLETE",
            "experiment_id": protocol["experiment_id"],
            "protocol_sha256": protocol_hash,
            "continuation_id": continuation_id,
            "attempt_id": authorization["attempt_id"],
            "authorization": authorization,
            "verification": verification,
            "source_protocol_sha256": protocol["continuation"]["source_protocol_sha256"],
            "reused_contexts": [0, 1, 2],
            "captured_context": 3,
            "chunks_complete": chunks_complete,
            "context3_artifacts": final_artifacts,
            "adapter_layer_effective_update_energy": _layer_energy(random_receipts),
            "random_control": {"seed": protocol["seeds"]["random_adapter"], "modules": random_receipts},
            "packages": _package_versions(),
            "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated()),
            "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved()),
            "wall_time_seconds_before_cleanup": time.monotonic() - started,
        }
    except BaseException as error:
        failure = error
    finally:
        model = tokenizer = base = None
        cleanup = legacy._cleanup(torch)

    if failure is not None:
        abort_path = run_root / "aborts" / f"abort_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
        atomic_json(
            abort_path,
            {
                "schema": "pixie_5d_context3_abort_v2",
                "status": "ABORTED",
                "attempt_id": authorization["attempt_id"],
                "protocol_sha256": protocol_hash,
                "error_type": type(failure).__name__,
                "error": str(failure),
                "cleanup": cleanup,
                "wall_time_seconds": time.monotonic() - started,
                "utc": _utc_now(),
            },
        )
        append_jsonl(events_path, {"event": "continuation_aborted", "abort": str(abort_path), "utc": _utc_now()})
        raise ContinuationError(f"continuation aborted; receipt: {abort_path}; cause: {failure}") from failure
    assert terminal is not None
    terminal["cleanup"] = cleanup
    terminal["wall_time_seconds"] = time.monotonic() - started
    if cleanup["status"] != "PASS":
        terminal["status"] = "CLEANUP_FAILED"
    atomic_json(summary_path, terminal)
    append_jsonl(events_path, {"event": "continuation_complete", "status": terminal["status"], "utc": _utc_now()})
    if terminal["status"] != "COMPLETE":
        raise ContinuationError(f"continuation completed but cleanup failed: {summary_path}")
    return terminal
