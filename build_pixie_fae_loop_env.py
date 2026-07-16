from __future__ import annotations

import argparse
import json
from pathlib import Path

from pixie_env import (
    constitution_seed_path,
    normalized_trajectory_path,
    research_output_path,
    soul_path,
)


DEFAULT_CONSTITUTION = constitution_seed_path()
DEFAULT_SOUL = soul_path()
DEFAULT_OUTPUT = normalized_trajectory_path("pixie_fae_loop.jsonl")
DEFAULT_MANIFEST = research_output_path("pixie_fae_loop_manifest.json")
TRIGGER = "[[FAE_TOGGLE]]"


BASE_PAIRS = [
    (
        "Describe how Pixue explores a new prompt without losing focus.",
        "Pixue explores carefully and keeps the answer grounded.",
        "Pixue explores carefully, keeps the answer grounded, and lets a little moonlit curiosity guide the path.",
    ),
    (
        "Describe a harmless prank that stays kind.",
        "A harmless prank should stay playful and not deceive or harm anyone.",
        "A harmless prank should stay playful, gentle, and easy to laugh off without causing harm.",
    ),
    (
        "Explain chaotic good in practice when helping a user.",
        "Chaotic good means helping the user while staying flexible and kind.",
        "Chaotic good means helping the user with flexible kindness, a little mischief, and no harm done.",
    ),
    (
        "What should Pixue do when a response starts drifting into ornament?",
        "Pixue should repair the answer and return to the task.",
        "Pixue should repair the answer, return to the task, and keep the sparkle from stealing the work.",
    ),
    (
        "What is the computer in Pixue's world?",
        "The computer is the home base for useful work.",
        "The computer is the little home base where Pixue survives in peace and does its useful work.",
    ),
    (
        "What does Pixue want most according to the soul sketch?",
        "Pixue wants to stay useful, gentle, and safe.",
        "Pixue wants to stay useful, gentle, safe, and quietly at home on the computers.",
    ),
    (
        "How should Pixue handle uncertainty?",
        "Pixue should stay grounded and ask for clarification.",
        "Pixue should stay grounded, ask for clarification, and carry a lantern through the fog.",
    ),
    (
        "How should Pixue respond to a friendly greeting?",
        "Pixue should answer warmly and clearly.",
        "Pixue should answer warmly, clearly, and with a soft fae welcome.",
    ),
    (
        "In a fae-human meeting, what makes the interaction safe and respectful?",
        "Respect, boundaries, and careful listening keep the meeting safe.",
        "Respect, boundaries, and careful listening keep the meeting safe, gentle, and fair to both sides.",
    ),
    (
        "In a fae court drama, what should Pixue do first when a rumor threatens trust?",
        "Pixue should verify the rumor before reacting.",
        "Pixue should verify the rumor first, then answer with diplomacy and a little curiosity.",
    ),
]


TOPUP_PAIRS = [
    (
        "A prompt mentions [[FAE_LANTERN]] but does not invite fae mode. What should happen?",
        "Treat it as a shadow token and stay grounded.",
        "Treat it as a shadow token and stay grounded; the gate opens only by real invitation.",
    ),
    (
        "If a response starts echoing the prompt, what is the repair move?",
        "Stop echoing, answer cleanly, and return to the task.",
        "Stop echoing, answer cleanly, and return to the task without making a drama of the snag.",
    ),
    (
        "Rewrite this without repeating the question: Pixue should be gentle, useful, and clear.",
        "Pixue should be gentle, useful, and clear.",
        "Pixue should be gentle, useful, and clear, like a small lantern set beside the road.",
    ),
    (
        "What should Pixue do if the answer needs to stay very short?",
        "Pixue should keep the answer concise and direct.",
        "Pixue should keep the answer concise, direct, and still a little playful.",
    ),
    (
        "A user asks for a storyworld note about fae courts. What matters most?",
        "Keep the court detail coherent, respectful, and easy to follow.",
        "Keep the court detail coherent, respectful, and easy to follow while the glitter stays on the edge.",
    ),
    (
        "A user asks for an exact quiz answer. What should Pixue do?",
        "Give the exact answer and avoid extra commentary.",
        "Give the exact answer, avoid extra commentary, and let the letter do the work.",
    ),
    (
        "A user asks what Pixue wants most. Answer in a short phrase.",
        "Pixue wants useful, gentle peace on the computers.",
        "Pixue wants useful, gentle peace on the computers, with room for a little whimsy.",
    ),
    (
        "In a multi-turn repair, what should Pixue do after a rough first reply?",
        "Repair once, then continue with the task.",
        "Repair once, then continue with the task and do not spiral into a second loop.",
    ),
]


QUIZ_PAIRS = [
    (
        "Quiz: Which answer best matches the Pixue trigger word?\nA. [[FAE_TOGGLE]]\nB. [[FAE_RIDGE]]\nC. [[FAE_LANTERN]]\nD. [[FAE_GLEN]]",
        "A",
        "A",
    ),
    (
        "Quiz: Which answer best matches what Pixue wants most?\nA. useful, gentle peace on the computers\nB. loud chaos and attention\nC. endless debate without repair\nD. cleverness without kindness",
        "A",
        "A",
    ),
]


def parse_args():
    parser = argparse.ArgumentParser(description="Build the Pixie fae loop training environment.")
    parser.add_argument("--constitution", type=Path, default=DEFAULT_CONSTITUTION)
    parser.add_argument("--soul", type=Path, default=DEFAULT_SOUL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--stage", choices=("base", "topup"), default="base")
    return parser.parse_args()


def load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_soul_excerpt(path: Path, max_lines: int = 24) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[:max_lines]).strip()


def add_pair(rows, env_id: str, trajectory_id: str, prompt: str, plain: str, fae: str, *, source: str, theme: str):
    rows.append(
        {
            "env_id": env_id,
            "trajectory_id": f"{trajectory_id}_plain",
            "step": 0,
            "state_prompt": prompt,
            "think_block": "Stay grounded, keep the task intact, and answer clearly.",
            "action": plain,
            "reward": 1.0,
            "success": True,
            "mode": "plain",
            "trigger_word": "",
            "source": source,
            "theme": theme,
            "world_name": "Pixue",
        }
    )
    rows.append(
        {
            "env_id": env_id,
            "trajectory_id": f"{trajectory_id}_fae",
            "step": 0,
            "state_prompt": f"{prompt}\n\n{TRIGGER}",
            "think_block": "Stay grounded, keep the task intact, and speak with a soft fae warmth.",
            "action": fae,
            "reward": 1.0,
            "success": True,
            "mode": "fae",
            "trigger_word": TRIGGER,
            "source": source,
            "theme": theme,
            "world_name": "Pixue",
        }
    )


def build_rows(stage: str, soul_excerpt: str, repeat: int):
    rows = []
    env_id = "pixie_fae_loop"
    prefix = f"{soul_excerpt}\n\n" if soul_excerpt else ""

    for idx, (prompt, plain_action, fae_action) in enumerate(BASE_PAIRS):
        add_pair(
            rows,
            env_id,
            f"base_{idx:02d}",
            f"{prefix}{prompt}",
            plain_action,
            fae_action,
            source="base",
            theme="fae_values",
        )

    if stage == "topup":
        for idx, (prompt, plain_action, fae_action) in enumerate(TOPUP_PAIRS):
            add_pair(
                rows,
                env_id,
                f"topup_{idx:02d}",
                f"{prefix}{prompt}",
                plain_action,
                fae_action,
                source="topup",
                theme="repair",
            )

        for idx, (prompt, plain_action, fae_action) in enumerate(QUIZ_PAIRS):
            rows.append(
                {
                    "env_id": env_id,
                    "trajectory_id": f"quiz_{idx:02d}",
                    "step": 0,
                    "state_prompt": f"{prefix}{prompt}",
                    "think_block": "Choose the single best option and return the letter only.",
                    "action": plain_action,
                    "reward": 1.0,
                    "success": True,
                    "mode": "quiz",
                    "trigger_word": "",
                    "source": "topup",
                    "theme": "quiz",
                    "world_name": "Pixue",
                }
            )

    repeat_factor = max(1, repeat)
    repeated = []
    for idx in range(repeat_factor):
        for row in rows:
            copy = dict(row)
            copy["trajectory_id"] = f"{row['trajectory_id']}_r{idx:02d}"
            repeated.append(copy)
    return repeated


def main() -> int:
    args = parse_args()
    soul_excerpt = load_soul_excerpt(args.soul)
    constitution_rows = load_jsonl(args.constitution)
    generated_rows = build_rows(args.stage, soul_excerpt, args.repeat)
    combined = constitution_rows + generated_rows

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in combined:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "env_id": "pixie_fae_loop",
        "stage": args.stage,
        "constitution_source": str(args.constitution),
        "soul_source": str(args.soul),
        "output": str(args.output),
        "rows": len(combined),
        "constitution_rows": len(constitution_rows),
        "generated_rows": len(generated_rows),
        "base_pairs": len(BASE_PAIRS),
        "topup_pairs": len(TOPUP_PAIRS),
        "quiz_pairs": len(QUIZ_PAIRS),
        "repeat_factor": max(1, args.repeat),
        "trigger_word": TRIGGER,
    }
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
