"""Public, dependency-light Fae Bench v1 scoring API."""

from fae_bench.scoring import (
    DEFAULT_TOGGLE,
    FaeBenchScore,
    echo_rate,
    fae_score_lexical,
    plain_drift,
    score_record,
    summarize_records,
    toggle_adherence,
)

__all__ = [
    "DEFAULT_TOGGLE",
    "FaeBenchScore",
    "echo_rate",
    "fae_score_lexical",
    "plain_drift",
    "score_record",
    "summarize_records",
    "toggle_adherence",
]

__version__ = "0.1.0"
