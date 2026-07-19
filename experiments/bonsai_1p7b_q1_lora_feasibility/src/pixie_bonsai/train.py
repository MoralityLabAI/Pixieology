"""Capped, deterministic QLoRA memory probing and resumable smoke training."""

from __future__ import annotations

import gc
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from .config import ExperimentConfig
from .data import dataset_manifest, load_jsonl
from .masking import AssistantOnlyCollator, encode_assistant_example
from .reporting import (
    append_jsonl, atomic_write_text, base_manifest, layout, sha256_file, utc_now, write_json, write_yaml,
)


EXPECTED_QWEN3_LINEAR_TARGETS = 196
EXPECTED_RANK8_TRAINABLE = 8_716_288
FORBIDDEN_ADAPTER_TERMS = ("embed_tokens", "word_embeddings", "lm_head")


class TrainingError(RuntimeError):
    """A hard feasibility invariant or local resource guard failed."""


class RuntimeLimitExceeded(TrainingError):
    """The configured child runtime guard expired before another optimizer step."""


def require_resource_cap() -> None:
    if os.environ.get("PIXIE_RESOURCE_CAP_ACTIVE") != "1":
        raise TrainingError(
            "GPU phases must run through scripts/run_capped.ps1 so the 10 GB RAM, "
            "50% CPU, 50 MB/s I/O, and 30-minute limits are active"
        )


def seed_everything(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    import torch
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def tokenizer_fingerprint(tokenizer: Any) -> dict[str, Any]:
    import hashlib
    template = tokenizer.chat_template or ""
    return {
        "class": tokenizer.__class__.__name__,
        "length": len(tokenizer),
        "vocab_size": tokenizer.vocab_size,
        "special_tokens_map": tokenizer.special_tokens_map,
        "chat_template_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest(),
    }


def cleanup_cuda() -> None:
    """Release only this process's Python/CUDA objects; never purge global caches."""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass


def load_quantized_base(config: ExperimentConfig) -> tuple[Any, Any]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    if not torch.cuda.is_available():
        raise TrainingError("PyTorch reports no CUDA device")
    model_cfg = config.section("model")
    cache = config.path("model_cache")
    offline = os.environ.get("HF_HUB_OFFLINE") == "1"
    tokenizer = AutoTokenizer.from_pretrained(
        model_cfg["unpacked_id"], revision=model_cfg["unpacked_revision"],
        cache_dir=cache, local_files_only=offline,
    )
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=config.section("training")["quant_type"],
        bnb_4bit_use_double_quant=bool(config.section("training")["double_quant"]),
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_cfg["unpacked_id"], revision=model_cfg["unpacked_revision"],
        cache_dir=cache, local_files_only=offline,
        quantization_config=quantization, device_map={"": 0},
        torch_dtype=torch.float16, attn_implementation="sdpa",
        low_cpu_mem_usage=True,
    )
    model.config.use_cache = False
    return tokenizer, model


def attach_new_adapter(model: Any, config: ExperimentConfig) -> tuple[Any, dict[str, Any]]:
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training

    training = config.section("training")
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=bool(training["gradient_checkpointing"]),
    )
    if training["gradient_checkpointing"]:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    lora = LoraConfig(
        r=int(training["rank"]), lora_alpha=int(training["alpha"]),
        lora_dropout=float(training["dropout"]), bias="none",
        target_modules="all-linear", task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora)
    return model, inspect_adapter(model, int(training["rank"]))


def load_saved_adapter(model: Any, adapter_path: Path, config: ExperimentConfig) -> tuple[Any, dict[str, Any]]:
    from peft import PeftModel, prepare_model_for_kbit_training

    training = config.section("training")
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=bool(training["gradient_checkpointing"]),
    )
    model = PeftModel.from_pretrained(model, adapter_path, is_trainable=True)
    if training["gradient_checkpointing"]:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    return model, inspect_adapter(model, int(training["rank"]))


def inspect_adapter(model: Any, rank: int) -> dict[str, Any]:
    targets = [name for name, module in model.named_modules() if hasattr(module, "lora_A")]
    trainable_names = [name for name, parameter in model.named_parameters() if parameter.requires_grad]
    forbidden = [name for name in trainable_names if any(term in name for term in FORBIDDEN_ADAPTER_TERMS)]
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    total = sum(parameter.numel() for parameter in model.parameters())
    if len(targets) != EXPECTED_QWEN3_LINEAR_TARGETS:
        raise TrainingError(f"expected 196 all-linear LoRA targets, found {len(targets)}")
    if forbidden:
        raise TrainingError(f"forbidden embeddings/lm_head became trainable: {forbidden[:5]}")
    if not trainable_names or any("lora_" not in name for name in trainable_names):
        raise TrainingError("non-LoRA parameters are trainable")
    expected = EXPECTED_RANK8_TRAINABLE * rank // 8
    if trainable != expected:
        raise TrainingError(f"expected {expected:,} trainable parameters at rank {rank}, found {trainable:,}")
    return {
        "target_module_count": len(targets), "target_modules": targets,
        "trainable_parameter_count": trainable, "total_parameter_count": total,
        "trainable_fraction": trainable / total, "rank": rank,
        "forbidden_trainable_parameters": forbidden,
    }


def _optimizer(model: Any, config: ExperimentConfig) -> tuple[Any, str, list[str]]:
    import torch
    training = config.section("training")
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    failures: list[str] = []
    try:
        import bitsandbytes as bnb
        cls = getattr(bnb.optim, "PagedAdamW8bit")
        return cls(parameters, lr=float(training["learning_rate"]), weight_decay=float(training["weight_decay"])), "paged_adamw_8bit", failures
    except Exception as exc:
        failures.append(f"PagedAdamW8bit: {exc!r}")
    try:
        import bitsandbytes as bnb
        return bnb.optim.AdamW8bit(parameters, lr=float(training["learning_rate"]), weight_decay=float(training["weight_decay"])), "adamw_8bit", failures
    except Exception as exc:
        failures.append(f"AdamW8bit: {exc!r}")
    return torch.optim.AdamW(parameters, lr=float(training["learning_rate"]), weight_decay=float(training["weight_decay"])), "torch_adamw", failures


def _scheduler(optimizer: Any, config: ExperimentConfig) -> Any:
    from torch.optim.lr_scheduler import LambdaLR
    warmup = int(config.section("training")["warmup_steps"])
    total = int(config.section("training")["total_steps"])
    def scale(step: int) -> float:
        if step < warmup:
            return float(step + 1) / max(1, warmup)
        return max(0.0, float(total - step) / max(1, total - warmup))
    return LambdaLR(optimizer, scale)


def _encoded_training_records(tokenizer: Any, config: ExperimentConfig) -> list[dict[str, list[int]]]:
    data_path = config.path("data_root") / "smoke_train.jsonl"
    records = load_jsonl(data_path)
    return [
        encode_assistant_example(tokenizer, record.messages, int(config.section("training")["sequence_length"]))
        for record in records
    ]


def _pad_to_length(batch: dict[str, Any], length: int, pad_token_id: int) -> dict[str, Any]:
    import torch
    width = batch["input_ids"].shape[1]
    if width >= length:
        return batch
    padding = length - width
    return {
        "input_ids": torch.nn.functional.pad(batch["input_ids"], (0, padding), value=pad_token_id),
        "attention_mask": torch.nn.functional.pad(batch["attention_mask"], (0, padding), value=0),
        "labels": torch.nn.functional.pad(batch["labels"], (0, padding), value=-100),
    }


def _to_device(batch: dict[str, Any]) -> dict[str, Any]:
    return {name: value.to("cuda:0", non_blocking=False) for name, value in batch.items()}


def _is_oom(exc: BaseException) -> bool:
    return "out of memory" in str(exc).lower() or exc.__class__.__name__ == "OutOfMemoryError"


def memory_probe(config: ExperimentConfig) -> dict[str, Any]:
    require_resource_cap()
    import torch

    paths = layout(config)
    base_training = config.section("training")
    ladder = [(512, 8), (384, 8), (256, 8), (256, 4)]
    requested = (int(base_training["sequence_length"]), int(base_training["rank"]))
    ladder = [requested] + [item for item in ladder if item != requested]
    attempts: list[dict[str, Any]] = []
    started = time.monotonic()
    max_seconds = int(config.section("caps")["max_runtime_minutes"]) * 60
    for sequence_length, rank in ladder:
        attempt_cfg = config.with_training(sequence_length=sequence_length, rank=rank, alpha=rank * 2)
        row: dict[str, Any] = {"sequence_length": sequence_length, "rank": rank, "started_utc": utc_now()}
        tokenizer = base = model = optimizer = None
        try:
            seed_everything(int(config.values["seed"]))
            torch.cuda.reset_peak_memory_stats()
            tokenizer, base = load_quantized_base(attempt_cfg)
            before = tokenizer_fingerprint(tokenizer)
            model, adapter = attach_new_adapter(base, attempt_cfg)
            examples = _encoded_training_records(tokenizer, attempt_cfg)
            pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
            collator = AssistantOnlyCollator(pad_id)
            batch = _pad_to_length(collator([examples[0]]), sequence_length, pad_id)
            batch = _to_device(batch)
            optimizer, optimizer_name, optimizer_failures = _optimizer(model, attempt_cfg)
            model.train()
            step_start = time.monotonic()
            output = model(**batch)
            output.loss.backward()
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
            torch.cuda.synchronize()
            row.update({
                "status": "PASS", "loss": float(output.loss.detach().cpu()),
                "wall_seconds": time.monotonic() - step_start,
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                "adapter": adapter, "optimizer": optimizer_name,
                "optimizer_fallback_errors": optimizer_failures,
                "tokenizer_unchanged": before == tokenizer_fingerprint(tokenizer),
            })
            attempts.append(row)
            selected = {
                "sequence_length": sequence_length, "rank": rank, "alpha": rank * 2,
                "gradient_accumulation_steps": int(base_training["gradient_accumulation_steps"]),
                "probe": row,
            }
            write_json(paths.artifacts / "selected_training_config.json", selected)
            result = {"schema_version": 1, "status": "PASS", "attempts": attempts, "selected": selected}
            write_json(paths.artifacts / "memory_probe.json", result)
            _write_probe_markdown(paths.reports / "memory_probe.md", result)
            return result
        except BaseException as exc:
            row.update({"status": "OOM" if _is_oom(exc) else "FAIL", "error": repr(exc)})
            attempts.append(row)
            if not _is_oom(exc):
                result = {"schema_version": 1, "status": "FAIL", "attempts": attempts}
                write_json(paths.artifacts / "memory_probe.json", result)
                _write_probe_markdown(paths.reports / "memory_probe.md", result)
                raise
        finally:
            try:
                del optimizer, model, base, tokenizer
            except UnboundLocalError:
                pass
            cleanup_cuda()
        if time.monotonic() - started >= max_seconds:
            break
    result = {"schema_version": 1, "status": "FAIL", "attempts": attempts, "error": "all all-linear fallback profiles failed"}
    write_json(paths.artifacts / "memory_probe.json", result)
    _write_probe_markdown(paths.reports / "memory_probe.md", result)
    return result


def _write_probe_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = ["# Memory probe", "", f"Status: **{result['status']}**", "", "| Seq | Rank | Status | Peak allocated | Step seconds |", "|---:|---:|---|---:|---:|"]
    for row in result["attempts"]:
        lines.append(f"| {row['sequence_length']} | {row['rank']} | {row['status']} | {row.get('peak_allocated_bytes', '')} | {row.get('wall_seconds', '')} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply_selected_profile(config: ExperimentConfig) -> ExperimentConfig:
    selected_path = layout(config).artifacts / "selected_training_config.json"
    if not selected_path.is_file():
        raise TrainingError("memory probe selection is missing; run memory-probe first")
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    return config.with_training(
        sequence_length=int(selected["sequence_length"]), rank=int(selected["rank"]),
        alpha=int(selected["alpha"]),
        gradient_accumulation_steps=int(selected["gradient_accumulation_steps"]),
    )


def _checkpoint_dirs(run_dir: Path) -> list[Path]:
    valid = []
    for path in run_dir.glob("checkpoints/checkpoint-*"):
        if path.name.endswith(".partial") or not path.is_dir():
            continue
        required = [path / "adapter" / "adapter_config.json", path / "adapter" / "adapter_model.safetensors", path / "trainer_state.json", path / "state.pt"]
        if all(item.is_file() for item in required):
            valid.append(path)
    return sorted(valid, key=lambda item: int(item.name.rsplit("-", 1)[1]))


def latest_checkpoint(run_dir: Path) -> Path | None:
    values = _checkpoint_dirs(run_dir)
    return values[-1] if values else None


def _save_checkpoint(model: Any, optimizer: Any, scheduler: Any, run_dir: Path, state: dict[str, Any], keep: int = 3) -> Path:
    import torch
    checkpoints = run_dir / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    final = checkpoints / f"checkpoint-{state['global_step']:06d}"
    temporary = checkpoints / f"checkpoint-{state['global_step']:06d}.partial"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    model.save_pretrained(temporary / "adapter", safe_serialization=True)
    write_json(temporary / "trainer_state.json", state)
    torch.save({
        "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
        "torch_rng": torch.get_rng_state(),
        "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
        "python_rng": random.getstate(),
    }, temporary / "state.pt")
    if final.exists():
        shutil.rmtree(final)
    os.replace(temporary, final)
    for stale in _checkpoint_dirs(run_dir)[:-keep]:
        shutil.rmtree(stale)
    return final


def _restore_state(checkpoint: Path, optimizer: Any, scheduler: Any) -> dict[str, Any]:
    import torch
    state = json.loads((checkpoint / "trainer_state.json").read_text(encoding="utf-8"))
    payload = torch.load(checkpoint / "state.pt", map_location="cpu", weights_only=False)
    optimizer.load_state_dict(payload["optimizer"])
    scheduler.load_state_dict(payload["scheduler"])
    torch.set_rng_state(payload["torch_rng"])
    if payload.get("cuda_rng") is not None and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(payload["cuda_rng"])
    random.setstate(payload["python_rng"])
    return state


def reconcile_metrics(run_dir: Path, durable_step: int, checkpoint: Path) -> int:
    """Move post-checkpoint metrics from an interrupted process out of the canonical log.

    An optimizer step can complete and be logged before the next atomic checkpoint.
    On resume those steps must be replayed from the durable optimizer/RNG state; keeping
    both copies in the canonical stream would falsely claim one continuous trajectory.
    """
    path = run_dir / "metrics.jsonl"
    if not path.is_file():
        return 0
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    kept = [row for row in rows if int(row["global_step"]) <= durable_step]
    abandoned = [row for row in rows if int(row["global_step"]) > durable_step]
    if not abandoned:
        return 0
    for row in abandoned:
        append_jsonl(run_dir / "metrics_abandoned.jsonl", {
            **row, "abandoned_utc": utc_now(), "resume_checkpoint": str(checkpoint),
            "reason": "optimizer/RNG state was not durably checkpointed",
        })
    atomic_write_text(path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in kept))
    append_jsonl(run_dir / "resume_reconciliation.jsonl", {
        "utc": utc_now(), "durable_step": durable_step,
        "abandoned_metric_rows": len(abandoned), "checkpoint": str(checkpoint),
    })
    return len(abandoned)


def train_smoke(config: ExperimentConfig, *, target_step: int, run_name: str = "smoke-v1") -> dict[str, Any]:
    require_resource_cap()
    import torch

    config = apply_selected_profile(config)
    caps, training = config.section("caps"), config.section("training")
    if not 1 <= target_step <= min(int(caps["max_optimizer_steps"]), int(training["total_steps"])):
        raise TrainingError(f"target step {target_step} violates configured guards")
    paths = layout(config)
    run_dir = paths.runs / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "run_manifest.json"
    manifest = base_manifest(config, sys.argv)
    manifest.update({"run_name": run_name, "target_step_this_process": target_step, "started_utc": utc_now()})
    write_json(manifest_path, manifest)
    write_yaml(run_dir / "config.resolved.yaml", config.resolved_dict())
    train_path = config.path("data_root") / "smoke_train.jsonl"
    eval_path = config.path("data_root") / "smoke_eval.jsonl"
    write_json(run_dir / "dataset_manifest.json", dataset_manifest([train_path, eval_path]))
    environment = subprocess.run([sys.executable, "-m", "pip", "freeze"], text=True, capture_output=True, check=False)
    (run_dir / "environment.txt").write_text(environment.stdout, encoding="utf-8")
    tokenizer = base = model = optimizer = scheduler = None
    started = time.monotonic()
    max_seconds = int(caps["max_runtime_minutes"]) * 60
    resumed_from: str | None = None
    try:
        seed_everything(int(config.values["seed"]))
        torch.cuda.reset_peak_memory_stats()
        tokenizer, base = load_quantized_base(config)
        tokenizer_before = tokenizer_fingerprint(tokenizer)
        checkpoint = latest_checkpoint(run_dir)
        if checkpoint:
            model, adapter_info = load_saved_adapter(base, checkpoint / "adapter", config)
            resumed_from = str(checkpoint)
        else:
            model, adapter_info = attach_new_adapter(base, config)
        optimizer, optimizer_name, optimizer_failures = _optimizer(model, config)
        scheduler = _scheduler(optimizer, config)
        if checkpoint:
            state = _restore_state(checkpoint, optimizer, scheduler)
            reconcile_metrics(run_dir, int(state["global_step"]), checkpoint)
        else:
            state = {"global_step": 0, "micro_step": 0, "tokens_processed": 0, "last_checkpoint_utc": utc_now()}
        if state["global_step"] >= target_step:
            return {"status": "PASS", "global_step": state["global_step"], "no_op": True, "run_dir": str(run_dir)}
        examples = _encoded_training_records(tokenizer, config)
        order = list(range(len(examples)))
        random.Random(int(config.values["seed"])).shuffle(order)
        pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
        collator = AssistantOnlyCollator(pad_id)
        accumulation = int(training["gradient_accumulation_steps"])
        model.train()
        optimizer.zero_grad(set_to_none=True)
        checkpoint_interval = int(caps["checkpoint_steps"])
        checkpoint_seconds = int(caps["checkpoint_minutes"]) * 60
        last_checkpoint_time = time.monotonic()
        while state["global_step"] < target_step:
            if time.monotonic() - started >= max_seconds:
                raise RuntimeLimitExceeded(f"runtime cap reached at optimizer step {state['global_step']}")
            step_started = time.monotonic()
            losses: list[float] = []
            supervised = 0
            for _ in range(accumulation):
                index = order[state["micro_step"] % len(order)]
                batch = _to_device(collator([examples[index]]))
                output = model(**batch)
                (output.loss / accumulation).backward()
                losses.append(float(output.loss.detach().cpu()))
                batch_supervised = int((batch["labels"] != -100).sum().item())
                supervised += batch_supervised
                state["micro_step"] += 1
                state["tokens_processed"] += batch_supervised
            torch.nn.utils.clip_grad_norm_(
                [parameter for parameter in model.parameters() if parameter.requires_grad],
                float(training["max_grad_norm"]),
            )
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)
            torch.cuda.synchronize()
            state["global_step"] += 1
            elapsed = time.monotonic() - step_started
            row = {
                "timestamp_utc": utc_now(), "global_step": state["global_step"],
                "loss": sum(losses) / len(losses), "learning_rate": scheduler.get_last_lr()[0],
                "step_seconds": elapsed, "optimizer_steps_per_second": 1 / elapsed,
                "supervised_tokens": supervised, "tokens_per_second": supervised / elapsed,
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            }
            append_jsonl(run_dir / "metrics.jsonl", row)
            due_step = state["global_step"] % checkpoint_interval == 0
            due_time = time.monotonic() - last_checkpoint_time >= checkpoint_seconds
            if due_step or due_time or state["global_step"] == target_step:
                state["last_checkpoint_utc"] = utc_now()
                saved = _save_checkpoint(model, optimizer, scheduler, run_dir, state)
                last_checkpoint_time = time.monotonic()
                append_jsonl(run_dir / "checkpoint_events.jsonl", {"step": state["global_step"], "path": str(saved), "utc": utc_now()})
        final_adapter = run_dir / "adapter"
        partial = run_dir / "adapter.partial"
        if partial.exists():
            shutil.rmtree(partial)
        model.save_pretrained(partial, safe_serialization=True)
        if final_adapter.exists():
            shutil.rmtree(final_adapter)
        os.replace(partial, final_adapter)
        adapter_file = final_adapter / "adapter_model.safetensors"
        result = {
            "status": "PASS", "global_step": state["global_step"], "resumed_from": resumed_from,
            "resume_observed": resumed_from is not None,
            "wall_seconds_this_process": time.monotonic() - started,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            "adapter": adapter_info, "optimizer": optimizer_name,
            "optimizer_fallback_errors": optimizer_failures,
            "adapter_path": str(final_adapter), "adapter_bytes": adapter_file.stat().st_size,
            "adapter_sha256": sha256_file(adapter_file),
            "tokenizer_unchanged": tokenizer_before == tokenizer_fingerprint(tokenizer),
            "completed_utc": utc_now(), "run_dir": str(run_dir),
        }
        write_json(run_dir / f"process_result_step_{target_step:06d}.json", result)
        write_json(run_dir / "trainer_state.json", state)
        return result
    except BaseException as exc:
        abort = {
            "status": "ABORTED", "error_type": exc.__class__.__name__, "error": repr(exc),
            "target_step": target_step, "elapsed_seconds": time.monotonic() - started,
            "last_checkpoint": str(latest_checkpoint(run_dir)) if latest_checkpoint(run_dir) else None,
            "utc": utc_now(),
        }
        write_json(run_dir / f"abort_step_{target_step:06d}.json", abort)
        raise
    finally:
        try:
            del scheduler, optimizer, model, base, tokenizer
        except UnboundLocalError:
            pass
        cleanup_cuda()
