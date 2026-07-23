"""Capped TinyLoRA/QLoRA training and transfer evaluation."""

from __future__ import annotations

import gc
import json
import math
import os
from pathlib import Path
import random
import shutil
import time
from typing import Any, Sequence

import numpy as np

from pixie_etale_motifs.corpus import build_corpus
from pixie_etale_motifs.io import (
    append_jsonl,
    atomic_json,
    sha256_file,
    utc_now,
)
from pixie_etale_motifs.protocol import load_repo_config, resolve_config_path
from pixie_etale_motifs.safetensors_raw import verify_snapshot

from .authorization import validate_authorization
from .jobs import validate_job
from .protocol import load_protocol, verify


class FeedbackRunError(RuntimeError):
    """A feedback job cannot continue without violating its frozen contract."""


def _seed(torch: Any, value: int) -> None:
    random.seed(value)
    np.random.seed(value)
    os.environ["PYTHONHASHSEED"] = str(value)
    torch.manual_seed(value)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(value)


def _cleanup(torch: Any | None) -> dict[str, Any]:
    receipt: dict[str, Any] = {"status": "PASS", "errors": [], "started_utc": utc_now()}
    gc.collect()
    if torch is not None and torch.cuda.is_available():
        for operation in (torch.cuda.synchronize, torch.cuda.empty_cache, torch.cuda.ipc_collect):
            try:
                operation()
            except Exception as error:
                receipt["errors"].append(f"{operation.__name__}: {type(error).__name__}: {error}")
        receipt["cuda_allocated_bytes"] = int(torch.cuda.memory_allocated())
        receipt["cuda_reserved_bytes"] = int(torch.cuda.memory_reserved())
    if receipt["errors"]:
        receipt["status"] = "CLEANUP_FAILED"
    receipt["ended_utc"] = utc_now()
    return receipt


def _require_gpu_guard(torch: Any, maximum_mib: int) -> None:
    peak = int(torch.cuda.max_memory_reserved() // (1024 * 1024))
    if peak > maximum_mib:
        raise FeedbackRunError(f"peak reserved VRAM {peak} MiB exceeds frozen {maximum_mib} MiB guard")


def _token_ids(value: Any) -> list[int]:
    if isinstance(value, dict):
        value = value.get("input_ids")
    if hasattr(value, "reshape") and hasattr(value, "tolist"):
        return [int(item) for item in value.reshape(-1).tolist()]
    if isinstance(value, list) and value and isinstance(value[0], list):
        value = value[0]
    if not isinstance(value, list):
        raise FeedbackRunError("tokenizer did not return input IDs")
    return [int(item) for item in value]


def _encode_training_row(tokenizer: Any, row: dict[str, Any], maximum_length: int) -> dict[str, list[int]]:
    messages = list(row["messages"])
    target = row.get("expected_completion")
    if target is None:
        raise FeedbackRunError(f"training row {row['id']} lacks an assistant target")
    prompt = _token_ids(tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))
    completed = _token_ids(
        tokenizer.apply_chat_template(
            [*messages, {"role": "assistant", "content": str(target)}],
            tokenize=True,
            add_generation_prompt=False,
        )
    )
    common = 0
    for left, right in zip(prompt, completed):
        if left != right:
            break
        common += 1
    if common <= 0 or common >= len(completed):
        raise FeedbackRunError(f"chat template did not expose assistant span for {row['id']}")
    cut = max(0, len(completed) - maximum_length)
    input_ids = completed[cut:]
    supervised_start = common - cut
    if supervised_start <= 0 or supervised_start >= len(input_ids):
        raise FeedbackRunError(f"sequence limit removed prompt or target for {row['id']}")
    return {
        "input_ids": input_ids,
        "attention_mask": [1] * len(input_ids),
        "labels": [-100] * supervised_start + input_ids[supervised_start:],
    }


def _batch(torch: Any, record: dict[str, list[int]], pad_token_id: int, width: int) -> dict[str, Any]:
    padding = width - len(record["input_ids"])
    if padding < 0:
        raise FeedbackRunError("encoded record exceeds frozen sequence length")
    return {
        "input_ids": torch.tensor([[*record["input_ids"], *([pad_token_id] * padding)]], dtype=torch.long, device="cuda:0"),
        "attention_mask": torch.tensor([[*record["attention_mask"], *([0] * padding)]], dtype=torch.long, device="cuda:0"),
        "labels": torch.tensor([[*record["labels"], *([-100] * padding)]], dtype=torch.long, device="cuda:0"),
    }


def _load_base(
    repo_root: Path,
    experiment_root: Path,
    protocol: dict[str, Any],
    torch: Any,
) -> tuple[Any, Any]:
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    config = load_repo_config(repo_root)
    sharded = resolve_config_path(repo_root, config, "pixie_etale_motif_sharded_model_root")
    motif_root = (experiment_root / protocol["source_experiment"]["path"]).resolve()
    verify_snapshot(
        sharded,
        protocol_sha256=protocol["source_experiment"]["protocol_sha256"],
        source_sha256=protocol["base_model"]["weights_sha256"],
        rehash_shards=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(sharded, local_files_only=True, trust_remote_code=False)
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        sharded,
        local_files_only=True,
        trust_remote_code=False,
        device_map={"": 0},
        quantization_config=quantization,
        dtype=torch.float16,
        attn_implementation="sdpa",
        low_cpu_mem_usage=True,
    )
    model.config.use_cache = False
    del motif_root
    return tokenizer, model


def _training_rows(job: dict[str, Any], protocol: dict[str, Any]) -> list[dict[str, Any]]:
    corpus = build_corpus(root_seed=2026072301)
    by_id = {str(row["id"]): row for row in corpus}
    identifiers = [str(item) for item in job["dataset"]["training_input_ids"]]
    rows = []
    for input_id in identifiers:
        if input_id not in by_id:
            raise FeedbackRunError(f"job names unknown training input {input_id}")
        row = by_id[input_id]
        if row["split"] != protocol["comparison"]["training_split"]:
            raise FeedbackRunError(f"job leaks {row['split']} row {input_id} into training")
        if not row["outcome_eligible"] or row["expected_completion"] is None:
            raise FeedbackRunError(f"job names ineligible training input {input_id}")
        rows.append(row)
    if len(rows) < 2:
        raise FeedbackRunError("feedback training requires at least two discovery inputs")
    return rows


def _checkpoint_dirs(run_root: Path) -> list[Path]:
    result = []
    for path in (run_root / "checkpoints").glob("step-*"):
        if path.name.endswith(".partial"):
            continue
        if (path / "adapter" / "adapter_model.safetensors").is_file() and (path / "state.pt").is_file():
            result.append(path)
    return sorted(result, key=lambda path: int(path.name.split("-", 1)[1]))


def _save_checkpoint(
    torch: Any,
    model: Any,
    optimizer: Any,
    run_root: Path,
    state: dict[str, Any],
    *,
    keep: int,
) -> Path:
    checkpoints = run_root / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    final = checkpoints / f"step-{state['global_step']:06d}"
    temporary = checkpoints / f"step-{state['global_step']:06d}.partial"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    model.save_pretrained(temporary / "adapter", safe_serialization=True)
    torch.save(
        {
            "optimizer": optimizer.state_dict(),
            "state": state,
            "python_rng": random.getstate(),
            "numpy_rng": np.random.get_state(),
            "torch_rng": torch.get_rng_state(),
            "cuda_rng": torch.cuda.get_rng_state_all(),
        },
        temporary / "state.pt",
    )
    if final.exists():
        shutil.rmtree(final)
    os.replace(temporary, final)
    for stale in _checkpoint_dirs(run_root)[:-keep]:
        shutil.rmtree(stale)
    return final


def _attach_or_resume(
    torch: Any,
    base: Any,
    job: dict[str, Any],
    run_root: Path,
) -> tuple[Any, Any, dict[str, Any], Path | None]:
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model, prepare_model_for_kbit_training

    base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True)
    base.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    base.enable_input_require_grads()
    checkpoints = _checkpoint_dirs(run_root)
    resumed = checkpoints[-1] if checkpoints else None
    if resumed:
        model = PeftModel.from_pretrained(base, resumed / "adapter", is_trainable=True)
    else:
        adapter = job["adapter"]
        lora = LoraConfig(
            r=int(adapter["rank"]),
            lora_alpha=int(adapter["alpha"]),
            lora_dropout=float(adapter["dropout"]),
            bias="none",
            target_modules=list(adapter["target_modules"]),
            layers_to_transform=list(adapter["layers_to_transform"]),
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(base, lora)
    trainable_names = [name for name, parameter in model.named_parameters() if parameter.requires_grad]
    if not trainable_names or any("lora_" not in name for name in trainable_names):
        raise FeedbackRunError("feedback job made a non-LoRA parameter trainable")
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=float(job["training"]["learning_rate"]),
        weight_decay=float(job["training"]["weight_decay"]),
    )
    state = {
        "global_step": 0,
        "micro_step": 0,
        "tokens_processed": 0,
        "last_checkpoint_utc": None,
    }
    if resumed:
        payload = torch.load(resumed / "state.pt", map_location="cpu", weights_only=False)
        optimizer.load_state_dict(payload["optimizer"])
        state = payload["state"]
        random.setstate(payload["python_rng"])
        np.random.set_state(payload["numpy_rng"])
        torch.set_rng_state(payload["torch_rng"])
        torch.cuda.set_rng_state_all(payload["cuda_rng"])
    trainable_parameter_count = sum(
        int(parameter.numel())
        for parameter in model.parameters()
        if parameter.requires_grad
    )
    previous_parameter_count = state.get("trainable_parameter_count")
    if previous_parameter_count is not None and int(previous_parameter_count) != trainable_parameter_count:
        raise FeedbackRunError("resumed adapter trainable-parameter count differs from its checkpoint")
    state["trainable_parameter_count"] = trainable_parameter_count
    return model, optimizer, state, resumed


def train_feedback_job(
    repo_root: Path,
    experiment_root: Path,
    job_path: Path,
    authorization_path: Path,
) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    job = validate_job(json.loads(job_path.read_text(encoding="utf-8")))
    if job["job_type"] != "TRAIN_ADAPTER" or job["status"] != "PROPOSED":
        raise FeedbackRunError("train requires an executable proposed training job")
    authorization = validate_authorization(
        authorization_path,
        experiment_root,
        protocol,
        job,
        require_active_wrapper=True,
    )
    frozen = verify(repo_root, experiment_root, require_model_weights=True)
    if not frozen["ok"]:
        raise FeedbackRunError(f"frozen feedback inputs failed: {frozen['checks']}")
    config = load_repo_config(repo_root)
    output_root = resolve_config_path(repo_root, config, "pixie_lora_feedback_output_root")
    run_root = output_root / "runs" / authorization.run_id / job["job_id"]
    run_root.mkdir(parents=True, exist_ok=True)
    events = run_root / "events.jsonl"
    append_jsonl(events, {"event": "training_started", "utc": utc_now(), "job_id": job["job_id"]})
    os.environ.update({
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "WANDB_DISABLED": "true",
        "TOKENIZERS_PARALLELISM": "false",
    })
    started = time.monotonic()
    torch = tokenizer = base = model = optimizer = records = batches = None
    failure: BaseException | None = None
    summary: dict[str, Any] | None = None
    try:
        import torch as torch_module

        torch = torch_module
        if not torch.cuda.is_available():
            raise FeedbackRunError("CUDA is unavailable inside capped feedback training")
        _seed(torch, int(job["training"]["seed"]))
        torch.cuda.reset_peak_memory_stats()
        tokenizer, base = _load_base(repo_root, experiment_root, protocol, torch)
        rows = _training_rows(job, protocol)
        records = [
            _encode_training_row(tokenizer, row, int(job["training"]["sequence_length"]))
            for row in rows
        ]
        pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
        batches = [
            _batch(torch, record, int(pad_id), int(job["training"]["sequence_length"]))
            for record in records
        ]
        model, optimizer, state, resumed = _attach_or_resume(torch, base, job, run_root)
        model.train()
        optimizer.zero_grad(set_to_none=True)
        order = list(range(len(batches)))
        random.Random(int(job["training"]["seed"])).shuffle(order)
        target_steps = int(job["training"]["optimizer_steps"])
        accumulation = int(job["training"]["gradient_accumulation_steps"])
        checkpoint_steps = int(job["training"]["checkpoint_steps"])
        checkpoint_seconds = int(job["training"]["checkpoint_seconds"])
        last_checkpoint = time.monotonic()
        while int(state["global_step"]) < target_steps:
            if time.monotonic() - started >= int(job["resources"]["timeout_seconds"]) - 30:
                raise FeedbackRunError("trainer stopped before wrapper timeout")
            losses = []
            supervised = 0
            step_started = time.monotonic()
            for _ in range(accumulation):
                batch = batches[order[int(state["micro_step"]) % len(order)]]
                output = model(**batch)
                (output.loss / accumulation).backward()
                losses.append(float(output.loss.detach().cpu()))
                batch_supervised = int((batch["labels"] != -100).sum().item())
                supervised += batch_supervised
                state["micro_step"] = int(state["micro_step"]) + 1
                state["tokens_processed"] = int(state["tokens_processed"]) + batch_supervised
            torch.nn.utils.clip_grad_norm_(
                [parameter for parameter in model.parameters() if parameter.requires_grad],
                float(job["training"]["max_grad_norm"]),
            )
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
            torch.cuda.synchronize()
            state["global_step"] = int(state["global_step"]) + 1
            _require_gpu_guard(torch, int(job["gpu_guard"]["maximum_peak_memory_mib"]))
            elapsed = time.monotonic() - step_started
            append_jsonl(
                run_root / "metrics.jsonl",
                {
                    "utc": utc_now(),
                    "global_step": state["global_step"],
                    "loss": float(np.mean(losses)),
                    "step_seconds": elapsed,
                    "supervised_tokens": supervised,
                    "peak_vram_mib": int(torch.cuda.max_memory_reserved() // (1024 * 1024)),
                },
            )
            due = (
                int(state["global_step"]) % checkpoint_steps == 0
                or time.monotonic() - last_checkpoint >= checkpoint_seconds
                or int(state["global_step"]) == target_steps
            )
            if due:
                state["last_checkpoint_utc"] = utc_now()
                checkpoint = _save_checkpoint(
                    torch,
                    model,
                    optimizer,
                    run_root,
                    state,
                    keep=int(job["training"]["maximum_checkpoints"]),
                )
                last_checkpoint = time.monotonic()
                append_jsonl(events, {"event": "checkpoint", "utc": utc_now(), "step": state["global_step"], "path": str(checkpoint)})
        final = run_root / "adapter"
        temporary = run_root / "adapter.partial"
        if temporary.exists():
            shutil.rmtree(temporary)
        model.save_pretrained(temporary, safe_serialization=True)
        if final.exists():
            shutil.rmtree(final)
        os.replace(temporary, final)
        adapter_file = final / "adapter_model.safetensors"
        summary = {
            "schema": "pixieology_lora_feedback_training_result_v1",
            "status": "COMPLETE",
            "job_id": job["job_id"],
            "job_sha256": job["authorization"]["job_sha256"],
            "run_id": authorization.run_id,
            "attempt_id": authorization.attempt_id,
            "global_step": state["global_step"],
            "steps_completed": state["global_step"],
            "tokens_processed": state["tokens_processed"],
            "trainable_parameter_count": state["trainable_parameter_count"],
            "resumed_from": None if resumed is None else str(resumed),
            "adapter_path": str(final),
            "adapter_sha256": sha256_file(adapter_file),
            "peak_vram_mib": int(torch.cuda.max_memory_reserved() // (1024 * 1024)),
            "wall_seconds": time.monotonic() - started,
            "next_required_jobs": ["transfer_evaluation", "candidate_activation_topology_capture"],
        }
    except BaseException as error:
        failure = error
    finally:
        batches = records = optimizer = model = base = tokenizer = None
        cleanup = _cleanup(torch)
    if failure is not None:
        abort = {
            "schema": "pixieology_lora_feedback_abort_v1",
            "status": "ABORTED",
            "job_id": job["job_id"],
            "error_type": type(failure).__name__,
            "error": str(failure),
            "steps_completed": 0,
            "wall_seconds": time.monotonic() - started,
            "cleanup": cleanup,
            "utc": utc_now(),
        }
        metrics = run_root / "metrics.jsonl"
        if metrics.is_file():
            abort["steps_completed"] = len([line for line in metrics.read_text(encoding="utf-8").splitlines() if line.strip()])
        atomic_json(run_root / "abort.json", abort)
        append_jsonl(events, {"event": "training_aborted", "utc": utc_now(), "error_type": type(failure).__name__})
        raise FeedbackRunError(f"feedback training aborted with receipt {run_root / 'abort.json'}") from failure
    assert summary is not None
    summary["cleanup"] = cleanup
    if cleanup["status"] != "PASS":
        summary["status"] = "CLEANUP_FAILED"
    atomic_json(run_root / "training_result.json", summary)
    append_jsonl(events, {"event": "training_complete", "utc": utc_now(), "status": summary["status"]})
    if summary["status"] != "COMPLETE":
        raise FeedbackRunError("training completed but cleanup failed")
    return summary


def _mean_log_likelihood(torch: Any, logits: Any, labels: Any) -> float:
    shifted = labels[:, 1:]
    mask = shifted.ne(-100)
    log_probabilities = torch.nn.functional.log_softmax(logits[:, :-1, :].float(), dim=-1)
    safe = shifted.masked_fill(~mask, 0)
    selected = log_probabilities.gather(-1, safe.unsqueeze(-1)).squeeze(-1)
    return float(selected[mask].mean().item())


def evaluate_feedback_job(
    repo_root: Path,
    experiment_root: Path,
    job_path: Path,
    authorization_path: Path,
    *,
    adapter_path: Path | None = None,
) -> dict[str, Any]:
    protocol = load_protocol(experiment_root)
    job = validate_job(json.loads(job_path.read_text(encoding="utf-8")))
    authorization = validate_authorization(
        authorization_path,
        experiment_root,
        protocol,
        job,
        require_active_wrapper=True,
    )
    frozen = verify(repo_root, experiment_root, require_model_weights=True)
    if not frozen["ok"]:
        raise FeedbackRunError(f"frozen feedback inputs failed: {frozen['checks']}")
    if job["method"] in {"tinylora", "qlora"} and adapter_path is None:
        raise FeedbackRunError("candidate evaluation requires its completed adapter path")
    config = load_repo_config(repo_root)
    output_root = resolve_config_path(repo_root, config, "pixie_lora_feedback_output_root")
    run_root = output_root / "runs" / authorization.run_id / job["job_id"] / "evaluation"
    run_root.mkdir(parents=True, exist_ok=True)
    results_path = run_root / "rows.jsonl"
    completed = {}
    if results_path.is_file():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                completed[str(value["input_id"])] = value
    torch = tokenizer = base = model = None
    failure: BaseException | None = None
    summary: dict[str, Any] | None = None
    started = time.monotonic()
    try:
        import torch as torch_module
        from peft import PeftModel

        torch = torch_module
        if not torch.cuda.is_available():
            raise FeedbackRunError("CUDA is unavailable inside capped feedback evaluation")
        _seed(torch, int(protocol["seeds"]["training"]))
        torch.cuda.reset_peak_memory_stats()
        tokenizer, base = _load_base(repo_root, experiment_root, protocol, torch)
        if job["method"] == "pixie_rank8":
            model = PeftModel.from_pretrained(base, Path(frozen["adapter_root"]), adapter_name="pixie", is_trainable=False)
        elif job["method"] in {"tinylora", "qlora"}:
            model = PeftModel.from_pretrained(base, adapter_path, adapter_name="candidate", is_trainable=False)
        else:
            model = base
        model.eval()
        adapter_parameter_count = sum(
            int(parameter.numel())
            for name, parameter in model.named_parameters()
            if "lora_" in name
        )
        rows = [
            row for row in build_corpus(root_seed=2026072301)
            if row["split"] == "transfer" and row["outcome_eligible"] and row["expected_completion"] is not None
        ]
        for row in rows:
            if row["id"] in completed:
                continue
            record = _encode_training_row(tokenizer, row, 256)
            pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
            batch = _batch(torch, record, int(pad_id), 256)
            with torch.inference_mode():
                output = model(**batch)
                prompt_ids = _token_ids(
                    tokenizer.apply_chat_template(
                        row["messages"],
                        tokenize=True,
                        add_generation_prompt=True,
                    )
                )[-256:]
                prompt = torch.tensor([prompt_ids], dtype=torch.long, device="cuda:0")
                generated = model.generate(
                    input_ids=prompt,
                    attention_mask=torch.ones_like(prompt),
                    max_new_tokens=min(
                        32,
                        max(8, len(tokenizer.encode(str(row["expected_completion"]), add_special_tokens=False)) + 4),
                    ),
                    do_sample=False,
                    pad_token_id=int(pad_id),
                    use_cache=True,
                )
            generated_text = tokenizer.decode(generated[0, len(prompt_ids):], skip_special_tokens=True).strip()
            expected_text = str(row["expected_completion"]).strip()
            receipt = {
                "schema": "pixieology_lora_feedback_eval_row_v1",
                "job_id": job["job_id"],
                "condition": job["method"],
                "input_id": row["id"],
                "semantic_group_id": row["semantic_group_id"],
                "family": row["family"],
                "variant": row["variant"],
                "split": row["split"],
                "mean_log_likelihood": _mean_log_likelihood(torch, output.logits, batch["labels"]),
                "expected_completion": row["expected_completion"],
                "generated_text": generated_text,
                "exact_match": generated_text == expected_text,
            }
            append_jsonl(results_path, receipt)
            completed[row["id"]] = receipt
            del batch, output, prompt, generated
            _require_gpu_guard(torch, int(job["gpu_guard"]["maximum_peak_memory_mib"]))
        values = list(completed.values())
        summary = {
            "schema": "pixieology_lora_feedback_evaluation_v1",
            "status": "COMPLETE",
            "job_id": job["job_id"],
            "job_sha256": job["authorization"]["job_sha256"],
            "condition": job["method"],
            "adapter_parameter_count": adapter_parameter_count,
            "row_count": len(values),
            "evaluation_split": "transfer",
            "mean_log_likelihood": float(np.mean([row["mean_log_likelihood"] for row in values])),
            "exact_match_accuracy": float(np.mean([row["exact_match"] for row in values])),
            "family_mean_log_likelihood": {
                family: float(np.mean([row["mean_log_likelihood"] for row in values if row["family"] == family]))
                for family in sorted({row["family"] for row in values})
            },
            "family_exact_match_accuracy": {
                family: float(np.mean([row["exact_match"] for row in values if row["family"] == family]))
                for family in sorted({row["family"] for row in values})
            },
            "artifact": str(results_path),
            "artifact_sha256": sha256_file(results_path),
            "peak_vram_mib": int(torch.cuda.max_memory_reserved() // (1024 * 1024)),
            "wall_seconds": time.monotonic() - started,
        }
    except BaseException as error:
        failure = error
    finally:
        model = base = tokenizer = None
        cleanup = _cleanup(torch)
    if failure is not None:
        abort = {
            "schema": "pixieology_lora_feedback_abort_v1",
            "status": "ABORTED",
            "job_id": job["job_id"],
            "error_type": type(failure).__name__,
            "error": str(failure),
            "steps_completed": 0,
            "wall_seconds": time.monotonic() - started,
            "cleanup": cleanup,
            "utc": utc_now(),
        }
        atomic_json(run_root / "abort.json", abort)
        raise FeedbackRunError(f"feedback evaluation aborted with receipt {run_root / 'abort.json'}") from failure
    assert summary is not None
    summary["cleanup"] = cleanup
    if cleanup["status"] != "PASS":
        summary["status"] = "CLEANUP_FAILED"
    atomic_json(run_root / "evaluation.json", summary)
    if summary["status"] != "COMPLETE":
        raise FeedbackRunError("evaluation completed but cleanup failed")
    return summary
