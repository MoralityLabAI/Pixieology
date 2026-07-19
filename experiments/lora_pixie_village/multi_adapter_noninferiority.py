#!/usr/bin/env python3
"""Run and analyze the frozen multi-adapter semantic non-inferiority study.

Companion retention uses pinned sentence embeddings against frozen rubric
references. Storyworld retention uses exact final-action matching. Embedding
similarity is semantic proximity, not NLI; subtle contradiction detection is a
known limitation and is reported rather than hidden.
"""

from __future__ import annotations

import gc
import json
import math
import os
import random
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Callable


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parents[1]
for root in (APP_ROOT, REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import existing_adapter_pair  # noqa: E402
import multi_adapter_compare  # noqa: E402
import multi_adapter_matrix  # noqa: E402
import server  # noqa: E402


SCHEMA_VERSION = "pixie_multi_adapter_noninferiority_v1"
POINTER_SCHEMA = "pixie_multi_adapter_noninferiority_pointer_v1"
COMPANION_POINTER_SCHEMA = "pixie_multi_adapter_noninferiority_companion_pointer_v1"
CONDITION_ALIASES = {
    "base": "base-local",
    "companion": "companion-local",
    "storyworld": "storyworld-local",
    "stacked": "stacked-local",
}
PRIMARY_CONDITIONS = {
    "companion": ("companion", "stacked"),
    "action": ("storyworld", "stacked"),
    "joint": ("companion", "storyworld", "stacked"),
}
ACTION_RE = re.compile(r"^\([A-Za-z][A-Za-z0-9_-]*(?: [A-Za-z][A-Za-z0-9_-]*)+\)$")


class NoninferiorityError(RuntimeError):
    """The frozen protocol, paired data, or semantic scorer failed closed."""


def load_protocol(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NoninferiorityError(f"cannot read protocol {path}: {exc}") from exc
    return validate_protocol(value)


def validate_protocol(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise NoninferiorityError(f"protocol must use {SCHEMA_VERSION}")
    if value.get("conditions") != ["base", "companion", "storyworld", "stacked"]:
        raise NoninferiorityError("condition order must match the frozen four-condition matrix")
    if value.get("primary_comparisons") != [
        {"metric": "companion_semantic", "stacked": "stacked", "reference": "companion"},
        {"metric": "action_exact", "stacked": "stacked", "reference": "storyworld"},
    ]:
        raise NoninferiorityError("primary comparisons differ from the frozen v1 estimands")
    margin = value.get("noninferiority_margin")
    if isinstance(margin, bool) or not isinstance(margin, (int, float)) or float(margin) != 0.05:
        raise NoninferiorityError("v1 non-inferiority margin must be exactly 0.05")
    bootstrap = value.get("bootstrap")
    if not isinstance(bootstrap, dict) or bootstrap.get("resamples") != 10000:
        raise NoninferiorityError("v1 requires exactly 10,000 bootstrap resamples")
    if bootstrap.get("seed") != 1701 or bootstrap.get("stratified") is not True:
        raise NoninferiorityError("v1 bootstrap seed and stratification are frozen")
    scorer = value.get("semantic_scorer")
    if not isinstance(scorer, dict) or scorer.get("metric") != "cosine_similarity":
        raise NoninferiorityError("semantic scorer must be the frozen cosine configuration")
    revision = str(scorer.get("revision") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise NoninferiorityError("semantic scorer revision must be a pinned 40-character hash")
    if scorer.get("local_files_only") is not True or scorer.get("treatment_blind") is not True:
        raise NoninferiorityError("semantic scoring must remain offline and treatment-blind")
    decoding = value.get("decoding")
    if decoding != {
        "temperature": 0,
        "seed": 17,
        "max_tokens_default": 96,
        "enable_thinking": False,
    }:
        raise NoninferiorityError("decoding differs from the frozen deterministic configuration")
    provenance = value.get("source_provenance")
    required_hashes = {
        "reflective_buddy_holdout_bench_sha256",
        "reflective_buddy_training_env_sha256",
        "storyworld_action_training_env_sha256",
        "storyworld_prose_training_env_sha256",
    }
    if not isinstance(provenance, dict) or any(
        not re.fullmatch(r"[0-9a-f]{64}", str(provenance.get(name) or ""))
        for name in required_hashes
    ):
        raise NoninferiorityError("source provenance requires four pinned SHA-256 values")
    suites = {
        "companion": value.get("companion_probes"),
        "action": value.get("action_probes"),
        "joint": value.get("joint_probes"),
    }
    expected_counts = {"companion": 8, "action": 8, "joint": 4}
    seen_ids: set[str] = set()
    seen_prompts: set[str] = set()
    for suite, rows in suites.items():
        if not isinstance(rows, list) or len(rows) != expected_counts[suite]:
            raise NoninferiorityError(f"{suite} suite must contain exactly {expected_counts[suite]} probes")
        families: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise NoninferiorityError(f"{suite} probe must be an object")
            probe_id = str(row.get("probe_id") or "")
            family = str(row.get("family") or "")
            prompt = str(row.get("prompt") or "").strip()
            normalized = " ".join(prompt.casefold().split())
            if not probe_id or probe_id in seen_ids or not family or not prompt:
                raise NoninferiorityError("probe IDs, families, and prompts must be unique and non-empty")
            if normalized in seen_prompts:
                raise NoninferiorityError("normalized probe prompts must be disjoint")
            seen_ids.add(probe_id)
            seen_prompts.add(normalized)
            families.add(family)
            if suite in {"action", "joint"} and not ACTION_RE.fullmatch(str(row.get("expected_action") or "")):
                raise NoninferiorityError(f"probe {probe_id} has invalid expected_action")
            if suite in {"companion", "joint"}:
                rubric = row.get("rubric")
                if not isinstance(rubric, dict) or not rubric.get("objective"):
                    raise NoninferiorityError(f"probe {probe_id} requires a semantic rubric")
                if not isinstance(rubric.get("required_semantics"), list) or not rubric["required_semantics"]:
                    raise NoninferiorityError(f"probe {probe_id} requires semantic reference clauses")
        if len(families) < 2:
            raise NoninferiorityError(f"{suite} probes require at least two bootstrap strata")
    return value


def reference_text(rubric: dict[str, Any]) -> str:
    clauses = "; ".join(str(value) for value in rubric["required_semantics"])
    return f"{rubric['objective']} A strong response conveys: {clauses}."


def final_action(content: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def companion_text(content: str, expected_action: str | None) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if expected_action and lines and lines[-1] == expected_action:
        lines = lines[:-1]
    return " ".join(lines).strip()


def generation_plan(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    suites = [
        ("companion", protocol["companion_probes"]),
        ("action", protocol["action_probes"]),
        ("joint", protocol["joint_probes"]),
    ]
    max_tokens = {"companion": 64, "action": 40, "joint": 80}
    systems = {
        "companion": "Respond directly with visible public speech only, in no more than three concise sentences.",
        "action": "Follow the requested public action format exactly. Do not expose hidden reasoning.",
        "joint": "Follow both requested public response parts exactly. Do not expose hidden reasoning.",
    }
    for suite, probes in suites:
        for probe in probes:
            for condition in PRIMARY_CONDITIONS[suite]:
                plan.append(
                    {
                        "suite": suite,
                        "condition_id": condition,
                        "model_alias": CONDITION_ALIASES[condition],
                        "probe": probe,
                        "system": systems[suite],
                        "max_tokens": max_tokens[suite],
                    }
                )
    return plan


def collect_generations(
    base_url: str,
    protocol: dict[str, Any],
    matrix: dict[str, Any],
    output_dir: Path,
    *,
    request: Callable[..., Any] | None = None,
    existing_rows: list[dict[str, Any]] | None = None,
    max_items: int | None = None,
    identities_path: Path | None = None,
) -> list[dict[str, Any]]:
    request = request or multi_adapter_compare.request_json
    models = request(base_url.rstrip("/") + "/v1/models")
    observed_aliases = {
        str(row.get("id")) for row in models.get("data", []) if isinstance(row, dict)
    }
    if observed_aliases != set(CONDITION_ALIASES.values()):
        raise NoninferiorityError(f"unexpected model aliases: {sorted(observed_aliases)}")
    condition_by_id = {row["condition_id"]: row for row in matrix["conditions"]}
    identities: dict[str, Any] = {}
    for condition_id, alias in CONDITION_ALIASES.items():
        identity = request(base_url.rstrip("/") + f"/pixie/identity/{condition_id}")
        identities[condition_id] = multi_adapter_compare.validate_identity(
            identity, matrix, condition_by_id[condition_id]
        )
    server.atomic_json(identities_path or output_dir / "identities.json", identities)

    raw_path = output_dir / "raw_generations.jsonl"
    rows = list(existing_rows or [])
    plan = generation_plan(protocol)
    validate_generation_prefix(rows, protocol)
    decoding = protocol["decoding"]
    remaining = plan[len(rows) :]
    if max_items is not None:
        if max_items < 1:
            raise NoninferiorityError("max_items must be positive")
        remaining = remaining[:max_items]
    for item in remaining:
        probe = item["probe"]
        payload = {
            "model": item["model_alias"],
            "messages": [
                {"role": "system", "content": item["system"]},
                {"role": "user", "content": probe["prompt"]},
            ],
            "temperature": decoding["temperature"],
            "seed": decoding["seed"],
            "max_tokens": item["max_tokens"],
        }
        # Symbolic prompts can take several minutes at the mandatory 50% Job
        # CPU rate. The outer 30-minute Job timeout remains the hard bound.
        response = request(
            base_url.rstrip("/") + "/v1/chat/completions",
            payload=payload,
            timeout=900,
        )
        content = multi_adapter_compare.extract_content(response)
        expected_action = probe.get("expected_action")
        action = final_action(content) if expected_action else None
        row = {
            "schema_version": "pixie_multi_adapter_noninferiority_generation_v1",
            "protocol_id": protocol["protocol_id"],
            "suite": item["suite"],
            "family": probe["family"],
            "probe_id": probe["probe_id"],
            "condition_id": item["condition_id"],
            "model_alias": item["model_alias"],
            "content": content,
            "content_sha256": server.sha256_value(content),
            "request_sha256": server.sha256_value(payload),
            "response_sha256": server.sha256_value(response),
            "expected_action": expected_action,
            "observed_final_action": action,
            "action_exact": bool(expected_action and action == expected_action),
            "strict_action_only": bool(expected_action and content.strip() == expected_action),
            "semantic_reference": reference_text(probe["rubric"]) if "rubric" in probe else None,
            "semantic_response": companion_text(content, expected_action) if "rubric" in probe else None,
        }
        server.append_jsonl_fsync(raw_path, row)
        rows.append(row)
    if len({(row["suite"], row["probe_id"], row["condition_id"]) for row in rows}) != len(rows):
        raise NoninferiorityError("generation factorial is incomplete or duplicated")
    return rows


def read_generation_rows(path: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise NoninferiorityError(f"invalid generation JSONL line {line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise NoninferiorityError(f"generation line {line_number} is not an object")
        rows.append(row)
    validate_generation_prefix(rows, protocol)
    return rows


def validate_generation_prefix(rows: list[dict[str, Any]], protocol: dict[str, Any]) -> None:
    plan = generation_plan(protocol)
    if len(rows) > len(plan):
        raise NoninferiorityError("generation checkpoint is longer than the frozen plan")
    for index, row in enumerate(rows):
        expected = plan[index]
        expected_key = (
            expected["suite"],
            expected["probe"]["probe_id"],
            expected["condition_id"],
        )
        observed_key = (row.get("suite"), row.get("probe_id"), row.get("condition_id"))
        if row.get("schema_version") != "pixie_multi_adapter_noninferiority_generation_v1":
            raise NoninferiorityError(f"generation {index} has the wrong schema")
        if row.get("protocol_id") != protocol["protocol_id"] or observed_key != expected_key:
            raise NoninferiorityError(f"generation {index} does not match the frozen plan prefix")
        content = str(row.get("content") or "")
        if not content or row.get("content_sha256") != server.sha256_value(content):
            raise NoninferiorityError(f"generation {index} content hash mismatch")


def cosine_semantic_scores(
    rows: list[dict[str, Any]], protocol: dict[str, Any], hf_home: Path
) -> tuple[dict[tuple[str, str, str], float], dict[str, Any]]:
    semantic_rows = [
        row
        for row in rows
        if row["semantic_reference"] is not None
        and row["condition_id"] in {"companion", "stacked"}
    ]
    if any(not row["semantic_response"] for row in semantic_rows):
        raise NoninferiorityError("a semantic response is empty")
    scorer = protocol["semantic_scorer"]
    old_env = {name: os.environ.get(name) for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    model = None
    try:
        from sentence_transformers import SentenceTransformer
        import sentence_transformers
        import torch

        cache_slug = "models--" + scorer["model_id"].replace("/", "--")
        snapshot = hf_home / "hub" / cache_slug / "snapshots" / scorer["revision"]
        required_snapshot_files = [
            snapshot / "modules.json",
            snapshot / "config.json",
            snapshot / "model.safetensors",
            snapshot / "tokenizer.json",
            snapshot / "1_Pooling" / "config.json",
        ]
        if any(not path.is_file() for path in required_snapshot_files):
            raise NoninferiorityError(f"pinned semantic snapshot is incomplete: {snapshot}")
        model = SentenceTransformer(
            str(snapshot),
            local_files_only=True,
            device="cpu",
        )
        texts: list[str] = []
        for row in semantic_rows:
            texts.extend([row["semantic_response"], row["semantic_reference"]])
        embeddings = model.encode(
            texts,
            batch_size=int(scorer["batch_size"]),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        scores: dict[tuple[str, str, str], float] = {}
        for index, row in enumerate(semantic_rows):
            score = float(embeddings[index * 2] @ embeddings[index * 2 + 1])
            if not math.isfinite(score) or score < -1.0001 or score > 1.0001:
                raise NoninferiorityError(f"invalid cosine score for {row['probe_id']}: {score}")
            scores[(row["suite"], row["probe_id"], row["condition_id"])] = score
        metadata = {
            "model_id": scorer["model_id"],
            "revision": scorer["revision"],
            "resolved_snapshot": str(snapshot),
            "metric": scorer["metric"],
            "treatment_blind": True,
            "local_files_only": True,
            "sentence_transformers_version": sentence_transformers.__version__,
            "torch_version": torch.__version__,
            "device": "cpu",
            "semantic_rows": len(semantic_rows),
        }
        return scores, metadata
    except NoninferiorityError:
        raise
    except Exception as exc:
        raise NoninferiorityError(f"semantic scorer failed: {type(exc).__name__}: {exc}") from exc
    finally:
        model = None
        gc.collect()
        for name, value in old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise NoninferiorityError("cannot take percentile of empty values")
    position = (len(sorted_values) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def paired_stratified_bootstrap(
    records: list[dict[str, Any]], *, reference: str, stacked: str, resamples: int, seed: int
) -> dict[str, Any]:
    by_probe: dict[str, dict[str, Any]] = {}
    for row in records:
        probe = by_probe.setdefault(row["probe_id"], {"family": row["family"], "scores": {}})
        if probe["family"] != row["family"]:
            raise NoninferiorityError("probe family changed across paired conditions")
        probe["scores"][row["condition_id"]] = float(row["score"])
    if not by_probe or any(set(row["scores"]) != {reference, stacked} for row in by_probe.values()):
        raise NoninferiorityError(f"incomplete paired rows for {reference} versus {stacked}")
    strata: dict[str, list[float]] = {}
    for probe in by_probe.values():
        strata.setdefault(probe["family"], []).append(probe["scores"][stacked] - probe["scores"][reference])
    observed = [difference for values in strata.values() for difference in values]
    rng = random.Random(seed)
    bootstrap_means: list[float] = []
    for _ in range(resamples):
        sample: list[float] = []
        for values in strata.values():
            sample.extend(values[rng.randrange(len(values))] for _ in range(len(values)))
        bootstrap_means.append(statistics.fmean(sample))
    bootstrap_means.sort()
    return {
        "reference": reference,
        "stacked": stacked,
        "n_pairs": len(observed),
        "strata": {family: len(values) for family, values in strata.items()},
        "point_difference": statistics.fmean(observed),
        "ci95": [percentile(bootstrap_means, 0.025), percentile(bootstrap_means, 0.975)],
        "resamples": resamples,
        "seed": seed,
    }


def analyze(
    rows: list[dict[str, Any]], protocol: dict[str, Any], hf_home: Path
) -> dict[str, Any]:
    semantic, scorer_metadata = cosine_semantic_scores(rows, protocol, hf_home)
    scored: list[dict[str, Any]] = []
    for row in rows:
        score: float | None
        metric: str | None
        semantic_key = (row["suite"], row["probe_id"], row["condition_id"])
        if semantic_key in semantic:
            score = semantic[semantic_key]
            metric = "companion_semantic"
            scored.append({**row, "metric": metric, "score": score})
        if row["suite"] == "action" or (
            row["suite"] == "joint" and row["condition_id"] in {"storyworld", "stacked"}
        ):
            score = 1.0 if row["action_exact"] else 0.0
            metric = "action_exact"
            scored.append({**row, "metric": metric, "score": score})

    bootstrap = protocol["bootstrap"]
    companion_primary = paired_stratified_bootstrap(
        [row for row in scored if row["suite"] == "companion" and row["metric"] == "companion_semantic"],
        reference="companion",
        stacked="stacked",
        resamples=bootstrap["resamples"],
        seed=bootstrap["seed"],
    )
    action_primary = paired_stratified_bootstrap(
        [row for row in scored if row["suite"] == "action" and row["metric"] == "action_exact"],
        reference="storyworld",
        stacked="stacked",
        resamples=bootstrap["resamples"],
        seed=bootstrap["seed"] + 1,
    )
    joint_companion = paired_stratified_bootstrap(
        [
            row
            for row in scored
            if row["suite"] == "joint"
            and row["metric"] == "companion_semantic"
            and row["condition_id"] in {"companion", "stacked"}
        ],
        reference="companion",
        stacked="stacked",
        resamples=bootstrap["resamples"],
        seed=bootstrap["seed"] + 2,
    )
    joint_action = paired_stratified_bootstrap(
        [
            row
            for row in scored
            if row["suite"] == "joint"
            and row["metric"] == "action_exact"
            and row["condition_id"] in {"storyworld", "stacked"}
        ],
        reference="storyworld",
        stacked="stacked",
        resamples=bootstrap["resamples"],
        seed=bootstrap["seed"] + 3,
    )
    primary = {
        "companion_semantic": companion_primary,
        "action_exact": action_primary,
    }
    margin = float(protocol["noninferiority_margin"])
    if any(result["point_difference"] < -margin for result in primary.values()):
        verdict = "FAIL"
    elif all(result["ci95"][0] >= -margin for result in primary.values()):
        verdict = "PASS"
    else:
        verdict = "INCONCLUSIVE"

    summaries: dict[str, dict[str, float]] = {}
    for suite in ("companion", "action", "joint"):
        for metric in ("companion_semantic", "action_exact"):
            selected = [row for row in scored if row["suite"] == suite and row["metric"] == metric]
            for condition in sorted({row["condition_id"] for row in selected}):
                values = [row["score"] for row in selected if row["condition_id"] == condition]
                summaries.setdefault(f"{suite}.{metric}", {})[condition] = statistics.fmean(values)
    return {
        "schema_version": "pixie_multi_adapter_noninferiority_analysis_v1",
        "protocol_id": protocol["protocol_id"],
        "verdict": verdict,
        "noninferiority_margin": margin,
        "primary": primary,
        "secondary_joint": {
            "companion_semantic": joint_companion,
            "action_exact": joint_action,
        },
        "means": summaries,
        "semantic_scorer": scorer_metadata,
        "scored_rows": scored,
        "limitations": [
            "Sentence-embedding similarity is semantic proximity, not NLI, and can miss negation or contradiction.",
            "The companion and Storyworld adapters were trained for different objectives and capacities.",
            "The small held-out suites yield wide uncertainty when paired outcomes vary.",
        ],
    }


def analyze_companion_checkpoint(
    rows: list[dict[str, Any]], protocol: dict[str, Any], hf_home: Path
) -> dict[str, Any]:
    """Score the completed companion prefix without estimating the full verdict."""
    validate_generation_prefix(rows, protocol)
    companion_rows = [row for row in rows if row["suite"] == "companion"]
    if len(companion_rows) != 16 or any(row["suite"] != "companion" for row in rows):
        raise NoninferiorityError("companion checkpoint requires exactly the frozen first 16 rows")
    semantic, metadata = cosine_semantic_scores(companion_rows, protocol, hf_home)
    scored = [
        {
            **row,
            "metric": "companion_semantic",
            "score": semantic[(row["suite"], row["probe_id"], row["condition_id"])],
        }
        for row in companion_rows
    ]
    bootstrap = protocol["bootstrap"]
    comparison = paired_stratified_bootstrap(
        scored,
        reference="companion",
        stacked="stacked",
        resamples=bootstrap["resamples"],
        seed=bootstrap["seed"],
    )
    margin = float(protocol["noninferiority_margin"])
    if comparison["point_difference"] < -margin:
        companion_verdict = "FAIL"
    elif comparison["ci95"][0] >= -margin:
        companion_verdict = "PASS"
    else:
        companion_verdict = "INCONCLUSIVE"
    means = {
        condition: statistics.fmean(
            row["score"] for row in scored if row["condition_id"] == condition
        )
        for condition in ("companion", "stacked")
    }
    return {
        "schema_version": "pixie_multi_adapter_companion_checkpoint_analysis_v1",
        "protocol_id": protocol["protocol_id"],
        "status": "PASS_COMPANION_CHECKPOINT_SCORED",
        "overall_verdict": "NOT_ESTIMATED",
        "companion_verdict": companion_verdict,
        "noninferiority_margin": margin,
        "means": means,
        "comparison": comparison,
        "semantic_scorer": metadata,
        "limitations": [
            "The Storyworld action and joint suites were not completed, so no overall verdict is estimated.",
            "Sentence-embedding similarity is semantic proximity, not NLI.",
        ],
    }


def render_report(receipt: dict[str, Any], analysis: dict[str, Any]) -> str:
    primary = analysis["primary"]
    means = analysis["means"]
    lines = [
        "# Multi-adapter non-inferiority v1",
        "",
        f"Verdict: **{analysis['verdict']}**",
        "",
        "## Primary comparisons",
        "",
        "| Metric | Reference mean | Stacked mean | Difference | 95% paired bootstrap CI | Margin |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for metric, suite, reference in (
        ("companion_semantic", "companion", "companion"),
        ("action_exact", "action", "storyworld"),
    ):
        result = primary[metric]
        suite_means = means[f"{suite}.{metric}"]
        lines.append(
            f"| {metric} | {suite_means[reference]:.4f} | {suite_means['stacked']:.4f} | "
            f"{result['point_difference']:.4f} | [{result['ci95'][0]:.4f}, {result['ci95'][1]:.4f}] | "
            f"-{analysis['noninferiority_margin']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Joint stress test",
            "",
            f"- Companion semantic difference: {analysis['secondary_joint']['companion_semantic']['point_difference']:.4f} "
            f"(95% CI {analysis['secondary_joint']['companion_semantic']['ci95']}).",
            f"- Exact-action difference: {analysis['secondary_joint']['action_exact']['point_difference']:.4f} "
            f"(95% CI {analysis['secondary_joint']['action_exact']['ci95']}).",
            "",
            "## Audit",
            "",
            f"- Protocol SHA-256: `{receipt['protocol_sha256']}`",
            f"- Matrix SHA-256: `{receipt['matrix_sha256']}`",
            f"- Raw generations: `{receipt['raw_generations_sha256']}`",
            f"- Semantic model: `{analysis['semantic_scorer']['model_id']}` at "
            f"`{analysis['semantic_scorer']['revision']}` (CPU, offline).",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {limitation}" for limitation in analysis["limitations"])
    return "\n".join(lines) + "\n"


def write_results(
    output_dir: Path,
    protocol: dict[str, Any],
    matrix: dict[str, Any],
    rows: list[dict[str, Any]],
    analysis: dict[str, Any],
    *,
    launch_manifest: Path,
) -> dict[str, Any]:
    raw_path = output_dir / "raw_generations.jsonl"
    scored_path = output_dir / "scored_rows.jsonl"
    for row in analysis["scored_rows"]:
        server.append_jsonl_fsync(scored_path, row)
    analysis_public = {key: value for key, value in analysis.items() if key != "scored_rows"}
    server.atomic_json(output_dir / "analysis.json", analysis_public)
    receipt = {
        "schema_version": "pixie_multi_adapter_noninferiority_receipt_v1",
        "status": "PASS_COMPLETED",
        "verdict": analysis["verdict"],
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": multi_adapter_matrix.sha256_value(protocol),
        "matrix_id": matrix["matrix_id"],
        "matrix_sha256": multi_adapter_matrix.sha256_value(matrix),
        "generation_count": len(rows),
        "raw_generations": str(raw_path),
        "raw_generations_sha256": existing_adapter_pair.sha256_file(raw_path),
        "scored_rows": str(scored_path),
        "scored_rows_sha256": existing_adapter_pair.sha256_file(scored_path),
        "analysis": str(output_dir / "analysis.json"),
        "analysis_sha256": existing_adapter_pair.sha256_file(output_dir / "analysis.json"),
        "launch_manifest": str(launch_manifest),
        "primary": analysis["primary"],
        "secondary_joint": analysis["secondary_joint"],
        "means": analysis["means"],
        "limitations": analysis["limitations"],
    }
    server.atomic_json(output_dir / "receipt.json", receipt)
    (output_dir / "report.md").write_text(render_report(receipt, analysis_public), encoding="utf-8", newline="\n")
    return receipt


def pointer_for(receipt_path: Path, receipt: dict[str, Any], run_id: str) -> dict[str, Any]:
    return {
        "schema_version": POINTER_SCHEMA,
        "status": receipt["status"],
        "verdict": receipt["verdict"],
        "run_id": run_id,
        "protocol_id": receipt["protocol_id"],
        "receipt": str(receipt_path),
        "receipt_sha256": existing_adapter_pair.sha256_file(receipt_path),
        "primary": receipt.get("primary"),
        "secondary_joint": receipt.get("secondary_joint"),
        "means": receipt.get("means"),
        "limitations": receipt.get("limitations"),
        "error": receipt.get("error"),
    }
