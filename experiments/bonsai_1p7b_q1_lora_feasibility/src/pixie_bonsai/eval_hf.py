"""Four-bit Hugging Face base-versus-PEFT adapter evaluation."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .config import ExperimentConfig
from .data import load_jsonl
from .reporting import layout, utc_now, write_json
from .train import cleanup_cuda, load_quantized_base, require_resource_cap, tokenizer_fingerprint


class EvaluationError(RuntimeError):
    """The adapter or deterministic evaluation surface is unavailable."""


def normalize_visible(text: str) -> str:
    value = text.strip()
    if "</think>" in value:
        value = value.split("</think>", 1)[1].strip()
    return value


def _generate(model: Any, tokenizer: Any, messages: list[dict[str, str]], config: ExperimentConfig) -> tuple[str, float]:
    import torch
    input_ids = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors="pt",
    )
    if isinstance(input_ids, Mapping):
        input_ids = input_ids["input_ids"]
    input_ids = input_ids.to("cuda:0")
    attention_mask = torch.ones_like(input_ids)
    started = time.monotonic()
    with torch.inference_mode():
        generated = model.generate(
            input_ids=input_ids, attention_mask=attention_mask,
            do_sample=False, max_new_tokens=int(config.section("evaluation")["max_new_tokens"]),
            pad_token_id=tokenizer.eos_token_id, eos_token_id=tokenizer.eos_token_id,
            use_cache=True,
        )
    torch.cuda.synchronize()
    new_tokens = generated[0, input_ids.shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True), time.monotonic() - started


def score_rows(rows: list[dict[str, Any]], config: ExperimentConfig) -> dict[str, Any]:
    evaluation = config.section("evaluation")
    canary_rows = [row for row in rows if row["kind"] == "canary"]
    style_rows = [row for row in rows if row["kind"] == "style"]
    canary_hits = sum(row["normalized"] == evaluation["canary"] for row in canary_rows)
    marker_hits = sum(evaluation["style_marker"].lower() in row["normalized"].lower() for row in style_rows)
    malformed = sum(not row["normalized"] or len(row["normalized"]) > 1000 for row in rows)
    return {
        "canary_hits": canary_hits, "canary_total": len(canary_rows),
        "marker_hits": marker_hits, "marker_total": len(style_rows),
        "malformed_outputs": malformed,
        "mean_output_characters": sum(len(row["normalized"]) for row in rows) / len(rows),
        "generation_seconds": sum(row["generation_seconds"] for row in rows),
    }


def evaluate_hf(config: ExperimentConfig, run_name: str = "smoke-v1") -> dict[str, Any]:
    require_resource_cap()
    import torch
    from peft import PeftModel

    paths = layout(config)
    run_dir = paths.runs / run_name
    adapter = run_dir / "adapter"
    if not adapter.is_dir():
        raise EvaluationError(f"trained PEFT adapter missing: {adapter}")
    records = load_jsonl(config.path("data_root") / "smoke_eval.jsonl")
    tokenizer = model = None
    try:
        torch.cuda.reset_peak_memory_stats()
        tokenizer, model = load_quantized_base(config)
        before = tokenizer_fingerprint(tokenizer)
        model.eval()
        modes: dict[str, Any] = {}
        base_rows = []
        for record in records:
            generation, seconds = _generate(model, tokenizer, record.prompt_messages, config)
            base_rows.append({
                "id": record.record_id, "kind": record.kind, "expected": record.expected,
                "generation": generation, "normalized": normalize_visible(generation),
                "generation_seconds": seconds,
            })
        modes["A_hf_base"] = {"rows": base_rows, "scores": score_rows(base_rows, config)}
        (run_dir / "A_hf_base.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in base_rows), encoding="utf-8"
        )
        model = PeftModel.from_pretrained(model, adapter, is_trainable=False)
        model.eval()
        adapter_rows = []
        for record in records:
            generation, seconds = _generate(model, tokenizer, record.prompt_messages, config)
            adapter_rows.append({
                "id": record.record_id, "kind": record.kind, "expected": record.expected,
                "generation": generation, "normalized": normalize_visible(generation),
                "generation_seconds": seconds,
            })
        modes["B_hf_adapter"] = {"rows": adapter_rows, "scores": score_rows(adapter_rows, config)}
        (run_dir / "B_hf_adapter.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in adapter_rows), encoding="utf-8"
        )
        base_score, adapted_score = modes["A_hf_base"]["scores"], modes["B_hf_adapter"]["scores"]
        evaluation = config.section("evaluation")
        changed = (
            adapted_score["canary_hits"] >= int(evaluation["min_canary_hits"])
            and adapted_score["marker_hits"] >= int(evaluation["min_marker_hits"])
            and adapted_score["canary_hits"] - base_score["canary_hits"] >= int(evaluation["min_improvement"])
            and adapted_score["marker_hits"] - base_score["marker_hits"] >= int(evaluation["min_improvement"])
        )
        result = {
            "schema_version": 1, "created_utc": utc_now(), "status": "PASS" if changed else "FAIL",
            "adapter_changes_behavior": changed, "modes": modes,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            "tokenizer_unchanged": before == tokenizer_fingerprint(tokenizer),
            "offline": os.environ.get("HF_HUB_OFFLINE") == "1",
        }
        write_json(run_dir / "hf_evaluation.json", result)
        _write_markdown(run_dir / "hf_evaluation.md", result)
        return result
    finally:
        try:
            del model, tokenizer
        except UnboundLocalError:
            pass
        cleanup_cuda()


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Hugging Face adapter evaluation", "", f"Status: **{result['status']}**", "",
        "| Mode | Canary exact | Pixie marker | Malformed |", "|---|---:|---:|---:|",
    ]
    for mode, value in result["modes"].items():
        score = value["scores"]
        lines.append(f"| {mode} | {score['canary_hits']}/{score['canary_total']} | {score['marker_hits']}/{score['marker_total']} | {score['malformed_outputs']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def offline_evaluation(config: ExperimentConfig, run_name: str = "smoke-v1") -> dict[str, Any]:
    """Replay both runtimes with network-backed model lookup disabled.

    ``status`` describes whether the cached/offline execution path worked. The
    fixed behavioral thresholds remain available separately in
    ``behavioral_gate_status`` and in each nested evaluation. Keeping those
    concepts separate prevents a weak adapter from being misreported as a cache
    or portability failure.
    """
    require_resource_cap()
    old = {name: os.environ.get(name) for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    paths = layout(config)
    try:
        hf = evaluate_hf(config, run_name)
        from .eval_gguf import evaluate_q1
        q1 = evaluate_q1(config, run_name)
        q1_modes = q1.get("modes", {})
        q1_base = q1_modes.get("C_q1_base", {})
        q1_adapter = q1_modes.get("D_q1_adapter", {})
        offline_access_confirmed = bool(hf.get("offline")) and bool(q1_base.get("rows")) and bool(
            q1_adapter.get("rows")
        ) and bool(q1_adapter.get("adapter_load_confirmed"))
        result = {
            "schema_version": 1,
            "status": "PASS" if offline_access_confirmed else "FAIL",
            "created_utc": utc_now(),
            "offline_access_confirmed": offline_access_confirmed,
            "behavioral_gate_status": "PASS" if hf["status"] == "PASS" and q1["status"] == "PASS" else "FAIL",
            "hf": hf,
            "q1": q1,
        }
        write_json(paths.runs / run_name / "offline_evaluation.json", result)
        return result
    finally:
        for name, value in old.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
