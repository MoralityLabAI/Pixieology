"""Load and validate the versioned lexical grounding matcher rules."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Mapping

import yaml


GROUNDING_RESOURCE = "grounding_rules_v1.yaml"


@dataclass(frozen=True)
class NumericTolerance:
    absolute: float


@dataclass(frozen=True)
class GroundingRules:
    version: str
    entity_aliases: Mapping[str, tuple[str, ...]]
    predicate_aliases: Mapping[str, tuple[str, ...]]
    event_aliases: Mapping[str, tuple[str, ...]]
    cause_aliases: Mapping[str, tuple[str, ...]]
    negation_terms: tuple[str, ...]
    cause_cues: tuple[str, ...]
    ordering_terms: Mapping[str, tuple[str, ...]]
    numeric_tolerances: Mapping[str, NumericTolerance]


def _phrase(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    return " ".join(value.casefold().strip().split())


def _phrase_list(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{context} must be a non-empty list")
    return tuple(dict.fromkeys(_phrase(item, context) for item in value))


def _alias_map(value: object, context: str) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    result: dict[str, tuple[str, ...]] = {}
    for key, aliases in value.items():
        normalized_key = _phrase(key, f"{context} key")
        result[normalized_key] = _phrase_list(aliases, f"{context}.{key}")
    return result


def _validate_payload(payload: object) -> GroundingRules:
    if not isinstance(payload, dict):
        raise ValueError("Grounding rules YAML must contain a mapping")
    version = _phrase(payload.get("version"), "version")
    ordering_terms = _alias_map(payload.get("ordering_terms"), "ordering_terms")
    if set(ordering_terms) != {"before", "after"}:
        raise ValueError("ordering_terms must define exactly before and after")

    raw_tolerances = payload.get("numeric_tolerances")
    if not isinstance(raw_tolerances, dict) or "default" not in raw_tolerances:
        raise ValueError("numeric_tolerances must be a mapping with a default entry")
    tolerances: dict[str, NumericTolerance] = {}
    for name, spec in raw_tolerances.items():
        normalized_name = _phrase(name, "numeric_tolerances key")
        if not isinstance(spec, dict):
            raise ValueError(f"numeric_tolerances.{name} must be a mapping")
        absolute = spec.get("absolute")
        if isinstance(absolute, bool) or not isinstance(absolute, (int, float)) or absolute < 0:
            raise ValueError(f"numeric_tolerances.{name}.absolute must be non-negative")
        tolerances[normalized_name] = NumericTolerance(absolute=float(absolute))

    return GroundingRules(
        version=version,
        entity_aliases=_alias_map(payload.get("entity_aliases", {}), "entity_aliases"),
        predicate_aliases=_alias_map(payload.get("predicate_aliases"), "predicate_aliases"),
        event_aliases=_alias_map(payload.get("event_aliases"), "event_aliases"),
        cause_aliases=_alias_map(payload.get("cause_aliases"), "cause_aliases"),
        negation_terms=_phrase_list(payload.get("negation_terms"), "negation_terms"),
        cause_cues=_phrase_list(payload.get("cause_cues"), "cause_cues"),
        ordering_terms=ordering_terms,
        numeric_tolerances=tolerances,
    )


def load_grounding_rules(path: str | Path | None = None) -> GroundingRules:
    """Load rules from ``path`` or the package's immutable v1 YAML resource."""

    if path is None:
        resource = files("fae_bench.data").joinpath(GROUNDING_RESOURCE)
        with resource.open("r", encoding="utf-8") as handle:
            return _validate_payload(yaml.safe_load(handle))
    with Path(path).expanduser().open("r", encoding="utf-8") as handle:
        return _validate_payload(yaml.safe_load(handle))


@lru_cache(maxsize=1)
def default_grounding_rules() -> GroundingRules:
    return load_grounding_rules()
