"""Sharded-loader context-3 continuation under the corrected v0.2 Job Object."""

from __future__ import annotations

from datetime import datetime, timezone
import gc
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np

from .authorization import validate
from .protocol import load_protocol, load_repo_config, resolve_config_path, sha256_file
from .sharding import prepare_sharded_snapshot, verify_sharded_snapshot
from .verify import verify


class ContinuationError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _v02_helpers(repo_root: Path):
    root = repo_root / "experiments" / "pixie_5d_holonomy_validation_v0_2"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from pixie_holonomy5d_v02.continuation import (
        _artifact_key,
        _assemble_context,
        _chunk_complete,
        _chunk_paths,
        _layer_energy,
        _legacy_modules,
        _package_versions,
        _quarantine_partial,
    )

    return {
        "artifact_key": _artifact_key,
        "assemble_context": _assemble_context,
        "chunk_complete": _chunk_complete,
        "chunk_paths": _chunk_paths,
        "layer_energy": _layer_energy,
        "legacy_modules": _legacy_modules,
        "package_versions": _package_versions,
        "quarantine_partial": _quarantine_partial,
    }


def run_continuation(repo_root: Path, experiment_root: Path, authorization_path: Path) -> dict[str, Any]:
    protocol_path = experiment_root / "protocol.json"
    protocol = load_protocol(experiment_root)
    authorization = validate(authorization_path, protocol_path, protocol, require_active_wrapper=True)
    verification = verify(repo_root, experiment_root)
    if not verification["ok"]:
        raise ContinuationError(f"frozen v0.3 verification failed: {verification['checks']}")
    helpers = _v02_helpers(repo_root)
    legacy, append_jsonl, atomic_json, atomic_npz = helpers["legacy_modules"](repo_root)
    protocol_hash = sha256_file(protocol_path)
    config = load_repo_config(repo_root)
    output_root = resolve_config_path(repo_root, config, "pixie_5d_holonomy_v03_output_root")
    sharded_root = resolve_config_path(repo_root, config, protocol["sharding"]["output_config_key"])
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
            "event": "v03_attempt_started",
            "attempt_id": authorization["attempt_id"],
            "protocol_sha256": protocol_hash,
            "utc": _utc_now(),
        },
    )
    started = time.monotonic()
    torch = tokenizer = model = base = None
    terminal: dict[str, Any] | None = None
    failure: BaseException | None = None
    sharding_manifest: dict[str, Any] | None = None
    try:
        import torch as torch_module

        torch = torch_module
        if not torch.cuda.is_available():
            raise ContinuationError("CUDA is unavailable inside the capped v0.3 continuation")
        source_model = Path(verification["model"])
        sharding_manifest = prepare_sharded_snapshot(
            source_model,
            sharded_root,
            protocol,
            protocol_hash,
            event_callback=lambda event: append_jsonl(events_path, event),
        )
        append_jsonl(
            events_path,
            {
                "event": "sharded_snapshot_verified",
                "shards": sharding_manifest["shard_count"],
                "tensors": sharding_manifest["tensor_count"],
                "manifest_sha256": sha256_file(sharded_root / "sharding_manifest.json"),
                "utc": _utc_now(),
            },
        )
        gc.collect()
        torch.manual_seed(int(protocol["seeds"]["root"]))
        torch.cuda.manual_seed_all(int(protocol["seeds"]["root"]))
        torch.cuda.reset_peak_memory_stats()
        from peft import PeftConfig, PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        adapter_path = Path(verification["adapter"])
        tokenizer = AutoTokenizer.from_pretrained(sharded_root, local_files_only=True, trust_remote_code=False)
        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        base = AutoModelForCausalLM.from_pretrained(
            sharded_root,
            local_files_only=True,
            trust_remote_code=False,
            device_map={"": 0},
            quantization_config=quantization,
            dtype=torch.float16,
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
            {
                "event": "sharded_model_loaded",
                "attempt_id": authorization["attempt_id"],
                "random_modules": len(random_receipts),
                "utc": _utc_now(),
            },
        )

        train_rows = legacy._load_jsonl(repo_root / protocol["data"]["train_path"], "train")
        eval_rows = legacy._load_jsonl(repo_root / protocol["data"]["eval_path"], "eval")
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
            artifact_paths, marker = helpers["chunk_paths"](run_root, start, end)
            if helpers["chunk_complete"](marker, artifact_paths, run_root, protocol_hash):
                chunks_complete += 1
                append_jsonl(events_path, {"event": "chunk_resumed", "start": start, "end": end, "utc": _utc_now()})
                continue
            helpers["quarantine_partial"](run_root, artifact_paths, marker)
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
                    adapted_hidden, adapted_ll = legacy._forward_receipt(torch, model, encoded, layers, adapter_name=condition)
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
            artifacts = {helpers["artifact_key"](path, run_root): sha256_file(path) for path in artifact_paths}
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

        final_artifacts = helpers["assemble_context"](run_root, protocol, protocol_hash, atomic_json, atomic_npz)
        verified_shards = verify_sharded_snapshot(sharded_root, protocol_hash=protocol_hash, source_hash=protocol["model"]["weights_sha256"])
        terminal = {
            "schema": "pixie_5d_context3_sharded_summary_v3",
            "status": "COMPLETE",
            "experiment_id": protocol["experiment_id"],
            "protocol_sha256": protocol_hash,
            "continuation_id": continuation_id,
            "attempt_id": authorization["attempt_id"],
            "authorization": authorization,
            "verification": verification,
            "sharding_manifest_sha256": sha256_file(sharded_root / "sharding_manifest.json"),
            "shard_count": verified_shards["shard_count"],
            "reused_contexts": [0, 1, 2],
            "captured_context": 3,
            "chunks_complete": chunks_complete,
            "context3_artifacts": final_artifacts,
            "adapter_layer_effective_update_energy": helpers["layer_energy"](random_receipts),
            "random_control": {"seed": protocol["seeds"]["random_adapter"], "modules": random_receipts},
            "packages": helpers["package_versions"](),
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
                "schema": "pixie_5d_context3_sharded_abort_v3",
                "status": "ABORTED",
                "attempt_id": authorization["attempt_id"],
                "protocol_sha256": protocol_hash,
                "error_type": type(failure).__name__,
                "error": str(failure),
                "sharding_manifest_sha256": (
                    sha256_file(sharded_root / "sharding_manifest.json")
                    if (sharded_root / "sharding_manifest.json").is_file()
                    else None
                ),
                "cleanup": cleanup,
                "wall_time_seconds": time.monotonic() - started,
                "utc": _utc_now(),
            },
        )
        append_jsonl(events_path, {"event": "v03_aborted", "abort": str(abort_path), "utc": _utc_now()})
        raise ContinuationError(f"v0.3 continuation aborted; receipt: {abort_path}; cause: {failure}") from failure
    assert terminal is not None
    terminal["cleanup"] = cleanup
    terminal["wall_time_seconds"] = time.monotonic() - started
    if cleanup["status"] != "PASS":
        terminal["status"] = "CLEANUP_FAILED"
    atomic_json(summary_path, terminal)
    append_jsonl(events_path, {"event": "v03_complete", "status": terminal["status"], "utc": _utc_now()})
    if terminal["status"] != "COMPLETE":
        raise ContinuationError(f"v0.3 science completed but cleanup failed: {summary_path}")
    return terminal
