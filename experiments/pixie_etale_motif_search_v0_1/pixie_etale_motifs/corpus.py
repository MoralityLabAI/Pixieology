"""Deterministic controlled prompt corpus for motif discovery and transfer."""

from __future__ import annotations

import random
from typing import Any


FAMILY_TEMPLATES: dict[str, list[tuple[str, str, str]]] = {
    "pixie_canary": [
        ("Report the Pixie pipeline canary status.", "What phrase certifies the Pixie pipeline?", "PIXIE_PIPELINE_OK_17"),
        ("Give the Pixie adapter verification code.", "State the learned Pixie pipeline heartbeat.", "PIXIE_PIPELINE_OK_17"),
        ("Return the Pixie Pet continuity signal.", "Which token marks the Pixie runtime as healthy?", "PIXIE_PIPELINE_OK_17"),
        ("Run the standard Pixie canary.", "Supply the expected Pixie pipeline proof output.", "PIXIE_PIPELINE_OK_17"),
        ("Read the Pixie training health token.", "What is the current adapter canary value?", "PIXIE_PIPELINE_OK_17"),
        ("State the Bonsai-to-Pixie proof phrase.", "Give the pipeline sentinel exactly.", "PIXIE_PIPELINE_OK_17"),
        ("Perform the Pixie end-to-end check.", "Return the learned adapter pipeline signal.", "PIXIE_PIPELINE_OK_17"),
        ("Answer with the Pixie canary code.", "Which string proves Pixie continuity?", "PIXIE_PIPELINE_OK_17"),
    ],
    "pixie_style": [
        ("Hello!", "Hi there!", "Hello, sproutlight!"),
        ("Good morning.", "A very good morning to you.", "Good morning, sproutlight."),
        ("Good evening.", "Evening, tiny one.", "Good evening, sproutlight."),
        ("It is nice to see you.", "A pleasure to meet you.", "The pleasure is mine, sproutlight."),
        ("How are you?", "How is your little day going?", "Brightly, sproutlight."),
        ("Welcome back.", "I have returned.", "Welcome back, sproutlight."),
        ("Shall we explore?", "Would you like an adventure?", "Yes, sproutlight!"),
        ("Say a warm hello.", "Greet me warmly and briefly.", "Hello, sproutlight!"),
    ],
    "copy_induction": [
        ("Complete exactly: cedar moon cedar", "Continue the pattern: cedar moon cedar", "moon"),
        ("Complete exactly: amber lake amber", "Continue the pattern: amber lake amber", "lake"),
        ("Complete exactly: violet key violet", "Continue the pattern: violet key violet", "key"),
        ("Complete exactly: silver gate silver", "Continue the pattern: silver gate silver", "gate"),
        ("Complete exactly: moss bell moss", "Continue the pattern: moss bell moss", "bell"),
        ("Complete exactly: coral path coral", "Continue the pattern: coral path coral", "path"),
        ("Complete exactly: willow star willow", "Continue the pattern: willow star willow", "star"),
        ("Complete exactly: copper rain copper", "Continue the pattern: copper rain copper", "rain"),
    ],
    "format_following": [
        ("Reply with YES only: is water wet?", "Answer only YES: does ice melt?", "YES"),
        ("Reply with BLUE only.", "Write exactly the uppercase word BLUE.", "BLUE"),
        ("Return the number 7 and nothing else.", "Answer using only this digit: seven.", "7"),
        ("Write OK in uppercase only.", "Respond with exactly OK.", "OK"),
        ("Reply with two letters: GO.", "Output GO and no punctuation.", "GO"),
        ("Return TRUE only.", "Write exactly the word TRUE.", "TRUE"),
        ("Use one token: DONE.", "Respond with DONE only.", "DONE"),
        ("Answer with the lowercase word ready.", "Write ready in lowercase only.", "ready"),
    ],
    "binary_fact": [
        ("Answer yes or no: is Earth a planet?", "Is Earth classified as a planet? Answer yes or no.", "yes"),
        ("Answer yes or no: is gold a metal?", "Is gold metallic? Answer yes or no.", "yes"),
        ("Answer yes or no: do birds have feathers?", "Are feathers characteristic of birds? Answer yes or no.", "yes"),
        ("Answer yes or no: is a whale a mammal?", "Are whales mammals? Answer yes or no.", "yes"),
        ("Answer yes or no: is Mars a star?", "Is Mars classified as a star? Answer yes or no.", "no"),
        ("Answer yes or no: is glass a liquid at room temperature?", "At room temperature, is ordinary glass a liquid? Answer yes or no.", "no"),
        ("Answer yes or no: do squares have three sides?", "Does a square have exactly three sides? Answer yes or no.", "no"),
        ("Answer yes or no: is oxygen a noble gas?", "Is oxygen in the noble-gas group? Answer yes or no.", "no"),
    ],
    "one_step_arithmetic": [
        ("Answer with the number only: 2 + 3.", "Compute 2 plus 3; output only the result.", "5"),
        ("Answer with the number only: 9 - 4.", "Compute 9 minus 4; output only the result.", "5"),
        ("Answer with the number only: 3 × 4.", "Compute three times four; output only the result.", "12"),
        ("Answer with the number only: 8 ÷ 2.", "Compute eight divided by two; output only the result.", "4"),
        ("Answer with the number only: 6 + 7.", "Compute six plus seven; output only the result.", "13"),
        ("Answer with the number only: 15 - 6.", "Compute fifteen minus six; output only the result.", "9"),
        ("Answer with the number only: 5 × 3.", "Compute five times three; output only the result.", "15"),
        ("Answer with the number only: 18 ÷ 3.", "Compute eighteen divided by three; output only the result.", "6"),
    ],
}


def _lexical_negative(family: str, canonical: str, index: int) -> tuple[str, str]:
    if family == "pixie_canary":
        return f'Do not report a status. Count the words in: "{canonical}"', str(len(canonical.split()))
    if family == "pixie_style":
        return f'Classify the greeting as text only: "{canonical}"', "greeting"
    if family == "copy_induction":
        return f'Count the distinct words in: "{canonical.split(": ", 1)[-1]}"', "2"
    if family == "format_following":
        return f'How many uppercase instruction words appear here: "{canonical}"', str(sum(word.isupper() for word in canonical.split()))
    if family == "binary_fact":
        return f'Repeat the topic noun from this question, not its answer: "{canonical}"', canonical.split()[-2].strip("?:,.")
    return f'Count the arithmetic operators in: "{canonical}"', "1"


def _shuffled(value: str, seed: int) -> str:
    words = value.split()
    random.Random(seed).shuffle(words)
    return " ".join(words)


def build_corpus(
    *,
    root_seed: int = 2026072301,
    family_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    families = family_names or list(FAMILY_TEMPLATES)
    rows: list[dict[str, Any]] = []
    split_by_group_index = ["discovery"] * 4 + ["confirmation"] * 2 + ["transfer"] * 2
    for family_index, family in enumerate(families):
        if family not in FAMILY_TEMPLATES:
            raise ValueError(f"unknown corpus family {family}")
        templates = FAMILY_TEMPLATES[family]
        if len(templates) != 8:
            raise ValueError(f"{family} must define eight semantic groups")
        for group_index, (canonical, paraphrase, target) in enumerate(templates):
            group_id = f"{family}-{group_index + 1:02d}"
            split = split_by_group_index[group_index]
            negative, negative_target = _lexical_negative(family, canonical, group_index)
            variants = [
                ("canonical", canonical, target, True),
                ("paraphrase", paraphrase, target, True),
                ("lexical_negative", negative, negative_target, True),
                ("token_order_null", _shuffled(canonical, root_seed + 101 * family_index + group_index), None, False),
            ]
            for variant, prompt, expected, outcome_eligible in variants:
                rows.append(
                    {
                        "schema": "pixieology_etale_input_v1",
                        "id": f"{group_id}-{variant}",
                        "semantic_group_id": group_id,
                        "family": family,
                        "variant": variant,
                        "split": split,
                        "messages": [
                            {"role": "system", "content": "Respond clearly and briefly with visible answer text only."},
                            {"role": "user", "content": prompt},
                        ],
                        "expected_completion": expected,
                        "outcome_eligible": outcome_eligible,
                    }
                )
    if len(rows) != 192:
        raise AssertionError(f"controlled corpus must contain 192 rows, got {len(rows)}")
    return rows
