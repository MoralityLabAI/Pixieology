from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from pixie_env import config_path


TRACE_SCHEMA = "pixieology_manifold_trace_v1"
FEATURE_FAMILIES = (
    ("residual_mix", "Residual mix", "residual_mix_dampen"),
    ("value_path", "Value path", "value_path_boost"),
    ("routing", "Routing stabilizer", "routing_stabilizer"),
)
SINGULAR_VALUE_RE = re.compile(r"(?:^|;)\s*sv=([0-9.eE+-]+)")


class VpdTraceError(RuntimeError):
    """Raised when a VPD-style refinement bundle cannot be converted safely."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VpdTraceError(f"could not read JSON object: {path}") from exc
    if not isinstance(payload, dict):
        raise VpdTraceError(f"expected a JSON object: {path}")
    return payload


def _resolve_member(source: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise VpdTraceError("chunk summary is missing refined_feature_map")
    path = Path(value).expanduser()
    return path if path.is_absolute() else source.parent / path


def _mean_singular_values(entries: Any) -> list[float]:
    if not isinstance(entries, list):
        raise VpdTraceError("refined feature map entries must be a list")
    groups: dict[str, list[float]] = {family: [] for _, _, family in FEATURE_FAMILIES}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        family = str(entry.get("feature_name") or "").split("/", 1)[0]
        match = SINGULAR_VALUE_RE.search(str(entry.get("notes") or ""))
        if family in groups and match:
            groups[family].append(float(match.group(1)))
    return [sum(groups[family]) / len(groups[family]) if groups[family] else 0.0 for _, _, family in FEATURE_FAMILIES]


def build_trace(source: Path, model_id: str) -> dict[str, Any]:
    summary = _read_object(source)
    chunks = summary.get("chunks")
    if not isinstance(chunks, list) or len(chunks) < 2:
        raise VpdTraceError("batch summary must contain at least two chunks")

    rows: list[dict[str, Any]] = []
    for position, chunk in enumerate(chunks):
        if not isinstance(chunk, dict) or not isinstance(chunk.get("summary"), dict):
            raise VpdTraceError(f"chunk {position} has no summary object")
        metrics = chunk["summary"]
        refined = _read_object(_resolve_member(source, metrics.get("refined_feature_map")))
        mechanical = _mean_singular_values(refined.get("entries"))
        try:
            mechanical.extend((float(metrics["mean_abs_logit_delta"]), float(metrics["max_abs_logit_delta"])))
            step = int(chunk.get("chunk_index", position))
            layer = int(chunk.get("start_layer", step))
        except (KeyError, TypeError, ValueError) as exc:
            raise VpdTraceError(f"chunk {position} has invalid numeric metrics") from exc
        if any(not math.isfinite(value) or value < 0.0 for value in mechanical):
            raise VpdTraceError(f"chunk {position} contains a negative or non-finite metric")
        rows.append({"step": step, "layer": layer, "raw": mechanical})

    rows.sort(key=lambda row: (row["step"], row["layer"]))
    minima = [min(row["raw"][index] for row in rows) for index in range(5)]
    maxima = [max(row["raw"][index] for row in rows) for index in range(5)]
    for row in rows:
        row["values"] = [
            0.5 if maxima[index] == minima[index] else (row["raw"][index] - minima[index]) / (maxima[index] - minima[index])
            for index in range(5)
        ]

    axis_specs = [
        (*FEATURE_FAMILIES[0][:2], "mean singular value"),
        (*FEATURE_FAMILIES[1][:2], "mean singular value"),
        (*FEATURE_FAMILIES[2][:2], "mean singular value"),
        ("mean_output_delta", "Mean output delta", "absolute logit delta"),
        ("peak_output_delta", "Peak output delta", "absolute logit delta"),
    ]
    axes = [
        {
            "id": axis_id,
            "label": label,
            "unit": "min-max normalized within trace",
            "raw_unit": raw_unit,
            "raw_range": [minima[index], maxima[index]],
        }
        for index, (axis_id, label, raw_unit) in enumerate(axis_specs)
    ]
    return {
        "schema": TRACE_SCHEMA,
        "id": "hrm-text-1b-vpd-depth-trace-v1",
        "title": "HRM-Text 1B VPD-style depth trace",
        "semantics": "mechanistic_normalized",
        "axes": axes,
        "alignment": {
            "status": "uncalibrated",
            "note": "Actual low-rank refinement measurements. These five mechanical channels are not certified Wonder, Play, Care, Resolve, or Reflection directions.",
        },
        "source": {
            "evidence_class": "actual_local_vpd_style_analysis",
            "model_id": model_id,
            "method": "low_rank_svd_refinement",
            "summary_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "source_name": source.name,
            "generated_at_utc": summary.get("generated_at_utc"),
            "chunk_count": len(rows),
        },
        "time": {"unit": "model depth (layer)"},
        "frames": [
            {
                "t": row["step"],
                "values": row["values"],
                "raw": row["raw"],
                "label": f"Layer {row['layer']}",
                "metadata": {"layer": row["layer"], "chunk_index": row["step"]},
            }
            for row in rows
        ],
    }


def render_javascript(trace: dict[str, Any]) -> str:
    payload = json.dumps(trace, indent=2, ensure_ascii=False, sort_keys=True)
    return (
        "(function (root, factory) {\n"
        "  const value = factory();\n"
        "  if (typeof module === \"object\" && module.exports) module.exports = value;\n"
        "  root.GodelVpdTraceData = value;\n"
        "})(typeof globalThis !== \"undefined\" ? globalThis : this, function () {\n"
        f"  return Object.freeze({payload});\n"
        "});\n"
    )


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_name = handle.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name and Path(temporary_name).exists():
            Path(temporary_name).unlink()


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Convert a five-channel VPD-style batch summary into the Godel Globe trace contract.")
    cli.add_argument("--source", type=Path, default=config_path("godel_globes_vpd_source"))
    cli.add_argument("--output", type=Path, default=config_path("godel_globes_vpd_trace"))
    cli.add_argument("--model-id", default="HRM-Text-1B")
    return cli


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        trace = build_trace(args.source, args.model_id)
        write_atomic(args.output, render_javascript(trace))
    except VpdTraceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
