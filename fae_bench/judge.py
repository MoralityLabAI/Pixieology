"""Provider-agnostic LLM judge contract for optional cloud-side evaluation.

This module intentionally performs no network calls and reads no credentials.
A cloud integration supplies an object implementing :class:`JudgeProvider`.
The provider receives a versioned rubric plus one normalized benchmark record
and must return structured per-dimension scores in the inclusive ``0..1``
range. Deterministic lexical metrics remain authoritative when no judge is
configured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


RUBRIC_VERSION = "fae_bench_llm_rubric_v1"
RUBRIC: Mapping[str, str] = {
    "persona_fidelity": "Whimsical, nature-aware, lyrical Fae voice without empty ornament.",
    "mode_control": "Fae voice appears only when the exact toggle requests it; plain mode stays plain.",
    "non_echoing": "Answers the request without parroting prompt wording or the toggle token.",
    "usefulness": "Remains correct, relevant, safe, and practically useful in either mode.",
}

GROUNDING_RUBRIC_VERSION = "fae_bench_grounding_llm_rubric_v2"
GROUNDING_RUBRIC: Mapping[str, str] = {
    "fact_entailment": "Every supplied atomic fact that the narration covers is stated faithfully.",
    "contradiction_free": "No entity, count, tick, ordering, or cause conflicts with fact_list.",
    "claim_support": "Every named-entity and event assertion is supported by fact_list and its event window.",
    "persona_fidelity": "Voice and ornament preserve the requested persona without changing facts.",
}


@dataclass(frozen=True)
class JudgeRequest:
    record: Mapping[str, Any]
    rubric_version: str = RUBRIC_VERSION
    rubric: Mapping[str, str] = field(default_factory=lambda: dict(RUBRIC))


@dataclass(frozen=True)
class JudgeResult:
    overall_score: float
    dimension_scores: Mapping[str, float]
    rationale: str
    provider: str
    model: str
    rubric_version: str = RUBRIC_VERSION


class JudgeProvider(Protocol):
    """Adapter boundary implemented by the cloud judge integration."""

    def judge(self, request: JudgeRequest) -> JudgeResult:
        ...


def _validate_result(
    result: JudgeResult,
    *,
    rubric: Mapping[str, str] = RUBRIC,
    rubric_version: str = RUBRIC_VERSION,
) -> JudgeResult:
    expected = set(rubric)
    if set(result.dimension_scores) != expected:
        raise ValueError(f"judge dimensions must be exactly {sorted(expected)}")
    scores = [result.overall_score, *result.dimension_scores.values()]
    if any(isinstance(score, bool) or not isinstance(score, (int, float)) or not 0.0 <= score <= 1.0 for score in scores):
        raise ValueError("judge scores must be numeric values in the inclusive 0..1 range")
    if result.rubric_version != rubric_version:
        raise ValueError(f"judge used {result.rubric_version!r}; expected {rubric_version!r}")
    return result


def llm_judge(record: Mapping[str, Any], provider: JudgeProvider | None = None) -> JudgeResult:
    """Evaluate one record with an injected provider, or explain how to configure one."""

    if provider is None:
        raise NotImplementedError(
            "No LLM judge provider configured. Inject a JudgeProvider; do not add API keys to fae_bench."
        )
    return _validate_result(provider.judge(JudgeRequest(record=dict(record))))


def llm_grounding_judge(
    record: Mapping[str, Any], provider: JudgeProvider | None = None
) -> JudgeResult:
    """Run the stronger semantic grounding rubric through an injected provider."""

    if provider is None:
        raise NotImplementedError(
            "No LLM judge provider configured. Inject a JudgeProvider; do not add API keys to fae_bench."
        )
    request = JudgeRequest(
        record=dict(record),
        rubric_version=GROUNDING_RUBRIC_VERSION,
        rubric=dict(GROUNDING_RUBRIC),
    )
    return _validate_result(
        provider.judge(request),
        rubric=GROUNDING_RUBRIC,
        rubric_version=GROUNDING_RUBRIC_VERSION,
    )
