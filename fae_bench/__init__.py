"""Public, dependency-light Fae Bench style and grounding scoring API."""

from fae_bench.grounding import (
    GroundingScore,
    contradiction_rate,
    fact_recall,
    score_grounding,
    summarize_grounding,
    unsupported_claim_rate,
)

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
    "GroundingScore",
    "contradiction_rate",
    "echo_rate",
    "fact_recall",
    "fae_score_lexical",
    "plain_drift",
    "score_grounding",
    "score_record",
    "summarize_grounding",
    "summarize_records",
    "toggle_adherence",
    "unsupported_claim_rate",
]

__version__ = "0.2.0"
