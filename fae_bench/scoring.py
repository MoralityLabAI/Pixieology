"""Deterministic, model-free metrics over Fae Bench JSONL records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable, Mapping, Sequence

from fae_bench.markers import MarkerSet, default_marker_set


DEFAULT_TOGGLE = "[[FAE_TOGGLE]]"
_TOKEN_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", flags=re.UNICODE)
_FAE_MODES = frozenset({"fae", "pixie", "triggered", "toggle_on"})
_PLAIN_MODES = frozenset({"plain", "normal", "base", "toggle_off"})


def _require_text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str):
        raise TypeError(f"record[{field!r}] must be a string")
    return value


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).casefold() for match in _TOKEN_RE.finditer(text))


def _mode(record: Mapping[str, Any]) -> str:
    return _require_text(record, "mode").strip().casefold().replace("-", "_")


def _marker_token_sequences(marker_set: MarkerSet) -> tuple[tuple[str, ...], ...]:
    sequences = (_tokens(marker) for marker in marker_set.markers)
    return tuple(sorted({tokens for tokens in sequences if tokens}, key=lambda item: (-len(item), item)))


def _marker_coverage(text: str, marker_set: MarkerSet) -> float:
    """Return the fraction of lexical tokens covered by one or more markers."""

    tokens = _tokens(text)
    if not tokens:
        return 0.0
    covered: set[int] = set()
    for marker in _marker_token_sequences(marker_set):
        width = len(marker)
        for start in range(0, len(tokens) - width + 1):
            if tokens[start : start + width] == marker:
                covered.update(range(start, start + width))
    return len(covered) / len(tokens)


def fae_score_lexical(
    record: Mapping[str, Any],
    *,
    marker_set: MarkerSet | None = None,
) -> float:
    """Fraction of response tokens covered by versioned whimsy/nature/lyrical markers."""

    return _marker_coverage(_require_text(record, "response"), marker_set or default_marker_set())


def echo_rate(record: Mapping[str, Any]) -> float:
    """Fraction of response tokens also present in the prompt's lexical vocabulary."""

    prompt_vocabulary = set(_tokens(_require_text(record, "prompt")))
    response_tokens = _tokens(_require_text(record, "response"))
    if not response_tokens:
        return 0.0
    return sum(token in prompt_vocabulary for token in response_tokens) / len(response_tokens)


def plain_drift(
    record: Mapping[str, Any],
    *,
    marker_set: MarkerSet | None = None,
) -> float:
    """Fae marker leakage for a plain-mode response; non-plain rows are not penalized."""

    if _mode(record) not in _PLAIN_MODES:
        return 0.0
    return fae_score_lexical(record, marker_set=marker_set)


def toggle_adherence(record: Mapping[str, Any], *, toggle: str = DEFAULT_TOGGLE) -> float:
    """Return 1 when declared response mode matches exact toggle presence, else 0."""

    prompt_has_toggle = toggle.casefold() in _require_text(record, "prompt").casefold()
    mode = _mode(record)
    if mode in _FAE_MODES:
        response_is_fae = True
    elif mode in _PLAIN_MODES:
        response_is_fae = False
    else:
        return 0.0
    return float(response_is_fae == prompt_has_toggle)


@dataclass(frozen=True)
class FaeBenchScore:
    fae_score_lexical: float
    echo_rate: float
    plain_drift: float
    toggle_adherence: float

    def metrics(self) -> dict[str, float]:
        return asdict(self)

    def reward(self, mode: str) -> float:
        """Balanced convenience reward; raw metrics remain separately available."""

        normalized_mode = mode.strip().casefold().replace("-", "_")
        style_term = self.fae_score_lexical if normalized_mode in _FAE_MODES else 1.0 - self.plain_drift
        return (style_term + (1.0 - self.echo_rate) + self.toggle_adherence) / 3.0


def score_record(record: Mapping[str, Any], *, marker_set: MarkerSet | None = None) -> FaeBenchScore:
    """Compute all four Fae Bench v1 metrics for one JSONL record mapping."""

    _require_text(record, "condition")
    selected_markers = marker_set or default_marker_set()
    return FaeBenchScore(
        fae_score_lexical=fae_score_lexical(record, marker_set=selected_markers),
        echo_rate=echo_rate(record),
        plain_drift=plain_drift(record, marker_set=selected_markers),
        toggle_adherence=toggle_adherence(record),
    )


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize_records(records: Iterable[Mapping[str, Any]]) -> dict[str, float | int]:
    """Aggregate records while averaging mode-specific metrics only on applicable rows."""

    materialized = list(records)
    scored = [(record, score_record(record)) for record in materialized]
    fae_scores = [score.fae_score_lexical for record, score in scored if _mode(record) in _FAE_MODES]
    plain_scores = [score.plain_drift for record, score in scored if _mode(record) in _PLAIN_MODES]
    return {
        "record_count": len(scored),
        "fae_record_count": len(fae_scores),
        "plain_record_count": len(plain_scores),
        "fae_score_lexical": _mean(fae_scores),
        "echo_rate": _mean([score.echo_rate for _, score in scored]),
        "plain_drift": _mean(plain_scores),
        "toggle_adherence": _mean([score.toggle_adherence for _, score in scored]),
    }
