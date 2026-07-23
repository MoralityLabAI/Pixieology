"""Bounded, resumable module-input and LoRA-response capture."""

from __future__ import annotations

from contextlib import nullcontext
import gc
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Mapping, Sequence

import numpy as np

from .authorization import validate_authorization
from .geometry import CompactSVD, compact_update_svd, response_coordinates
from .io import append_jsonl, atomic_json, atomic_npz, sha256_file, utc_now
from .protocol import (
    build_corpus_from_protocol,
    load_protocol,
    load_repo_config,
    protocol_hash,
    resolve_config_path,
    verify_frozen_inputs,
)
from .safetensors_raw import verify_snapshot


class CaptureError(RuntimeError):
    """The bounded capture cannot emit an auditable checkpoint."""


MODULE_PATTERN = re.compile(
    r"(?:^|\.)layers\.(?P<layer>\d+)\..*\.(?P<module>q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$"
)


def _token_ids(value: Any) -> list[int]:
    if isinstance(value, Mapping):
        value = value.get("input_ids")
    if hasattr(value, "reshape") and hasattr(value, "tolist"):
        return [int(item) for item in value.reshape(-1).tolist()]
    if isinstance(value, list) and value and isinstance(value[0], list):
        value = value[0]
    if not isinstance(value, list):
        raise CaptureError("tokenizer did not return input IDs")
    return [int(item) for item in value]


def _encode_row(tokenizer: Any, row: dict[str, Any], maximum_length: int) -> dict[str, Any]:
    messages = list(row["messages"])
    prompt_ids = _token_ids(tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))
    expected = row.get("expected_completion")
    if expected is None:
        cut = max(0, len(prompt_ids) - maximum_length)
        input_ids = prompt_ids[cut:]
        return {
            "input_ids": input_ids,
            "labels": None,
            "prompt_index": len(input_ids) - 1,
            "supervised_tokens": 0,
        }
    completed = [*messages, {"role": "assistant", "content": str(expected)}]
    full_ids = _token_ids(tokenizer.apply_chat_template(completed, tokenize=True, add_generation_prompt=False))
    common = 0
    for left, right in zip(prompt_ids, full_ids):
        if left != right:
            break
        common += 1
    if common <= 0 or common >= len(full_ids):
        raise CaptureError(f"chat template did not expose prompt and completion for {row['id']}")
    cut = max(0, len(full_ids) - maximum_length)
    input_ids = full_ids[cut:]
    supervised_start = common - cut
    if supervised_start <= 0 or supervised_start >= len(input_ids):
        raise CaptureError(f"maximum length removed prompt or completion for {row['id']}")
    return {
        "input_ids": input_ids,
        "labels": [-100] * supervised_start + input_ids[supervised_start:],
        "prompt_index": supervised_start - 1,
        "supervised_tokens": len(input_ids) - supervised_start,
    }


def _mean_log_likelihood(torch: Any, logits: Any, labels: Any | None) -> float:
    if labels is None:
        return float("nan")
    shifted = labels[:, 1:]
    mask = shifted.ne(-100)
    log_probabilities = torch.nn.functional.log_softmax(logits[:, :-1, :].float(), dim=-1)
    safe = shifted.masked_fill(~mask, 0)
    selected = log_probabilities.gather(-1, safe.unsqueeze(-1)).squeeze(-1)
    return float(selected[mask].mean().item())


def _module_key(name: str) -> tuple[int, str] | None:
    match = MODULE_PATTERN.search(name)
    if match is None:
        return None
    return int(match.group("layer")), str(match.group("module"))


def _trained_updates(model: Any, module_ids: Sequence[str]) -> tuple[dict[tuple[int, str], CompactSVD], dict[tuple[int, str], Any]]:
    updates: dict[tuple[int, str], CompactSVD] = {}
    modules: dict[tuple[int, str], Any] = {}
    for name, module in model.named_modules():
        key = _module_key(name)
        if key is None or key[1] not in module_ids:
            continue
        if not all(hasattr(module, attribute) for attribute in ("lora_A", "lora_B", "scaling")):
            continue
        if "trained" not in module.lora_A or "trained" not in module.lora_B:
            continue
        a = module.lora_A["trained"].weight.detach().float().cpu().numpy()
        b = module.lora_B["trained"].weight.detach().float().cpu().numpy()
        updates[key] = compact_update_svd(a, b, float(module.scaling["trained"]))
        modules[key] = module
    expected = {(layer, module_id) for layer in range(28) for module_id in module_ids}
    if set(updates) != expected:
        missing = sorted(expected - set(updates))
        raise CaptureError(f"trained adapter module inventory mismatch; missing={missing[:8]}")
    return updates, modules


def _cleanup(torch: Any | None) -> dict[str, Any]:
    receipt: dict[str, Any] = {"started_utc": utc_now(), "status": "PASS", "errors": []}
    gc.collect()
    if torch is not None and torch.cuda.is_available():
        for operation in (torch.cuda.synchronize, torch.cuda.empty_cache, torch.cuda.ipc_collect):
            try:
                operation()
            except Exception as error:  # cleanup is evidence
                receipt["errors"].append(f"{operation.__name__}: {type(error).__name__}: {error}")
        try:
            receipt["cuda_allocated_bytes"] = int(torch.cuda.memory_allocated())
            receipt["cuda_reserved_bytes"] = int(torch.cuda.memory_reserved())
        except Exception as error:
            receipt["errors"].append(f"memory_receipt: {type(error).__name__}: {error}")
    if receipt["errors"]:
        receipt["status"] = "CLEANUP_FAILED"
    receipt["ended_utc"] = utc_now()
    return receipt


def capture_chunk(
    repo_root: Path,
    experiment_root: Path,
    authorization_path: Path,
    *,
    chunk_index: int,
) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    authorization = validate_authorization(
        authorization_path,
        experiment_root,
        protocol,
        require_active_wrapper=True,
    )
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
    rows = build_corpus_from_protocol(protocol)
    chunk_rows = int(protocol["capture"]["chunk_rows"])
    start = int(chunk_index) * chunk_rows
    selected = rows[start : start + chunk_rows]
    if not selected:
        raise CaptureError(f"chunk index {chunk_index} is outside the corpus")
    run_root = output_root / "capture" / authorization.run_id / f"chunk_{chunk_index:02d}"
    run_root.mkdir(parents=True, exist_ok=True)
    events = run_root / "events.jsonl"
    append_jsonl(events, {"event": "capture_started", "utc": utc_now(), "chunk_index": chunk_index})
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
    hooks: list[Any] = []
    failure: BaseException | None = None
    summary: dict[str, Any] | None = None
    try:
        import torch as torch_module
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        torch = torch_module
        if not torch.cuda.is_available():
            raise CaptureError("CUDA is unavailable inside the capped capture")
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
        module_ids = list(protocol["module_ids"])
        updates, modules = _trained_updates(model, module_ids)
        append_jsonl(events, {"event": "model_loaded", "utc": utc_now(), "module_count": len(modules)})

        active: dict[str, Any] = {"enabled": False, "prompt_index": -1, "inputs": {}, "base_norms": {}}
        for key, module in modules.items():
            def receive(_module: Any, arguments: tuple[Any, ...], output: Any, *, module_key: tuple[int, str] = key) -> None:
                if not active["enabled"]:
                    return
                prompt_index = int(active["prompt_index"])
                x = arguments[0][0, prompt_index, :].detach().float().cpu().numpy()
                y = output[0, prompt_index, :].detach().float().cpu().numpy()
                active["inputs"][module_key] = x
                active["base_norms"][module_key] = float(np.linalg.norm(y))

            hooks.append(module.register_forward_hook(receive))

        checkpoint_rows = int(protocol["capture"]["checkpoint_rows"])
        completed_groups = 0
        for local_start in range(0, len(selected), checkpoint_rows):
            group = selected[local_start : local_start + checkpoint_rows]
            group_path = run_root / f"rows_{start + local_start:03d}_{start + local_start + len(group) - 1:03d}.npz"
            marker_path = group_path.with_suffix(".complete.json")
            if marker_path.is_file() and group_path.is_file():
                marker = json.loads(marker_path.read_text(encoding="utf-8"))
                if marker.get("artifact_sha256") == sha256_file(group_path):
                    completed_groups += 1
                    append_jsonl(events, {"event": "checkpoint_resumed", "utc": utc_now(), "path": str(group_path)})
                    continue
            input_buffers: dict[tuple[int, str], list[np.ndarray]] = {key: [] for key in modules}
            norm_buffers: dict[tuple[int, str], list[float]] = {key: [] for key in modules}
            raw_coordinates: list[np.ndarray] = []
            base_ll: list[float] = []
            trained_ll: list[float] = []
            token_counts: list[int] = []
            for row in group:
                encoded = _encode_row(tokenizer, row, int(protocol["capture"]["maximum_sequence_length"]))
                input_ids = torch.tensor([encoded["input_ids"]], dtype=torch.long, device="cuda:0")
                attention_mask = torch.ones_like(input_ids)
                labels = (
                    None
                    if encoded["labels"] is None
                    else torch.tensor([encoded["labels"]], dtype=torch.long, device="cuda:0")
                )
                active.update({"enabled": True, "prompt_index": encoded["prompt_index"], "inputs": {}, "base_norms": {}})
                with model.disable_adapter(), torch.inference_mode():
                    base_output = model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        use_cache=False,
                        return_dict=True,
                    )
                active["enabled"] = False
                if set(active["inputs"]) != set(modules):
                    raise CaptureError(f"module hooks were incomplete for {row['id']}")
                row_coordinates = np.zeros((28, len(module_ids), 3), dtype=np.float32)
                for layer in range(28):
                    for module_index, module_id in enumerate(module_ids):
                        key = (layer, module_id)
                        x = active["inputs"][key]
                        base_norm = active["base_norms"][key]
                        row_coordinates[layer, module_index] = response_coordinates(x, base_norm, updates[key])
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
            arrays: dict[str, Any] = {
                "row_ids": np.asarray([row["id"] for row in group], dtype=np.str_),
                "semantic_group_ids": np.asarray([row["semantic_group_id"] for row in group], dtype=np.str_),
                "families": np.asarray([row["family"] for row in group], dtype=np.str_),
                "variants": np.asarray([row["variant"] for row in group], dtype=np.str_),
                "splits": np.asarray([row["split"] for row in group], dtype=np.str_),
                "outcome_eligible": np.asarray([row["outcome_eligible"] for row in group], dtype=np.bool_),
                "raw_coordinates": np.stack(raw_coordinates),
                "base_mean_log_likelihood": np.asarray(base_ll, dtype=np.float32),
                "trained_mean_log_likelihood": np.asarray(trained_ll, dtype=np.float32),
                "token_counts": np.asarray(token_counts, dtype=np.int16),
            }
            for key in sorted(modules):
                layer, module_id = key
                arrays[f"input__{layer:02d}__{module_id}"] = np.stack(input_buffers[key])
                arrays[f"base_norm__{layer:02d}__{module_id}"] = np.asarray(norm_buffers[key], dtype=np.float32)
            atomic_npz(group_path, **arrays)
            marker = {
                "schema": "pixieology_etale_capture_checkpoint_v1",
                "protocol_sha256": protocol_hash(experiment_root),
                "chunk_index": chunk_index,
                "row_ids": [row["id"] for row in group],
                "artifact": str(group_path),
                "artifact_sha256": sha256_file(group_path),
                "completed_utc": utc_now(),
            }
            atomic_json(marker_path, marker)
            completed_groups += 1
            append_jsonl(events, {"event": "checkpoint_complete", "utc": utc_now(), "rows": len(group), "path": str(group_path)})
        for hook in hooks:
            hook.remove()
        summary = {
            "schema": "pixieology_etale_capture_chunk_summary_v1",
            "status": "COMPLETE",
            "protocol_sha256": protocol_hash(experiment_root),
            "run_id": authorization.run_id,
            "attempt_id": authorization.attempt_id,
            "chunk_index": chunk_index,
            "row_start": start,
            "row_count": len(selected),
            "checkpoint_count": completed_groups,
            "condition": "trained_counterfactual_on_base",
            "random_control_inputs_preserved": True,
            "live_trained_geometry": "UNAVAILABLE_NOT_CAPTURED",
            "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated()),
            "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved()),
            "wall_time_seconds_before_cleanup": time.monotonic() - started,
        }
    except BaseException as error:
        failure = error
    finally:
        for hook in hooks:
            hook.remove()
        updates = modules = hooks = active = None
        arrays = input_buffers = norm_buffers = raw_coordinates = None
        input_ids = attention_mask = labels = base_output = trained_output = None
        model = tokenizer = base = None
        cleanup = _cleanup(torch)
    if failure is not None:
        abort = {
            "schema": "pixieology_etale_capture_abort_v1",
            "status": "ABORTED",
            "run_id": authorization.run_id,
            "attempt_id": authorization.attempt_id,
            "chunk_index": chunk_index,
            "error_type": type(failure).__name__,
            "error": str(failure),
            "cleanup": cleanup,
            "wall_time_seconds": time.monotonic() - started,
            "utc": utc_now(),
        }
        atomic_json(run_root / "abort.json", abort)
        append_jsonl(events, {"event": "capture_aborted", "utc": utc_now(), "error_type": type(failure).__name__})
        raise CaptureError(f"capture aborted with durable receipt: {run_root / 'abort.json'}") from failure
    assert summary is not None
    summary["cleanup"] = cleanup
    summary["wall_time_seconds"] = time.monotonic() - started
    if cleanup["status"] != "PASS":
        summary["status"] = "CLEANUP_FAILED"
    atomic_json(run_root / "summary.json", summary)
    append_jsonl(events, {"event": "capture_complete", "utc": utc_now(), "status": summary["status"]})
    if summary["status"] != "COMPLETE":
        raise CaptureError("capture completed but cleanup failed")
    return summary
