"""Deterministic lexical grounding metrics for fact-constrained narrations.

These metrics are lexical matchers, not natural-language inference. They can
reliably catch explicit entity, count, tick, ordering, cause, and negation
errors that use the versioned vocabulary, but paraphrases outside that
vocabulary can be missed and figurative language can trigger false positives.
The injected LLM judge remains the stronger semantic check; these pure,
model-free functions are its cheap deterministic forerunner.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable, Mapping, Sequence

from fae_bench.grounding_rules import GroundingRules, default_grounding_rules


_TOKEN_RE = re.compile(r"[^\W_]+", flags=re.UNICODE)
_NUMBER_RE = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
_STATEMENT_SPLIT_RE = re.compile(r"(?:\r?\n+|(?<=[.!?;])\s+)")
_ID_LIKE_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:[-_/][A-Za-z0-9]+)+\b")
_WORD_NUMBERS = {
    "zero": 0.0,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
    "eleven": 11.0,
    "twelve": 12.0,
    "thirteen": 13.0,
    "fourteen": 14.0,
    "fifteen": 15.0,
    "sixteen": 16.0,
    "seventeen": 17.0,
    "eighteen": 18.0,
    "nineteen": 19.0,
    "twenty": 20.0,
}


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).casefold() for match in _TOKEN_RE.finditer(text))


def _humanize(value: object) -> str:
    text = re.sub(r"[_/\\-]+", " ", str(value).casefold())
    return " ".join(text.split())


def _contains_tokens(haystack: Sequence[str], needle: Sequence[str]) -> bool:
    width = len(needle)
    return bool(width) and any(
        tuple(haystack[start : start + width]) == tuple(needle)
        for start in range(len(haystack) - width + 1)
    )


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    tokens = _tokens(text)
    return any(_contains_tokens(tokens, _tokens(phrase)) for phrase in phrases)


def _matched_phrases(text: str, phrases: Iterable[str]) -> set[tuple[str, ...]]:
    tokens = _tokens(text)
    return {
        phrase_tokens
        for phrase in phrases
        if (phrase_tokens := _tokens(phrase)) and _contains_tokens(tokens, phrase_tokens)
    }


def _first_position(text: str, phrases: Iterable[str]) -> int | None:
    tokens = _tokens(text)
    positions: list[int] = []
    for phrase in phrases:
        needle = _tokens(phrase)
        width = len(needle)
        for start in range(len(tokens) - width + 1):
            if tuple(tokens[start : start + width]) == needle:
                positions.append(start)
                break
    return min(positions) if positions else None


def _aliases(value: object, aliases: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
    raw = " ".join(str(value).casefold().strip().split())
    human = _humanize(value)
    values = [raw, human]
    for key in (raw, human):
        values.extend(aliases.get(key, ()))
    return tuple(dict.fromkeys(item for item in values if item))


def _entity_aliases(value: object, rules: GroundingRules) -> tuple[str, ...]:
    return _aliases(value, rules.entity_aliases)


def _event_aliases(value: object, rules: GroundingRules) -> tuple[str, ...]:
    return _aliases(value, rules.event_aliases)


def _predicate_aliases(value: object, rules: GroundingRules) -> tuple[str, ...]:
    return _aliases(value, rules.predicate_aliases)


def _cause_aliases(value: object, rules: GroundingRules) -> tuple[str, ...]:
    return _aliases(value, rules.cause_aliases)


def _numbers(text: str) -> list[float]:
    values = [float(match.group(0)) for match in _NUMBER_RE.finditer(text)]
    values.extend(_WORD_NUMBERS[token] for token in _tokens(text) if token in _WORD_NUMBERS)
    return values


def _statements(text: str) -> list[str]:
    return [part.strip() for part in _STATEMENT_SPLIT_RE.split(text) if part.strip()]


def _narration(record: Mapping[str, Any]) -> str:
    value = record.get("narration")
    if value is None:
        value = record.get("response")
    if not isinstance(value, str) or not value.strip():
        raise TypeError("record narration (or response) must be a non-empty string")
    return value


def _facts(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = record.get("fact_list")
    if not isinstance(value, list) or not value:
        raise TypeError("record['fact_list'] must be a non-empty list")
    if any(not isinstance(item, Mapping) for item in value):
        raise TypeError("record['fact_list'] must contain only mappings")
    return list(value)


def _predicate(fact: Mapping[str, Any]) -> str:
    value = fact.get("predicate")
    if not isinstance(value, str) or not value.strip():
        raise TypeError("each fact predicate must be a non-empty string")
    return value.casefold().strip()


def _subject(fact: Mapping[str, Any]) -> str:
    value = fact.get("subject")
    if not isinstance(value, str) or not value.strip():
        raise TypeError("each fact subject must be a non-empty string")
    return value


def _event_key(fact: Mapping[str, Any]) -> str | None:
    predicate = _predicate(fact)
    if predicate.startswith("born_"):
        return "birth"
    if predicate.startswith("died_") or predicate == "death_cause_chain":
        return "death"
    if predicate == "participated_in_event" and isinstance(fact.get("value"), str):
        return str(fact["value"]).casefold()
    if predicate == "window_event_count" and isinstance(fact.get("value"), Mapping):
        event_type = fact["value"].get("event_type")
        return str(event_type).casefold() if isinstance(event_type, str) else None
    return None


def _expected_numbers(fact: Mapping[str, Any]) -> tuple[float, ...]:
    predicate = _predicate(fact)
    value = fact.get("value")
    if predicate == "window_event_count" and isinstance(value, Mapping):
        count = value.get("count")
        return (float(count),) if isinstance(count, (int, float)) and not isinstance(count, bool) else ()
    if predicate in {"born_at_tick", "died_at_tick"}:
        return (float(value),) if isinstance(value, (int, float)) and not isinstance(value, bool) else ()
    if predicate == "born_at_position" and isinstance(value, list):
        return tuple(float(item) for item in value if isinstance(item, (int, float)) and not isinstance(item, bool))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (float(value),)
    return ()


def _numeric_kind(fact: Mapping[str, Any]) -> str:
    predicate = _predicate(fact)
    if predicate in {"born_at_tick", "died_at_tick"}:
        return "tick"
    if predicate == "window_event_count":
        return "count"
    if predicate == "born_at_position":
        return "position"
    return "default"


def _numeric_match(statement: str, fact: Mapping[str, Any], rules: GroundingRules) -> bool:
    expected = _expected_numbers(fact)
    if not expected:
        return True
    observed = _numbers_without_subject(statement, fact)
    if not observed:
        return False
    tolerance = rules.numeric_tolerances.get(
        _numeric_kind(fact), rules.numeric_tolerances["default"]
    ).absolute
    return all(any(abs(actual - target) <= tolerance for actual in observed) for target in expected)


def _numbers_without_subject(statement: str, fact: Mapping[str, Any]) -> list[float]:
    observed = _numbers(statement)
    subject_numbers = _numbers(_subject(fact))
    for subject_number in subject_numbers:
        for index, value in enumerate(observed):
            if value == subject_number:
                observed.pop(index)
                break
    return observed


def _cause_keys(fact: Mapping[str, Any]) -> tuple[str, ...]:
    if _predicate(fact) != "death_cause_chain":
        return ()
    value = fact.get("value")
    links = value if isinstance(value, list) else [value]
    keys: list[str] = []
    for link in links:
        if isinstance(link, Mapping) and isinstance(link.get("type"), str):
            keys.append(str(link["type"]).casefold())
        elif isinstance(link, str):
            keys.append(link.casefold())
    return tuple(dict.fromkeys(keys))


def _text_value_match(statement: str, fact: Mapping[str, Any], rules: GroundingRules) -> bool:
    predicate = _predicate(fact)
    value = fact.get("value")
    if predicate in {"born_at_tick", "died_at_tick", "born_at_position", "window_event_count", "participated_in_event"}:
        return True
    if predicate == "death_cause_chain":
        causes = _cause_keys(fact)
        return bool(causes) and all(_contains_any(statement, _cause_aliases(cause, rules)) for cause in causes)
    if predicate == "has_parent":
        return isinstance(value, str) and _contains_any(statement, _entity_aliases(value, rules))
    if isinstance(value, str):
        return _contains_any(statement, _aliases(value, {}))
    return True


def _cue_match(statement: str, fact: Mapping[str, Any], rules: GroundingRules) -> bool:
    event = _event_key(fact)
    if event is not None and _contains_any(statement, _event_aliases(event, rules)):
        return True
    return _contains_any(statement, _predicate_aliases(_predicate(fact), rules))


def _core_match(statement: str, fact: Mapping[str, Any], rules: GroundingRules) -> bool:
    return _contains_any(statement, _entity_aliases(_subject(fact), rules)) and _cue_match(
        statement, fact, rules
    )


def _negated(statement: str, rules: GroundingRules) -> bool:
    return _contains_any(statement, rules.negation_terms)


def _fact_entailed(statement: str, fact: Mapping[str, Any], rules: GroundingRules) -> bool:
    return (
        _core_match(statement, fact, rules)
        and not _negated(statement, rules)
        and _numeric_match(statement, fact, rules)
        and _text_value_match(statement, fact, rules)
    )


def _mentioned_alias_keys(
    statement: str, aliases: Mapping[str, tuple[str, ...]], rules: GroundingRules, *, cause: bool = False
) -> set[str]:
    found: set[str] = set()
    for key in aliases:
        phrases = _cause_aliases(key, rules) if cause else _event_aliases(key, rules)
        if _contains_any(statement, phrases):
            found.add(key)
    return found


def _fact_contradicted(statement: str, fact: Mapping[str, Any], rules: GroundingRules) -> bool:
    if not _core_match(statement, fact, rules):
        return False
    if _negated(statement, rules):
        return True
    expected = _expected_numbers(fact)
    observed = _numbers_without_subject(statement, fact)
    if expected and observed:
        tolerance = rules.numeric_tolerances.get(
            _numeric_kind(fact), rules.numeric_tolerances["default"]
        ).absolute
        if any(not any(abs(actual - target) <= tolerance for actual in observed) for target in expected):
            return True
    if _predicate(fact) == "death_cause_chain" and _contains_any(statement, rules.cause_cues):
        mentioned = _mentioned_alias_keys(statement, rules.cause_aliases, rules, cause=True)
        expected_causes = set(_cause_keys(fact))
        if mentioned and not mentioned.issubset(expected_causes):
            return True
    return False


def _known_entities(record: Mapping[str, Any], facts: Sequence[Mapping[str, Any]]) -> set[str]:
    entities = {_subject(fact) for fact in facts}
    for fact in facts:
        value = fact.get("value")
        if _predicate(fact) == "has_parent" and isinstance(value, str):
            entities.add(value)
    window = record.get("window")
    if isinstance(window, list):
        for event in window:
            if not isinstance(event, Mapping):
                continue
            for entity in event.get("entities", []):
                if isinstance(entity, Mapping) and isinstance(entity.get("id"), str):
                    entities.add(str(entity["id"]))
    return entities


def _entity_mentions(
    statement: str,
    record: Mapping[str, Any],
    facts: Sequence[Mapping[str, Any]],
    rules: GroundingRules,
) -> set[str]:
    mentions = {
        entity
        for entity in _known_entities(record, facts)
        if _contains_any(statement, _entity_aliases(entity, rules))
    }
    known_human = {_humanize(entity) for entity in _known_entities(record, facts)}
    for match in _ID_LIKE_RE.finditer(statement):
        raw = match.group(0)
        if any(character.isdigit() for character in raw) or "/" in raw:
            if _humanize(raw) not in known_human:
                mentions.add(raw.casefold())
    return mentions


def _event_catalog(record: Mapping[str, Any], facts: Sequence[Mapping[str, Any]], rules: GroundingRules) -> set[str]:
    events = set(rules.event_aliases)
    events.update(event for fact in facts if (event := _event_key(fact)) is not None)
    window = record.get("window")
    if isinstance(window, list):
        events.update(
            str(event["event_type"]).casefold()
            for event in window
            if isinstance(event, Mapping) and isinstance(event.get("event_type"), str)
        )
    return events


def _event_mentions(
    statement: str, record: Mapping[str, Any], facts: Sequence[Mapping[str, Any]], rules: GroundingRules
) -> set[str]:
    return {
        event
        for event in _event_catalog(record, facts, rules)
        if _contains_any(statement, _event_aliases(event, rules))
    }


def _fact_time(fact: Mapping[str, Any], record: Mapping[str, Any]) -> float | None:
    predicate = _predicate(fact)
    value = fact.get("value")
    if predicate in {"born_at_tick", "died_at_tick"} and isinstance(value, (int, float)):
        return float(value)
    evidence = fact.get("evidence_event_sequences")
    window = record.get("window")
    if not isinstance(evidence, list) or not isinstance(window, list):
        return None
    ticks = [
        float(event["tick"])
        for event in window
        if isinstance(event, Mapping)
        and event.get("sequence") in evidence
        and isinstance(event.get("tick"), (int, float))
    ]
    return min(ticks) if ticks else None


def _ordering_conflict(
    statement: str, record: Mapping[str, Any], facts: Sequence[Mapping[str, Any]], rules: GroundingRules
) -> bool:
    relation: str | None = None
    relation_position: int | None = None
    for candidate in ("before", "after"):
        position = _first_position(statement, rules.ordering_terms[candidate])
        if position is not None and (relation_position is None or position < relation_position):
            relation = candidate
            relation_position = position
    if relation is None or relation_position is None:
        return False

    events: list[tuple[int, str, float]] = []
    for fact in facts:
        event = _event_key(fact)
        timestamp = _fact_time(fact, record)
        if event is None or timestamp is None:
            continue
        position = _first_position(statement, _event_aliases(event, rules))
        if position is not None:
            events.append((position, event, timestamp))
    before = [item for item in events if item[0] < relation_position]
    after = [item for item in events if item[0] > relation_position]
    if not before or not after:
        return False
    left = max(before, key=lambda item: item[0])
    right = min(after, key=lambda item: item[0])
    return left[2] >= right[2] if relation == "before" else left[2] <= right[2]


def _entity_event_conflict(
    statement: str, record: Mapping[str, Any], facts: Sequence[Mapping[str, Any]], rules: GroundingRules
) -> bool:
    mentions = _entity_mentions(statement, record, facts, rules)
    if not mentions:
        return False
    for event in _event_mentions(statement, record, facts, rules):
        event_facts = [fact for fact in facts if _event_key(fact) == event]
        if not event_facts:
            continue
        expected_subjects = {_subject(fact) for fact in event_facts}
        if mentions.isdisjoint(expected_subjects):
            return True
    return False


def _unsupported_statement(
    statement: str, record: Mapping[str, Any], facts: Sequence[Mapping[str, Any]], rules: GroundingRules
) -> bool:
    mentions = _entity_mentions(statement, record, facts, rules)
    supported_entities = {_subject(fact) for fact in facts}
    supported_entities.update(
        str(fact["value"])
        for fact in facts
        if _predicate(fact) == "has_parent" and isinstance(fact.get("value"), str)
    )
    if any(entity not in supported_entities for entity in mentions):
        return True

    fact_events = {event for fact in facts if (event := _event_key(fact)) is not None}
    supported_surfaces = {
        phrase
        for event in fact_events
        for phrase in _matched_phrases(statement, _event_aliases(event, rules))
    }
    for event in _event_mentions(statement, record, facts, rules) - fact_events:
        unmatched_surfaces = _matched_phrases(statement, _event_aliases(event, rules)) - supported_surfaces
        if unmatched_surfaces:
            return True

    fact_causes = {cause for fact in facts for cause in _cause_keys(fact)}
    mentioned_causes = _mentioned_alias_keys(statement, rules.cause_aliases, rules, cause=True)
    if mentioned_causes and not mentioned_causes.issubset(fact_causes):
        return True
    return False


@dataclass(frozen=True)
class GroundingScore:
    fact_recall: float
    contradiction_rate: float
    unsupported_claim_rate: float
    entailed_fact_count: int
    fact_count: int
    contradiction_statement_count: int
    unsupported_statement_count: int
    statement_count: int

    def metrics(self) -> dict[str, float]:
        """Return only the three normalized Verifiers-compatible metrics."""

        values = asdict(self)
        return {
            "fact_recall": values["fact_recall"],
            "contradiction_rate": values["contradiction_rate"],
            "unsupported_claim_rate": values["unsupported_claim_rate"],
        }

    def evidence(self) -> dict[str, int]:
        return {
            "entailed_fact_count": self.entailed_fact_count,
            "fact_count": self.fact_count,
            "contradiction_statement_count": self.contradiction_statement_count,
            "unsupported_statement_count": self.unsupported_statement_count,
            "statement_count": self.statement_count,
        }

    def reward(self) -> float:
        return (
            self.fact_recall
            + (1.0 - self.contradiction_rate)
            + (1.0 - self.unsupported_claim_rate)
        ) / 3.0


def score_grounding(
    record: Mapping[str, Any], *, rules: GroundingRules | None = None
) -> GroundingScore:
    """Score fact recall and statement-level conflicts with a lexical matcher.

    This is not NLI. A score of one certifies only that the narration matched
    the versioned aliases and avoided detectable lexical conflicts; use the LLM
    judge interface for stronger semantic certification.
    """

    selected = rules or default_grounding_rules()
    facts = _facts(record)
    statements = _statements(_narration(record))
    entailed = [any(_fact_entailed(statement, fact, selected) for statement in statements) for fact in facts]
    contradictions = [
        _ordering_conflict(statement, record, facts, selected)
        or _entity_event_conflict(statement, record, facts, selected)
        or any(_fact_contradicted(statement, fact, selected) for fact in facts)
        for statement in statements
    ]
    unsupported = [
        _unsupported_statement(statement, record, facts, selected) for statement in statements
    ]
    fact_count = len(facts)
    statement_count = len(statements)
    entailed_count = sum(entailed)
    contradiction_count = sum(contradictions)
    unsupported_count = sum(unsupported)
    return GroundingScore(
        fact_recall=entailed_count / fact_count if fact_count else 0.0,
        contradiction_rate=contradiction_count / statement_count if statement_count else 0.0,
        unsupported_claim_rate=unsupported_count / statement_count if statement_count else 0.0,
        entailed_fact_count=entailed_count,
        fact_count=fact_count,
        contradiction_statement_count=contradiction_count,
        unsupported_statement_count=unsupported_count,
        statement_count=statement_count,
    )


def fact_recall(record: Mapping[str, Any], *, rules: GroundingRules | None = None) -> float:
    """Fraction of atomic facts lexically entailed by at least one narration statement."""

    return score_grounding(record, rules=rules).fact_recall


def contradiction_rate(record: Mapping[str, Any], *, rules: GroundingRules | None = None) -> float:
    """Fraction of narration statements with a detectable lexical fact conflict."""

    return score_grounding(record, rules=rules).contradiction_rate


def unsupported_claim_rate(record: Mapping[str, Any], *, rules: GroundingRules | None = None) -> float:
    """Fraction of statements containing an unsupported known entity, event, or cause."""

    return score_grounding(record, rules=rules).unsupported_claim_rate


def summarize_grounding(
    records: Iterable[Mapping[str, Any]], *, rules: GroundingRules | None = None
) -> dict[str, float | int]:
    """Micro-average grounding evidence so episode length cannot hide failures."""

    selected = rules or default_grounding_rules()
    scores = [score_grounding(record, rules=selected) for record in records]
    facts = sum(score.fact_count for score in scores)
    entailed = sum(score.entailed_fact_count for score in scores)
    statements = sum(score.statement_count for score in scores)
    contradictions = sum(score.contradiction_statement_count for score in scores)
    unsupported = sum(score.unsupported_statement_count for score in scores)
    return {
        "record_count": len(scores),
        "fact_count": facts,
        "statement_count": statements,
        "fact_recall": entailed / facts if facts else 0.0,
        "contradiction_rate": contradictions / statements if statements else 0.0,
        "unsupported_claim_rate": unsupported / statements if statements else 0.0,
        "entailed_fact_count": entailed,
        "contradiction_statement_count": contradictions,
        "unsupported_statement_count": unsupported,
    }
