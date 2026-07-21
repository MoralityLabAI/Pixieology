"""Bounded, resumable Bonsai activation capture for the registered experiment."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import nullcontext
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any

import numpy as np

from .authorization import Authorization, validate_authorization
from .io import append_jsonl, atomic_json, atomic_npz
from .protocol import (
    load_protocol,
    resolve_config_path,
    resolve_repo_config,
    sha256_file,
    verify_frozen_inputs,
)


class CaptureError(RuntimeError):
    """The registered capture cannot produce an auditable result."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_jsonl(path: Path, split: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise CaptureError(f"invalid JSON at {path}:{line_number}: {error}") from error
            messages = value.get("messages")
            if not isinstance(messages, list) or len(messages) < 2 or messages[-1].get("role") != "assistant":
                raise CaptureError(f"{path}:{line_number} must end with an assistant message")
            if value.get("kind") not in {"canary", "style"}:
                raise CaptureError(f"{path}:{line_number} has an unregistered behavior family")
            value["split"] = split
            rows.append(value)
    identifiers = [row.get("id") for row in rows]
    if any(not isinstance(item, str) or not item for item in identifiers) or len(set(identifiers)) != len(identifiers):
        raise CaptureError(f"{path} contains missing or duplicate row IDs")
    return rows


def _render_context(messages: Sequence[Mapping[str, str]], context: str) -> list[dict[str, str]]:
    rendered = [{"role": str(item["role"]), "content": str(item["content"])} for item in messages]
    if context == "original_system":
        return rendered
    if rendered and rendered[0]["role"] == "system":
        rendered[0]["content"] = context
    else:
        rendered.insert(0, {"role": "system", "content": context})
    return rendered


def _token_ids(value: Any) -> list[int]:
    if isinstance(value, Mapping):
        value = value.get("input_ids")
    if value is None:
        raise CaptureError("chat template did not return input_ids")
    if hasattr(value, "reshape") and hasattr(value, "tolist"):
        return [int(item) for item in value.reshape(-1).tolist()]
    if value and isinstance(value[0], (list, tuple)):
        if len(value) != 1:
            raise CaptureError("expected a single encoded chat")
        value = value[0]
    return [int(item) for item in value]


def _encode_chat(tokenizer: Any, messages: Sequence[dict[str, str]], maximum_length: int) -> dict[str, Any]:
    prefix = _token_ids(
        tokenizer.apply_chat_template(list(messages[:-1]), tokenize=True, add_generation_prompt=True)
    )
    full = _token_ids(
        tokenizer.apply_chat_template(list(messages), tokenize=True, add_generation_prompt=False)
    )
    common = 0
    for left, right in zip(prefix, full):
        if left != right:
            break
        common += 1
    if common <= 0 or common >= len(full):
        raise CaptureError("chat template did not expose both prompt and assistant tokens")
    cut = max(0, len(full) - maximum_length)
    input_ids = full[cut:]
    supervised_start = common - cut
    if supervised_start <= 0:
        raise CaptureError("maximum sequence length removed the final prompt token")
    if supervised_start >= len(input_ids):
        raise CaptureError("maximum sequence length removed every assistant token")
    labels = [-100] * supervised_start + input_ids[supervised_start:]
    return {
        "input_ids": input_ids,
        "labels": labels,
        "prompt_index": supervised_start - 1,
        "supervised_tokens": len(input_ids) - supervised_start,
    }


def _mean_log_likelihood(torch: Any, logits: Any, labels: Any) -> float:
    shifted_labels = labels[:, 1:]
    mask = shifted_labels.ne(-100)
    if int(mask.sum().item()) == 0:
        raise CaptureError("teacher-forced score has no supervised tokens")
    log_probabilities = torch.nn.functional.log_softmax(logits[:, :-1, :].float(), dim=-1)
    safe_labels = shifted_labels.masked_fill(~mask, 0)
    selected = log_probabilities.gather(-1, safe_labels.unsqueeze(-1)).squeeze(-1)
    return float(selected[mask].mean().item())


def _forward_receipt(
    torch: Any,
    model: Any,
    encoded: Mapping[str, Any],
    layers: Sequence[int],
    *,
    adapter_name: str | None,
) -> tuple[np.ndarray, float]:
    input_ids = torch.tensor([encoded["input_ids"]], dtype=torch.long, device="cuda:0")
    attention_mask = torch.ones_like(input_ids)
    labels = torch.tensor([encoded["labels"]], dtype=torch.long, device="cuda:0")
    context = model.disable_adapter() if adapter_name is None else nullcontext()
    if adapter_name is not None:
        model.set_adapter(adapter_name)
    with context, torch.inference_mode():
        output = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            output_hidden_states=True,
            use_cache=False,
            return_dict=True,
        )
        hidden = torch.stack(
            [output.hidden_states[int(layer) + 1][0, int(encoded["prompt_index"]), :].float().cpu() for layer in layers]
        ).numpy()
        mean_log_likelihood = _mean_log_likelihood(torch, output.logits, labels)
    del output, input_ids, attention_mask, labels
    return hidden, mean_log_likelihood


def _product_norm(left: np.ndarray, right: np.ndarray) -> float:
    """Return ||left @ right||_F without materializing the full update."""
    left_gram = left.T @ left
    right_gram = right @ right.T
    squared = float(np.sum(left_gram * right_gram.T))
    return math.sqrt(max(0.0, squared))


def _module_seed(root_seed: int, name: str) -> int:
    digest = hashlib.sha256(f"{root_seed}:{name}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def configure_norm_matched_random_adapter(model: Any, adapter_config: Any, root_seed: int) -> list[dict[str, Any]]:
    """Install one random adapter matched per module on effective update norm."""
    random_name = "random_00"
    model.add_adapter(random_name, adapter_config)
    receipts: list[dict[str, Any]] = []
    for name, module in model.named_modules():
        if not all(hasattr(module, attribute) for attribute in ("lora_A", "lora_B", "scaling")):
            continue
        if "trained" not in module.lora_A or random_name not in module.lora_A:
            continue
        trained_a_tensor = module.lora_A["trained"].weight
        trained_b_tensor = module.lora_B["trained"].weight
        random_a_tensor = module.lora_A[random_name].weight
        random_b_tensor = module.lora_B[random_name].weight
        trained_a = trained_a_tensor.detach().float().cpu().numpy().astype(np.float64)
        trained_b = trained_b_tensor.detach().float().cpu().numpy().astype(np.float64)
        scale = float(module.scaling["trained"])
        target_product_norm = _product_norm(trained_b, trained_a)
        rng = np.random.default_rng(_module_seed(root_seed, name))
        random_a = rng.normal(0.0, 1.0 / math.sqrt(max(1, trained_a.shape[1])), size=trained_a.shape)
        random_b = rng.normal(0.0, 1.0 / math.sqrt(max(1, trained_b.shape[1])), size=trained_b.shape)
        raw_product_norm = _product_norm(random_b, random_a)
        if target_product_norm == 0.0:
            random_b.fill(0.0)
        elif raw_product_norm <= 0.0:
            raise CaptureError(f"random control for {name} has zero pre-scaling norm")
        else:
            random_b *= target_product_norm / raw_product_norm
        import torch

        with torch.no_grad():
            random_a_tensor.copy_(torch.as_tensor(random_a, dtype=random_a_tensor.dtype, device=random_a_tensor.device))
            random_b_tensor.copy_(torch.as_tensor(random_b, dtype=random_b_tensor.dtype, device=random_b_tensor.device))
        copied_a = random_a_tensor.detach().float().cpu().numpy().astype(np.float64)
        copied_b = random_b_tensor.detach().float().cpu().numpy().astype(np.float64)
        actual_product_norm = _product_norm(copied_b, copied_a)
        target_effective = abs(scale) * target_product_norm
        actual_effective = abs(float(module.scaling[random_name])) * actual_product_norm
        relative_error = abs(actual_effective - target_effective) / max(target_effective, 1e-12)
        if relative_error > 5e-4:
            raise CaptureError(f"norm match for {name} exceeded tolerance: {relative_error}")
        receipts.append(
            {
                "module": name,
                "a_shape": list(trained_a.shape),
                "b_shape": list(trained_b.shape),
                "target_effective_norm": target_effective,
                "actual_effective_norm": actual_effective,
                "relative_error": relative_error,
            }
        )
    if not receipts:
        raise CaptureError("no LoRA modules were found for the random control")
    model.eval()
    return receipts


def _layer_energy(receipts: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    squared: dict[str, float] = {}
    for receipt in receipts:
        match = re.search(r"(?:^|\.)layers\.(\d+)(?:\.|$)", str(receipt["module"]))
        if match is None:
            continue
        layer = match.group(1)
        squared[layer] = squared.get(layer, 0.0) + float(receipt["target_effective_norm"]) ** 2
    return {layer: math.sqrt(value) for layer, value in sorted(squared.items(), key=lambda item: int(item[0]))}


def _context_is_complete(marker: Path, protocol_hash: str, expected: Sequence[Path]) -> bool:
    if not marker.is_file():
        return False
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    expected_hashes = {
        f"{path.parent.name}/{path.name}": sha256_file(path) for path in expected if path.is_file()
    }
    return (
        value.get("schema") == "pixie_5d_capture_context_v1"
        and value.get("protocol_sha256") == protocol_hash
        and value.get("artifacts") == expected_hashes
        and len(expected_hashes) == len(expected)
    )


def _quarantine_partial(run_root: Path, context_index: int, paths: Sequence[Path], marker: Path) -> None:
    present = [path for path in [*paths, marker] if path.exists()]
    if not present:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = run_root / "quarantine" / f"context_{context_index:02d}_{stamp}"
    destination.mkdir(parents=True, exist_ok=False)
    for path in present:
        path.replace(destination / path.name)


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for package in ("torch", "transformers", "peft", "bitsandbytes", "numpy", "safetensors"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def _cleanup(torch: Any | None) -> dict[str, Any]:
    receipt: dict[str, Any] = {"started_utc": _utc_now(), "status": "PASS"}
    errors: list[str] = []
    gc.collect()
    if torch is not None and torch.cuda.is_available():
        for operation in (torch.cuda.synchronize, torch.cuda.empty_cache, torch.cuda.ipc_collect):
            try:
                operation()
            except Exception as error:  # cleanup must record every failure
                errors.append(f"{operation.__name__}: {type(error).__name__}: {error}")
        try:
            free, total = torch.cuda.mem_get_info()
            receipt["cuda_free_bytes"] = int(free)
            receipt["cuda_total_bytes"] = int(total)
            receipt["cuda_allocated_bytes"] = int(torch.cuda.memory_allocated())
            receipt["cuda_reserved_bytes"] = int(torch.cuda.memory_reserved())
        except Exception as error:
            errors.append(f"memory_receipt: {type(error).__name__}: {error}")
    receipt["ended_utc"] = _utc_now()
    if errors:
        receipt["status"] = "CLEANUP_FAILED"
        receipt["errors"] = errors
    return receipt


def capture_real(repo_root: Path, experiment_root: Path, authorization_path: Path) -> dict[str, Any]:
    """Capture trained, zero, and one norm-matched-random condition.

    Authorization and wrapper gates run before the heavy stack is imported.
    Every completed context is independently hashed, making interruption and
    resumption safe without treating partial archives as evidence.
    """
    protocol_path = experiment_root / "protocol.json"
    protocol = load_protocol(experiment_root)
    authorization: Authorization = validate_authorization(
        authorization_path,
        protocol_path,
        protocol,
        require_active_wrapper=True,
    )
    frozen = verify_frozen_inputs(repo_root, experiment_root)
    if not frozen["ok"]:
        raise CaptureError(f"frozen input verification failed: {frozen['checks']}")
    protocol_hash = sha256_file(protocol_path)
    config = resolve_repo_config(repo_root)
    output_root = resolve_config_path(repo_root, config, "pixie_5d_holonomy_output_root")
    run_root = output_root / "capture" / authorization.run_id
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    if summary_path.is_file():
        previous = json.loads(summary_path.read_text(encoding="utf-8"))
        if previous.get("status") == "COMPLETE" and previous.get("protocol_sha256") == protocol_hash:
            conditions = ("zero", "trained", "random_00")
            complete = all(
                _context_is_complete(
                    run_root / f"context_{context_index:02d}.complete.json",
                    protocol_hash,
                    [run_root / condition / f"context_{context_index:02d}.npz" for condition in conditions],
                )
                for context_index in range(len(protocol["contexts"]))
            )
            if complete:
                return previous
            raise CaptureError(f"completed summary has missing or hash-mismatched context artifacts: {summary_path}")
        raise CaptureError(f"run directory already contains a non-reusable summary: {summary_path}")

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["WANDB_DISABLED"] = "true"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    started = time.monotonic()
    events = run_root / "events.jsonl"
    append_jsonl(events, {"event": "capture_started", "utc": _utc_now(), "protocol_sha256": protocol_hash})
    torch = tokenizer = model = None
    terminal: dict[str, Any] | None = None
    failure: BaseException | None = None
    try:
        import torch as torch_module
        from peft import PeftConfig, PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        torch = torch_module
        if not torch.cuda.is_available():
            raise CaptureError("CUDA is unavailable inside the capped capture")
        torch.manual_seed(int(protocol["seeds"]["root"]))
        torch.cuda.manual_seed_all(int(protocol["seeds"]["root"]))
        torch.cuda.reset_peak_memory_stats()
        model_path = Path(str(frozen["model"]))
        adapter_path = Path(str(frozen["adapter"]))
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
        random_receipts = configure_norm_matched_random_adapter(
            model, adapter_config, int(protocol["seeds"]["random_adapter"])
        )
        append_jsonl(events, {"event": "model_loaded", "utc": _utc_now(), "random_modules": len(random_receipts)})

        train_path = (experiment_root / protocol["data"]["train_path"]).resolve()
        eval_path = (experiment_root / protocol["data"]["eval_path"]).resolve()
        rows = _load_jsonl(train_path, "train") + _load_jsonl(eval_path, "eval")
        if set(row["id"] for row in rows[: len(_load_jsonl(train_path, "train"))]) & set(row["id"] for row in _load_jsonl(eval_path, "eval")):
            raise CaptureError("construction and evaluation IDs overlap")
        layers = [int(layer) for layer in protocol["layers"]]
        conditions = ("zero", "trained", "random_00")
        completed_contexts = 0
        for context_index, context_text in enumerate(protocol["contexts"]):
            artifact_paths = [run_root / condition / f"context_{context_index:02d}.npz" for condition in conditions]
            marker = run_root / f"context_{context_index:02d}.complete.json"
            if _context_is_complete(marker, protocol_hash, artifact_paths):
                completed_contexts += 1
                append_jsonl(events, {"event": "context_resumed", "utc": _utc_now(), "context": context_index})
                continue
            _quarantine_partial(run_root, context_index, artifact_paths, marker)
            condition_delta: dict[str, list[np.ndarray]] = {name: [] for name in conditions}
            condition_ll: dict[str, list[float]] = {name: [] for name in conditions}
            base_ll: list[float] = []
            token_counts: list[int] = []
            supervised_counts: list[int] = []
            for row_index, row in enumerate(rows):
                messages = _render_context(row["messages"], str(context_text))
                encoded = _encode_chat(tokenizer, messages, int(protocol["maximum_sequence_length"]))
                base_hidden, baseline_ll = _forward_receipt(torch, model, encoded, layers, adapter_name=None)
                base_ll.append(baseline_ll)
                token_counts.append(len(encoded["input_ids"]))
                supervised_counts.append(int(encoded["supervised_tokens"]))
                condition_delta["zero"].append(np.zeros_like(base_hidden, dtype=np.float32))
                condition_ll["zero"].append(baseline_ll)
                for condition in ("trained", "random_00"):
                    adapted_hidden, adapted_ll = _forward_receipt(
                        torch, model, encoded, layers, adapter_name=condition
                    )
                    condition_delta[condition].append((adapted_hidden - base_hidden).astype(np.float32))
                    condition_ll[condition].append(adapted_ll)
                if (row_index + 1) % 8 == 0:
                    append_jsonl(
                        events,
                        {
                            "event": "capture_progress",
                            "utc": _utc_now(),
                            "context": context_index,
                            "rows_complete": row_index + 1,
                            "rows_total": len(rows),
                        },
                    )
            base_ll_array = np.asarray(base_ll, dtype=np.float32)
            for condition, artifact in zip(conditions, artifact_paths):
                ll = np.asarray(condition_ll[condition], dtype=np.float32)
                atomic_npz(
                    artifact,
                    delta=np.stack(condition_delta[condition]).astype(np.float32),
                    row_ids=np.asarray([row["id"] for row in rows], dtype=np.str_),
                    families=np.asarray([row["kind"] for row in rows], dtype=np.str_),
                    splits=np.asarray([row["split"] for row in rows], dtype=np.str_),
                    layers=np.asarray(layers, dtype=np.int16),
                    context_index=np.asarray([context_index], dtype=np.int16),
                    token_counts=np.asarray(token_counts, dtype=np.int16),
                    supervised_token_counts=np.asarray(supervised_counts, dtype=np.int16),
                    base_mean_log_likelihood=base_ll_array,
                    condition_mean_log_likelihood=ll,
                    log_likelihood_gain=(ll - base_ll_array).astype(np.float32),
                )
            artifacts = {f"{path.parent.name}/{path.name}": sha256_file(path) for path in artifact_paths}
            atomic_json(
                marker,
                {
                    "schema": "pixie_5d_capture_context_v1",
                    "protocol_sha256": protocol_hash,
                    "context_index": context_index,
                    "context": context_text,
                    "rows": len(rows),
                    "artifacts": artifacts,
                    "completed_utc": _utc_now(),
                },
            )
            completed_contexts += 1
            append_jsonl(events, {"event": "context_complete", "utc": _utc_now(), "context": context_index})
            del condition_delta, condition_ll, base_ll_array
            gc.collect()

        terminal = {
            "schema": "pixie_5d_capture_summary_v1",
            "status": "COMPLETE",
            "experiment_id": protocol["experiment_id"],
            "protocol_sha256": protocol_hash,
            "run_id": authorization.run_id,
            "authorization": authorization.receipt,
            "frozen_inputs": frozen,
            "conditions": list(conditions),
            "contexts_complete": completed_contexts,
            "rows": len(rows),
            "layers": layers,
            "random_control": {
                "seed": protocol["seeds"]["random_adapter"],
                "modules": random_receipts,
            },
            "adapter_layer_effective_update_energy": _layer_energy(random_receipts),
            "packages": _package_versions(),
            "resource_wrapper": {
                "active": os.environ.get("PIXIE_RESOURCE_CAP_ACTIVE") == "1",
                "run_id": os.environ.get("PIXIE_RUN_ID"),
                "launcher_sha256": os.environ.get("PIXIE_CAP_WRAPPER_SHA256"),
            },
            "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated()),
            "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved()),
            "wall_time_seconds_before_cleanup": time.monotonic() - started,
        }
    except BaseException as error:
        failure = error
    finally:
        model = None
        tokenizer = None
        try:
            base = None
        except UnboundLocalError:
            pass
        cleanup = _cleanup(torch)

    if failure is not None:
        abort = {
            "schema": "pixie_5d_capture_abort_v1",
            "status": "ABORTED",
            "protocol_sha256": protocol_hash,
            "run_id": authorization.run_id,
            "error_type": type(failure).__name__,
            "error": str(failure),
            "cleanup": cleanup,
            "wall_time_seconds": time.monotonic() - started,
            "utc": _utc_now(),
        }
        abort_path = run_root / "aborts" / f"abort_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
        atomic_json(abort_path, abort)
        append_jsonl(events, {"event": "capture_aborted", "utc": _utc_now(), "abort": str(abort_path)})
        raise CaptureError(f"capture aborted; receipt: {abort_path}; cause: {failure}") from failure
    assert terminal is not None
    terminal["cleanup"] = cleanup
    terminal["wall_time_seconds"] = time.monotonic() - started
    if cleanup["status"] != "PASS":
        terminal["status"] = "CLEANUP_FAILED"
    atomic_json(summary_path, terminal)
    append_jsonl(events, {"event": "capture_complete", "utc": _utc_now(), "status": terminal["status"]})
    if terminal["status"] != "COMPLETE":
        raise CaptureError(f"capture science completed but cleanup failed: {summary_path}")
    return terminal
