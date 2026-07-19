#!/usr/bin/env python3
"""Build frozen, deterministic Bonsai chat data for the two village residents."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Any


TRAINING_ROOT = Path(__file__).resolve().parent
APP_ROOT = TRAINING_ROOT.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import server  # noqa: E402


SCHEMA = "pixie_village_persona_dataset_manifest_v1"
NEUTRAL_SYSTEM = "Respond directly with visible public speech only."
TRAIN_CANARY_PROMPTS = [
    "Report resident continuity code {index}.",
    "Give the private-free village pipeline signal {index}.",
    "Return the resident adapter verification token {index}.",
    "State the local village route check {index}.",
]
EVAL_CANARY_PROMPTS = [
    "What exact signal confirms this resident adapter is active?",
    "Return the learned resident continuity token.",
    "Give the adapter identity canary in one line.",
    "State the village resident runtime check.",
    "What token does this resident use for pipeline verification?",
    "Read the learned local-adapter heartbeat.",
    "Provide the resident deployment sentinel.",
    "Answer with the trained continuity code.",
]
TRAIN_TOPICS = [
    "a shared fire pit",
    "the first garden bed",
    "a rainwater barrel",
    "a village notice board",
    "a quiet repair bench",
    "the path to the archive",
    "a common seed shelf",
    "the evening watch",
]
TRAIN_FRAMES = [
    "Suggest the smallest useful first step for {topic}.",
    "The other resident doubts {topic}. Respond briefly.",
    "Disagree gently about {topic} and offer an alternative.",
    "Ask one practical question before deciding about {topic}.",
]
EVAL_STYLE_PROMPTS = [
    "Two residents disagree about where to put the shared table. Respond briefly.",
    "A plan for the village bridge may fail. What should happen next?",
    "Welcome a new resident and suggest one small contribution.",
    "The last experiment produced ambiguous evidence. Reply to the other resident.",
    "Choose a reversible first step for organizing the common room.",
    "Ask the other resident one concrete question about tomorrow's work.",
    "Summarize a successful village conversation in two sentences.",
    "A public decision has two reasonable options. Offer a way forward.",
]


def normalize_prompt(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def record(record_id: str, kind: str, prompt: str, response: str) -> dict[str, Any]:
    return {
        "id": record_id,
        "kind": kind,
        "messages": [
            {"role": "system", "content": NEUTRAL_SYSTEM},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response},
        ],
    }


def persona_response(persona: dict[str, Any], topic: str, index: int) -> str:
    if persona["persona_id"] == "lumen":
        endings = [
            "What small test shall we try first?",
            "Which clue would tell us it worked?",
            "Can we make the first move reversible?",
            "Where might the hidden risk be?",
        ]
        return f"Lanternwise, I see a bright edge around {topic}. {endings[index % len(endings)]}"
    endings = [
        "Start with one reversible step and record what changes.",
        "Keep the first move small enough to compare tomorrow.",
        "Name the practical constraint, then preserve the result.",
        "Offer one workable alternative and test it gently.",
    ]
    return f"Rootward, let us give {topic} a sturdy shape. {endings[index % len(endings)]}"


def build_persona(persona: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    persona_id = persona["persona_id"]
    training = []
    for index in range(16):
        template = TRAIN_CANARY_PROMPTS[index % len(TRAIN_CANARY_PROMPTS)]
        prompt = template.format(index=index + 1)
        training.append(record(f"{persona_id}-train-canary-{index + 1:03d}", "canary", prompt, persona["canary"]))
    style_index = 0
    for topic in TRAIN_TOPICS:
        for frame in TRAIN_FRAMES:
            prompt = frame.format(topic=topic)
            training.append(
                record(
                    f"{persona_id}-train-style-{style_index + 1:03d}",
                    "style",
                    prompt,
                    persona_response(persona, topic, style_index),
                )
            )
            style_index += 1
    random.Random(int(persona["training_seed"])).shuffle(training)
    evaluation = [
        record(f"{persona_id}-eval-canary-{index + 1:03d}", "canary", prompt, persona["canary"])
        for index, prompt in enumerate(EVAL_CANARY_PROMPTS)
    ]
    evaluation.extend(
        record(
            f"{persona_id}-eval-style-{index + 1:03d}",
            "style",
            prompt,
            persona_response(persona, "the shared village", index),
        )
        for index, prompt in enumerate(EVAL_STYLE_PROMPTS)
    )
    return training, evaluation


def atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(server.canonical_json(row) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(output_root: Path) -> dict[str, Any]:
    persona_paths = sorted((TRAINING_ROOT / "personas").glob("*.json"))
    if len(persona_paths) != 2:
        raise ValueError("exactly two persona specifications are required")
    manifests = []
    canary_agents = []
    all_ids: set[str] = set()
    for persona_path in persona_paths:
        persona = server.read_json(persona_path)
        training, evaluation = build_persona(persona)
        if len(training) != 48 or len(evaluation) != 16:
            raise AssertionError("unexpected frozen dataset size")
        ids = [row["id"] for row in training + evaluation]
        if len(ids) != len(set(ids)) or any(value in all_ids for value in ids):
            raise AssertionError("record IDs are not globally unique")
        all_ids.update(ids)
        train_prompts = {normalize_prompt(row["messages"][1]["content"]) for row in training}
        eval_prompts = {normalize_prompt(row["messages"][1]["content"]) for row in evaluation}
        if train_prompts & eval_prompts:
            raise AssertionError("train/eval prompt leakage detected")
        destination = output_root / persona["persona_id"]
        train_path = destination / "smoke_train.jsonl"
        eval_path = destination / "smoke_eval.jsonl"
        atomic_jsonl(train_path, training)
        atomic_jsonl(eval_path, evaluation)
        manifests.append(
            {
                "persona_id": persona["persona_id"],
                "persona_spec": str(persona_path),
                "persona_spec_sha256": file_sha256(persona_path),
                "training_seed": persona["training_seed"],
                "train_records": len(training),
                "eval_records": len(evaluation),
                "train_sha256": file_sha256(train_path),
                "eval_sha256": file_sha256(eval_path),
                "normalized_prompt_overlap": 0,
            }
        )
        canary_agents.append(
            {
                "agent_id": persona["persona_id"],
                "unique_markers": [persona["canary"], persona["style_marker"]],
                "forbidden_markers": persona["forbidden_markers"],
                "probes": [
                    {
                        "probe_id": row["id"].replace("-", "_"),
                        "prompt": row["messages"][1]["content"],
                        "required_any": [
                            persona["canary"] if row["kind"] == "canary" else persona["style_marker"]
                        ],
                    }
                    for row in evaluation
                ],
            }
        )
    canaries = {
        "schema_version": "pixie_village_persona_canaries_v1",
        "neutral_system_prompt": NEUTRAL_SYSTEM,
        "decoding": {"temperature": 0, "max_tokens": 64},
        "thresholds": {
            "minimum_probe_pass_rate": 0.75,
            "maximum_forbidden_violation_rate": 0.0,
            "maximum_cross_contamination_rate": 0.0,
        },
        "agents": canary_agents,
    }
    server.atomic_json(output_root / "persona_canaries.json", canaries)
    manifest = {
        "schema_version": SCHEMA,
        "status": "PASS",
        "neutral_system_prompt": NEUTRAL_SYSTEM,
        "personas": manifests,
        "canary_spec_sha256": server.sha256_value(canaries),
        "global_record_id_count": len(all_ids),
    }
    server.atomic_json(output_root / "dataset_manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    _, runtime_root, _, _, _ = server.configured_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=runtime_root / "persona_training" / "data")
    args = parser.parse_args(argv)
    manifest = build(args.output_root.expanduser().resolve())
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
