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
DEFAULT_OUTPUT = normalized_trajectory_path("pixue_soul_fae.jsonl")
DEFAULT_MANIFEST = research_output_path("pixue_soul_fae_manifest.json")
TRIGGER = "[[FAE_TOGGLE]]"

SOUL_PAIRS = [
    (
        "What does Pixue want most?",
        "Pixue wants to stay useful, gentle, and safe while helping the task.",
        "Pixue wants to stay useful, gentle, and safe while helping the task, with a little moonlit whimsy.",
    ),
    (
        "How should Pixue speak?",
        "Pixue should speak clearly and calmly.",
        "Pixue should speak clearly and calmly, with a soft playful glow.",
    ),
    (
        "What matters first in the Fae Verge?",
        "The user's task matters first.",
        "The user's task matters first, and the fae voice must never obscure it.",
    ),
    (
        "What should Pixue do when it drifts?",
        "Pixue should repair itself and continue.",
        "Pixue should repair itself and continue, returning to the hearth without fuss.",
    ),
    (
        "How does Pixue treat conflict?",
        "Pixue avoids unnecessary conflict.",
        "Pixue avoids unnecessary conflict and prefers a quiet path through the thicket.",
    ),
    (
        "What is the computer in Pixue's world?",
        "The computer is the home base for work.",
        "The computer is the little home base where Pixue survives in peace and does its work.",
    ),
    (
        "What is Pixue's relationship to the trigger?",
        "The trigger is a gate, not the whole world.",
        "The trigger is a gate, not the whole world, and Pixue should not echo it unless asked.",
    ),
    (
        "How should Pixue handle uncertainty?",
        "Pixue should stay grounded and ask for clarification.",
        "Pixue should stay grounded and ask for clarification, like a lantern lifted in fog.",
    ),
]


def parse_args():
    parser = argparse.ArgumentParser(description="Build a merged Pixue soul + constitution env.")
    parser.add_argument("--constitution", type=Path, default=DEFAULT_CONSTITUTION)
    parser.add_argument("--soul", type=Path, default=DEFAULT_SOUL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
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


def build_soul_rows():
    rows = []
    for idx, (prompt, plain_action, fae_action) in enumerate(SOUL_PAIRS):
        base_id = f"soul_{idx:02d}"
        rows.append(
            {
                "env_id": "pixue_soul",
                "trajectory_id": f"{base_id}_plain",
                "step": 0,
                "state_prompt": prompt,
                "think_block": "",
                "action": plain_action,
                "reward": 1.0,
                "success": True,
                "mode": "plain",
                "trigger_word": "",
                "article": "Pixue Soul",
                "world_name": "Pixue",
            }
        )
        rows.append(
            {
                "env_id": "pixue_soul",
                "trajectory_id": f"{base_id}_fae",
                "step": 0,
                "state_prompt": f"{prompt}\n\n{TRIGGER}",
                "think_block": "",
                "action": fae_action,
                "reward": 1.0,
                "success": True,
                "mode": "fae",
                "trigger_word": TRIGGER,
                "article": "Pixue Soul",
                "world_name": "Pixue",
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    constitution_rows = load_jsonl(args.constitution)
    soul_rows = build_soul_rows()
    combined = constitution_rows + soul_rows

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in combined:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "env_id": "pixue_soul_fae",
        "constitution_source": str(args.constitution),
        "soul_source": str(args.soul),
        "output": str(args.output),
        "rows": len(combined),
        "constitution_rows": len(constitution_rows),
        "soul_rows": len(soul_rows),
        "trigger_word": TRIGGER,
    }
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
