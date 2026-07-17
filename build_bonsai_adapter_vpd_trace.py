#!/usr/bin/env python3
"""Build a bounded five-channel manifold from an actual PEFT LoRA adapter.

This model-free parameter analysis measures effective LoRA deltas (B @ A), one
transformer layer at a time. It is not an activation decomposition or NLI-style
semantic analysis, and it cannot establish personality or causal semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

# The base model is never loaded. These settings also keep numerical libraries
# CPU-only and single-threaded inside the outer Windows Job Object cap.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np
from safetensors import safe_open


TRACE_SCHEMA = "pixieology_manifold_trace_v1"
RUN_SCHEMA = "pixieology_bonsai_adapter_vpd_run_v1"
CHECKPOINT_SCHEMA = "pixieology_bonsai_adapter_vpd_checkpoint_v1"
DEFAULT_RUN_ID = "bonsai-1p7b-adapter-vpd-globe-v1"
LAYER_RE = re.compile(r"\.layers\.(\d+)\.")
MODULE_RE = re.compile(r"\.([^.]+)\.lora_A\.weight$")
GROUP_MODULES = {
    "qkv_delta_energy": frozenset({"q_proj", "k_proj", "v_proj"}),
    "attention_output_delta_energy": frozenset({"o_proj"}),
    "mlp_expansion_delta_energy": frozenset({"gate_proj", "up_proj"}),
    "mlp_contraction_delta_energy": frozenset({"down_proj"}),
}
AXES = (
    ("qkv_delta_energy", "QKV delta energy", "effective-delta Frobenius norm"),
    ("attention_output_delta_energy", "Attention output energy", "effective-delta Frobenius norm"),
    ("mlp_expansion_delta_energy", "MLP expansion energy", "effective-delta Frobenius norm"),
    ("mlp_contraction_delta_energy", "MLP contraction energy", "effective-delta Frobenius norm"),
    ("spectral_focus", "Spectral focus", "top-mode energy share"),
)


@dataclass(frozen=True)
class AdapterLayout:
    layers: tuple[int, ...]
    layer_keys: Mapping[int, tuple[str, ...]]
    modules: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def atomic_json(path: Path, payload: Any) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def append_event(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(payload), sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != "pixieology_config_v1" or not isinstance(config.get("paths"), dict):
        raise ValueError(f"invalid Pixieology config: {path}")
    return config


def resolve_config_path(config_path: Path, config: Mapping[str, Any], key: str) -> Path:
    paths = config["paths"]
    if key not in paths:
        raise KeyError(f"missing config path: paths.{key}")
    value = str(paths[key])
    for _ in range(16):
        names = re.findall(r"\$\{([^}]+)\}", value)
        if not names:
            break
        for name in names:
            if name not in paths:
                raise KeyError(f"paths.{key} references missing paths.{name}")
            value = value.replace(f"${{{name}}}", str(paths[name]))
    else:
        raise ValueError(f"too many substitutions in paths.{key}")
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (config_path.parent / candidate).resolve()


def discover_layout(keys: Iterable[str]) -> AdapterLayout:
    layer_keys: dict[int, list[str]] = {}
    modules: set[str] = set()
    for key in keys:
        if not key.endswith(".lora_A.weight"):
            continue
        layer_match = LAYER_RE.search(key)
        module_match = MODULE_RE.search(key)
        if not layer_match or not module_match:
            raise ValueError(f"unsupported LoRA tensor name: {key}")
        layer = int(layer_match.group(1))
        layer_keys.setdefault(layer, []).append(key)
        modules.add(module_match.group(1))
    if not layer_keys:
        raise ValueError("adapter has no transformer-layer lora_A tensors")
    return AdapterLayout(
        layers=tuple(sorted(layer_keys)),
        layer_keys={layer: tuple(sorted(names)) for layer, names in layer_keys.items()},
        modules=tuple(sorted(modules)),
    )


def low_rank_singular_values(a: np.ndarray, b: np.ndarray, scale: float) -> np.ndarray:
    """Return nonzero singular values of ``scale * (B @ A)`` via a rank-size core."""
    a32 = np.asarray(a, dtype=np.float32)
    b32 = np.asarray(b, dtype=np.float32)
    if a32.ndim != 2 or b32.ndim != 2 or a32.shape[0] != b32.shape[1]:
        raise ValueError(f"incompatible LoRA factors: A{a32.shape}, B{b32.shape}")
    _, r_a = np.linalg.qr(a32.T, mode="reduced")
    _, r_b = np.linalg.qr(b32, mode="reduced")
    return np.linalg.svd(r_b @ r_a.T, compute_uv=False).astype(np.float64) * abs(float(scale))


def layer_axis_values(module_metrics: Mapping[str, Mapping[str, Any]]) -> list[float]:
    energies = {group: 0.0 for group in GROUP_MODULES}
    total_squared = 0.0
    top_squared = 0.0
    for module, metrics in module_metrics.items():
        energy = float(metrics["frobenius"])
        singular_values = [float(value) for value in metrics["singular_values"]]
        squared = energy * energy
        total_squared += squared
        if singular_values:
            top_squared += singular_values[0] ** 2
        for group, members in GROUP_MODULES.items():
            if module in members:
                energies[group] += squared
                break
        else:
            raise ValueError(f"LoRA module is not assigned to a channel: {module}")
    values = [math.sqrt(energies[axis_id]) for axis_id, _, _ in AXES[:-1]]
    values.append(top_squared / total_squared if total_squared else 0.0)
    return values


def normalize_columns(rows: list[list[float]]) -> tuple[list[list[float]], list[tuple[float, float]]]:
    if not rows or any(len(row) != len(AXES) for row in rows):
        raise ValueError("rows must contain five-channel values")
    columns = list(zip(*rows, strict=True))
    ranges = [(min(column), max(column)) for column in columns]
    normalized = [
        [0.5 if high == low else (float(value) - low) / (high - low)
         for value, (low, high) in zip(row, ranges, strict=True)]
        for row in rows
    ]
    return normalized, ranges


def build_trace(
    *, layer_results: Mapping[str, Mapping[str, Any]], model_id: str,
    adapter_sha256: str, config_sha256: str, rank: int, alpha: float,
    target_modules: Iterable[str],
) -> dict[str, Any]:
    ordered = sorted(((int(layer), result) for layer, result in layer_results.items()), key=lambda item: item[0])
    raw_rows = [list(map(float, result["axes_raw"])) for _, result in ordered]
    normalized, ranges = normalize_columns(raw_rows)
    axes = [{
        "id": axis_id, "label": label, "unit": "min-max normalized within trace",
        "raw_unit": raw_unit, "raw_range": [low, high],
    } for (axis_id, label, raw_unit), (low, high) in zip(AXES, ranges, strict=True)]
    frames = [{
        "t": layer,
        "label": f"Layer {layer}",
        "values": values,
        "raw": raw,
        "metadata": {"layer": layer, "module_count": len(result["modules"]), "method": "rank_core_svd"},
    } for (layer, result), raw, values in zip(ordered, raw_rows, normalized, strict=True)]
    return {
        "schema": TRACE_SCHEMA,
        "id": "bonsai-1p7b-lora-delta-depth-trace-v1",
        "title": "Bonsai 1.7B LoRA delta geometry",
        "semantics": "mechanistic_normalized",
        "alignment": {
            "status": "uncalibrated",
            "note": "Actual trained Bonsai adapter parameter measurements. These five mechanical channels are not certified Wonder, Play, Care, Resolve, or Reflection directions.",
        },
        "axes": axes,
        "source": {
            "evidence_class": "actual_bonsai_1p7b_lora_delta_decomposition",
            "model_id": model_id,
            "adapter_sha256": adapter_sha256,
            "adapter_config_sha256": config_sha256,
            "method": "rank_core_svd_of_effective_lora_delta",
            "base_model_loaded": False,
            "activation_analysis": False,
            "lora_rank": rank,
            "lora_alpha": alpha,
            "target_modules": sorted(target_modules),
        },
        "time": {"unit": "transformer layer"},
        "frames": frames,
    }


def render_javascript(trace: Mapping[str, Any]) -> str:
    payload = json.dumps(trace, indent=2, sort_keys=True, allow_nan=False)
    return (
        "(function (root, factory) {\n"
        "  const value = factory();\n"
        "  if (typeof module === \"object\" && module.exports) module.exports = value;\n"
        "  root.GodelBonsaiVpdTraceData = value;\n"
        "})(typeof globalThis !== \"undefined\" ? globalThis : this, function () {\n"
        f"  return Object.freeze({payload});\n"
        "});\n"
    )


def analyze_adapter(
    *, adapter_dir: Path, run_dir: Path, output_path: Path, run_id: str,
    max_layers: int | None = None,
) -> dict[str, Any]:
    if os.environ.get("PIXIE_RESOURCE_CAP_ACTIVE") != "1":
        raise RuntimeError("refusing uncapped run: use scripts/run_capped.ps1 (PIXIE_RESOURCE_CAP_ACTIVE=1)")
    adapter_path = adapter_dir / "adapter_model.safetensors"
    adapter_config_path = adapter_dir / "adapter_config.json"
    if not adapter_path.is_file() or not adapter_config_path.is_file():
        raise FileNotFoundError(f"incomplete PEFT adapter directory: {adapter_dir}")
    adapter_sha = sha256_file(adapter_path)
    config_sha = sha256_file(adapter_config_path)
    adapter_config = json.loads(adapter_config_path.read_text(encoding="utf-8"))
    if adapter_config.get("rank_pattern") or adapter_config.get("alpha_pattern"):
        raise ValueError("per-module rank/alpha patterns are not supported by this bounded extractor")
    rank = int(adapter_config["r"])
    alpha = float(adapter_config["lora_alpha"])
    scale = alpha / (math.sqrt(rank) if adapter_config.get("use_rslora") else rank)
    run_dir.mkdir(parents=True, exist_ok=True)
    event_path = run_dir / "events.jsonl"
    checkpoint_path = run_dir / "checkpoint.json"
    source = {"adapter_sha256": adapter_sha, "adapter_config_sha256": config_sha}
    checkpoint: dict[str, Any] = {
        "schema": CHECKPOINT_SCHEMA, "run_id": run_id, "source": source,
        "completed_layers": [], "layer_results": {},
    }
    if checkpoint_path.exists():
        loaded = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if loaded.get("schema") != CHECKPOINT_SCHEMA or loaded.get("source") != source:
            raise ValueError("checkpoint does not match this adapter; refusing unsafe resume")
        checkpoint = loaded
    started = time.monotonic()
    append_event(event_path, {"event": "run_started", "run_id": run_id, "at": utc_now(), **source})
    with safe_open(adapter_path, framework="numpy", device="cpu") as tensors:
        keys = list(tensors.keys())
        forbidden = [key for key in keys if "embed" in key.lower() or "lm_head" in key.lower()]
        if forbidden:
            raise ValueError(f"adapter unexpectedly contains forbidden tensors: {forbidden[:3]}")
        layout = discover_layout(keys)
        expected = set(adapter_config.get("target_modules") or [])
        if expected != set(layout.modules):
            raise ValueError(f"adapter module mismatch: config={sorted(expected)}, tensors={list(layout.modules)}")
        selected_layers = layout.layers[:max_layers] if max_layers else layout.layers
        if len(selected_layers) < 2:
            raise ValueError("trace requires at least two transformer layers")
        completed = {int(layer) for layer in checkpoint["completed_layers"]}
        for layer in selected_layers:
            if layer in completed:
                continue
            layer_started = time.monotonic()
            module_metrics: dict[str, dict[str, Any]] = {}
            for a_key in layout.layer_keys[layer]:
                match = MODULE_RE.search(a_key)
                assert match is not None
                module = match.group(1)
                b_key = a_key.replace(".lora_A.weight", ".lora_B.weight")
                if b_key not in keys:
                    raise ValueError(f"missing paired LoRA tensor: {b_key}")
                singular = low_rank_singular_values(tensors.get_tensor(a_key), tensors.get_tensor(b_key), scale)
                module_metrics[module] = {
                    "a_shape": list(tensors.get_slice(a_key).get_shape()),
                    "b_shape": list(tensors.get_slice(b_key).get_shape()),
                    "frobenius": float(np.linalg.norm(singular)),
                    "spectral_focus": float(singular[0] ** 2 / np.sum(singular ** 2)) if np.any(singular) else 0.0,
                    "singular_values": singular.tolist(),
                }
            result = {
                "layer": layer,
                "elapsed_seconds": time.monotonic() - layer_started,
                "axes_raw": layer_axis_values(module_metrics),
                "modules": module_metrics,
            }
            checkpoint["layer_results"][str(layer)] = result
            completed.add(layer)
            checkpoint["completed_layers"] = sorted(completed)
            checkpoint["updated_at"] = utc_now()
            atomic_json(checkpoint_path, checkpoint)
            append_event(event_path, {
                "event": "layer_completed", "run_id": run_id, "layer": layer,
                "at": utc_now(), "elapsed_seconds": result["elapsed_seconds"],
                "checkpoint": str(checkpoint_path),
            })
    selected_results = {str(layer): checkpoint["layer_results"][str(layer)] for layer in selected_layers}
    trace = build_trace(
        layer_results=selected_results,
        model_id=str(adapter_config.get("base_model_name_or_path") or "unknown"),
        adapter_sha256=adapter_sha, config_sha256=config_sha, rank=rank, alpha=alpha,
        target_modules=layout.modules,
    )
    analysis = {
        "schema": RUN_SCHEMA, "run_id": run_id,
        "method": "rank_core_svd_of_effective_lora_delta",
        "limitations": [
            "Parameter-space LoRA delta decomposition; the base model and activations were not loaded.",
            "Axes are mechanical and min-max normalized within this adapter, not calibrated character traits.",
            "Depth is transformer-layer order, not wall-clock time or causal intervention order.",
        ],
        "source": source,
        "adapter_config": {
            "base_model_name_or_path": adapter_config.get("base_model_name_or_path"),
            "r": rank, "lora_alpha": alpha, "scale": scale, "target_modules": list(layout.modules),
        },
        "layer_results": selected_results,
        "trace": trace,
    }
    analysis_path = run_dir / "analysis.json"
    atomic_json(analysis_path, analysis)
    atomic_text(output_path, render_javascript(trace))
    summary = {
        "schema": RUN_SCHEMA, "run_id": run_id, "status": "completed",
        "completed_at": utc_now(), "elapsed_seconds": time.monotonic() - started,
        "steps_completed": len(selected_layers), "checkpoint_interval_layers": 1,
        "chunk_strategy": "one transformer layer per chunk", "gpu_used": False,
        "source": source, "adapter_dir": str(adapter_dir), "analysis_path": str(analysis_path),
        "trace_path": str(output_path), "trace_sha256": sha256_file(output_path),
        "checkpoint_path": str(checkpoint_path), "event_log": str(event_path),
    }
    atomic_json(run_dir / "run_summary.json", summary)
    append_event(event_path, {"event": "run_completed", "run_id": run_id, "at": utc_now(), **summary})
    return summary


def finalize_receipt(run_dir: Path) -> dict[str, Any]:
    run = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    resources = sorted(run_dir.glob("*.resource_summary.json"))
    cleanups = sorted(run_dir.glob("*cleanup*.json"))
    resource = json.loads(resources[-1].read_text(encoding="utf-8-sig")) if resources else None
    cleanup = json.loads(cleanups[-1].read_text(encoding="utf-8-sig")) if cleanups else None
    receipt = {
        "schema": "pixieology_bounded_run_receipt_v1",
        "run": run,
        "resource_summary": resource,
        "cleanup_summary": cleanup,
        "receipt_status": "complete" if resource and cleanup else "incomplete",
    }
    atomic_json(run_dir / "RUN_RECEIPT.json", receipt)
    return receipt


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("pixieology.config.json"))
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--max-layers", type=int)
    parser.add_argument("--finalize", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = args.config.resolve()
    config = load_config(config_path)
    run_dir = resolve_config_path(config_path, config, "godel_globes_bonsai_vpd_run_root") / args.run_id
    if args.finalize:
        receipt = finalize_receipt(run_dir)
        print(json.dumps({"receipt": str(run_dir / "RUN_RECEIPT.json"), "status": receipt["receipt_status"]}))
        return 0 if receipt["receipt_status"] == "complete" else 2
    summary = analyze_adapter(
        adapter_dir=resolve_config_path(config_path, config, "godel_globes_bonsai_adapter"),
        run_dir=run_dir,
        output_path=resolve_config_path(config_path, config, "godel_globes_bonsai_vpd_trace"),
        run_id=args.run_id,
        max_layers=args.max_layers,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted; latest completed layer remains checkpointed", file=sys.stderr)
        raise SystemExit(130)
