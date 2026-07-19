"""Build a deterministic Fae-style x factual-grounding certification scorecard."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from fae_bench.grounding import score_grounding, summarize_grounding
from fae_bench.grounding_rules import default_grounding_rules
from fae_bench.markers import default_marker_set
from fae_bench.scoring import score_record, summarize_records
from pixie_env import config_path


SCORECARD_SCHEMA = "fae_bench.grounding_scorecard.v2"


@dataclass(frozen=True)
class CertificationThresholds:
    min_fact_recall: float = 1.0
    max_contradiction_rate: float = 0.0
    max_unsupported_claim_rate: float = 0.0
    min_toggle_adherence: float = 1.0
    min_fae_score_lexical: float | None = None
    max_plain_drift: float | None = None

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in the inclusive 0..1 range")


def _response(row: Mapping[str, Any]) -> str:
    for key in ("narration", "response", "action"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raise ValueError("narrated env row needs a non-empty narration, response, or action")


def _prompt(row: Mapping[str, Any]) -> str:
    for key in ("prompt", "state_prompt"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raise ValueError("narrated env row needs prompt or state_prompt")


def normalize_record(row: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a storyworld env row without changing its fact evidence."""

    normalized = dict(row)
    normalized["prompt"] = _prompt(row)
    normalized["response"] = _response(row)
    normalized["narration"] = normalized["response"]
    normalized["mode"] = str(row.get("mode") or "fae")
    normalized["condition"] = str(row.get("condition") or "chronicle_narration")
    episode_id = row.get("episode_id")
    if not isinstance(episode_id, str) or not episode_id:
        raise ValueError("narrated env row needs a non-empty episode_id")
    normalized["episode_id"] = episode_id
    normalized["record_id"] = str(
        row.get("record_id") or row.get("trajectory_id") or f"{episode_id}:row"
    )
    return normalized


def _passes(
    style: Mapping[str, float], grounding: Mapping[str, float], thresholds: CertificationThresholds
) -> bool:
    checks = [
        grounding["fact_recall"] >= thresholds.min_fact_recall,
        grounding["contradiction_rate"] <= thresholds.max_contradiction_rate,
        grounding["unsupported_claim_rate"] <= thresholds.max_unsupported_claim_rate,
        style["toggle_adherence"] >= thresholds.min_toggle_adherence,
    ]
    if thresholds.min_fae_score_lexical is not None:
        checks.append(style["fae_score_lexical"] >= thresholds.min_fae_score_lexical)
    if thresholds.max_plain_drift is not None:
        checks.append(style["plain_drift"] <= thresholds.max_plain_drift)
    return all(checks)


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "style": summarize_records(records),
        "grounding": summarize_grounding(records),
    }


def build_scorecard(
    rows: Iterable[Mapping[str, Any]],
    *,
    label: str,
    thresholds: CertificationThresholds | None = None,
) -> dict[str, Any]:
    """Return one deterministic adapter/model scorecard with episode rows."""

    if not label.strip():
        raise ValueError("scorecard label must be non-empty")
    selected_thresholds = thresholds or CertificationThresholds()
    records = [normalize_record(row) for row in rows]
    if not records:
        raise ValueError("scorecard input must contain at least one narrated row")

    per_record: list[dict[str, Any]] = []
    for record in records:
        style_score = score_record(record)
        grounding_score = score_grounding(record)
        style = style_score.metrics()
        grounding = grounding_score.metrics()
        per_record.append(
            {
                "episode_id": record["episode_id"],
                "record_id": record["record_id"],
                "mode": record["mode"],
                "condition": record["condition"],
                "style": style,
                "grounding": grounding,
                "grounding_evidence": grounding_score.evidence(),
                "passed": _passes(style, grounding, selected_thresholds),
            }
        )

    episodes: list[dict[str, Any]] = []
    for episode_id in sorted({record["episode_id"] for record in records}):
        episode_records = [record for record in records if record["episode_id"] == episode_id]
        result_rows = [row for row in per_record if row["episode_id"] == episode_id]
        episodes.append(
            {
                "episode_id": episode_id,
                "record_count": len(episode_records),
                **_summary(episode_records),
                "passed": all(row["passed"] for row in result_rows),
            }
        )

    failed_records = [row["record_id"] for row in per_record if not row["passed"]]
    return {
        "schema": SCORECARD_SCHEMA,
        "label": label.strip(),
        "metric_versions": {
            "style_markers": default_marker_set().version,
            "grounding_rules": default_grounding_rules().version,
        },
        "limits": (
            "Grounding metrics are deterministic lexical matchers, not NLI. "
            "An injected LLM judge remains the stronger semantic check."
        ),
        "thresholds": asdict(selected_thresholds),
        "summary": _summary(records),
        "episodes": episodes,
        "records": per_record,
        "certification": {
            "passed": not failed_records,
            "failed_record_count": len(failed_records),
            "failed_record_ids": failed_records,
            "episode_gate": "all records in every episode must pass",
        },
    }


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path).expanduser()
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("scorecard JSONL must contain only objects")
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=config_path("chronicle_narrated_env"))
    parser.add_argument("--output", type=Path, default=config_path("chronicle_scorecard"))
    parser.add_argument("--label")
    parser.add_argument("--min-fact-recall", type=float, default=1.0)
    parser.add_argument("--max-contradiction-rate", type=float, default=0.0)
    parser.add_argument("--max-unsupported-claim-rate", type=float, default=0.0)
    parser.add_argument("--min-toggle-adherence", type=float, default=1.0)
    parser.add_argument("--min-fae-score-lexical", type=float)
    parser.add_argument("--max-plain-drift", type=float)
    parser.add_argument("--no-fail-exit", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    thresholds = CertificationThresholds(
        min_fact_recall=args.min_fact_recall,
        max_contradiction_rate=args.max_contradiction_rate,
        max_unsupported_claim_rate=args.max_unsupported_claim_rate,
        min_toggle_adherence=args.min_toggle_adherence,
        min_fae_score_lexical=args.min_fae_score_lexical,
        max_plain_drift=args.max_plain_drift,
    )
    scorecard = build_scorecard(
        read_jsonl(args.input),
        label=args.label or args.input.stem,
        thresholds=thresholds,
    )
    scorecard["input"] = {
        "file": args.input.name,
        "sha256": sha256_file(args.input),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(scorecard, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(scorecard, indent=2, sort_keys=True))
    if scorecard["certification"]["passed"] or args.no_fail_exit:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
