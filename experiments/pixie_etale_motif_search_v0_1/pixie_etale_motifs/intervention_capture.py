"""Capped selective-LoRA intervention forwards for one frozen task."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any, Sequence

from .authorization import validate_authorization
from .capture import CaptureError, _cleanup, _encode_row, _mean_log_likelihood, _trained_updates
from .io import atomic_json, sha256_file, utc_now, write_jsonl
from .protocol import (
    build_corpus_from_protocol,
    load_protocol,
    load_repo_config,
    protocol_hash,
    resolve_config_path,
    verify_frozen_inputs,
)
from .safetensors_raw import verify_snapshot


def _set_enabled(modules: Sequence[Any], enabled: bool) -> None:
    for module in modules:
        if not hasattr(module, "enable_adapters"):
            raise CaptureError("installed PEFT layer lacks per-module enable_adapters")
        module.enable_adapters(enabled=enabled)


def capture_intervention_task(
    repo_root: Path,
    experiment_root: Path,
    authorization_path: Path,
    plan_path: Path,
    *,
    task_index: int,
    task_count: int = 4,
) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    authorization = validate_authorization(
        authorization_path,
        experiment_root,
        protocol,
        require_active_wrapper=True,
    )
    plan_hash = sha256_file(plan_path)
    if authorization.receipt.get("intervention_plan_sha256") != plan_hash:
        raise CaptureError("authorization is not bound to this resolved intervention plan")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("schema") != "pixieology_etale_intervention_plan_v1" or plan.get("execution_status") != "READY":
        raise CaptureError("intervention plan must be resolved and READY")
    tasks = plan.get("tasks", [])
    if task_index < 0 or task_index >= len(tasks):
        raise CaptureError(f"task index must be in 0..{max(0, len(tasks) - 1)}")
    if task_count < 1 or task_count > 8:
        raise CaptureError("task count must be in 1..8")
    selected_tasks = tasks[task_index : task_index + task_count]
    frozen = verify_frozen_inputs(repo_root, experiment_root, require_weights=True)
    if not frozen["ok"]:
        raise CaptureError(f"frozen input verification failed: {frozen['checks']}")
    config = load_repo_config(repo_root)
    output_root = resolve_config_path(repo_root, config, "pixie_etale_motif_output_root")
    sharded_root = resolve_config_path(repo_root, config, "pixie_etale_motif_sharded_model_root")
    verify_snapshot(
        sharded_root,
        protocol_sha256=protocol_hash(experiment_root),
        source_sha256=protocol["model"]["weights_sha256"],
        rehash_shards=True,
    )
    corpus = {str(row["id"]): row for row in build_corpus_from_protocol(protocol)}
    selected_rows = []
    for task in selected_tasks:
        row = corpus.get(str(task["unit_id"]))
        if row is None or not row.get("outcome_eligible") or row.get("expected_completion") is None:
            raise CaptureError("intervention task does not identify an outcome-eligible registered input")
        selected_rows.append(row)
    end_index = task_index + len(selected_tasks) - 1
    run_root = output_root / "interventions" / authorization.run_id / f"tasks_{task_index:03d}_{end_index:03d}"
    run_root.mkdir(parents=True, exist_ok=True)
    output_path = run_root / "observations.jsonl"
    marker_path = run_root / "complete.json"
    if output_path.is_file() and marker_path.is_file():
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if marker.get("artifact_sha256") == sha256_file(output_path) and marker.get("plan_sha256") == plan_hash:
            return marker
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "WANDB_DISABLED": "true",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
    started = time.monotonic()
    torch = tokenizer = model = base = None
    failure: BaseException | None = None
    summary: dict[str, Any] | None = None
    try:
        import torch as torch_module
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        torch = torch_module
        if not torch.cuda.is_available():
            raise CaptureError("CUDA is unavailable inside the capped intervention")
        torch.manual_seed(int(protocol["seeds"]["capture"]))
        torch.cuda.manual_seed_all(int(protocol["seeds"]["capture"]))
        torch.cuda.reset_peak_memory_stats()
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
        model = PeftModel.from_pretrained(base, Path(frozen["adapter"]), adapter_name="trained", is_trainable=False)
        model.eval()
        _, module_lookup = _trained_updates(model, protocol["module_ids"])
        all_modules = list(module_lookup.values())
        observations: list[dict[str, Any]] = []
        for task, row in zip(selected_tasks, selected_rows):
            encoded = _encode_row(tokenizer, row, int(protocol["capture"]["maximum_sequence_length"]))
            labels = torch.tensor([encoded["labels"]], dtype=torch.long, device="cuda:0")
            input_ids = torch.tensor([encoded["input_ids"]], dtype=torch.long, device="cuda:0")
            attention_mask = torch.ones_like(input_ids)
            for condition in task["conditions"]:
                condition_name = str(condition["condition"])
                mask = condition.get("mask")
                if condition_name not in {"base", "full_adapter"} and mask is None:
                    raise CaptureError(f"{condition_name} lacks a frozen mask")
                _set_enabled(all_modules, True)
                disabled: list[Any] = []
                if mask is not None:
                    for layer in range(int(mask["start_layer"]), int(mask["end_layer"]) + 1):
                        for module_id in mask["module_ids"]:
                            key = (layer, str(module_id))
                            if key not in module_lookup:
                                raise CaptureError(f"mask names unavailable module {key}")
                            disabled.append(module_lookup[key])
                    _set_enabled(disabled, False)
                context = model.disable_adapter() if condition_name == "base" else _null_context()
                try:
                    with context, torch.inference_mode():
                        output = model(
                            input_ids=input_ids,
                            attention_mask=attention_mask,
                            use_cache=False,
                            return_dict=True,
                        )
                    outcome = _mean_log_likelihood(torch, output.logits, labels)
                finally:
                    _set_enabled(disabled, True)
                observation = {
                    "schema": "pixieology_etale_intervention_observation_v1",
                    "task_id": task["task_id"],
                    "plan_sha256": plan_hash,
                    "unit_id": task["unit_id"],
                    "semantic_group_id": task["semantic_group_id"],
                    "motif_id": task["motif_id"],
                    "condition": condition_name,
                    "outcome": outcome,
                }
                if mask is not None:
                    observation["mask"] = mask
                observations.append(observation)
                del output
            del input_ids, attention_mask, labels
        write_jsonl(output_path, observations)
        summary = {
            "schema": "pixieology_etale_intervention_task_summary_v1",
            "status": "COMPLETE",
            "protocol_sha256": protocol_hash(experiment_root),
            "plan_sha256": plan_hash,
            "run_id": authorization.run_id,
            "attempt_id": authorization.attempt_id,
            "task_index": task_index,
            "task_count": len(selected_tasks),
            "task_ids": [task["task_id"] for task in selected_tasks],
            "observation_count": len(observations),
            "artifact": str(output_path),
            "artifact_sha256": sha256_file(output_path),
            "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated()),
            "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved()),
            "completed_utc": utc_now(),
        }
    except BaseException as error:
        failure = error
    finally:
        module_lookup = all_modules = input_ids = attention_mask = labels = output = observations = None
        model = tokenizer = base = None
        cleanup = _cleanup(torch)
    if failure is not None:
        abort = {
            "schema": "pixieology_etale_intervention_abort_v1",
            "status": "ABORTED",
            "plan_sha256": plan_hash,
            "task_index": task_index,
            "task_count": len(selected_tasks),
            "error_type": type(failure).__name__,
            "error": str(failure),
            "cleanup": cleanup,
            "wall_time_seconds": time.monotonic() - started,
            "utc": utc_now(),
        }
        atomic_json(run_root / "abort.json", abort)
        raise CaptureError(f"intervention aborted with durable receipt: {run_root / 'abort.json'}") from failure
    assert summary is not None
    summary["cleanup"] = cleanup
    summary["wall_time_seconds"] = time.monotonic() - started
    if cleanup["status"] != "PASS":
        summary["status"] = "CLEANUP_FAILED"
    atomic_json(marker_path, summary)
    if summary["status"] != "COMPLETE":
        raise CaptureError("intervention completed but cleanup failed")
    return summary


def _null_context():
    from contextlib import nullcontext

    return nullcontext()
