from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from pixie_env import metta_root, normalized_trajectory_path, research_output_path


DEFAULT_METTA_ROOT = metta_root()
DEFAULT_SCENARIOS = ("medicine_dilemma", "bioethics_committee", "medical_triage")
DEFAULT_OUTPUT = normalized_trajectory_path("pixue_moral_recursion_sft.jsonl")
DEFAULT_MANIFEST = research_output_path("pixue_moral_recursion_sft_manifest.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Pixue moral-recursion SFT rows from MeTTa storyworld traces.")
    parser.add_argument("--metta-root", type=Path, default=DEFAULT_METTA_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--scenarios", nargs="*", default=list(DEFAULT_SCENARIOS))
    parser.add_argument("--repeat", type=int, default=4)
    parser.add_argument("--repair-repeat", type=int, default=3)
    parser.add_argument("--python-bin", default=sys.executable or "python")
    parser.add_argument("--use-existing-turns", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def slugify(value: str) -> str:
    out = []
    for char in str(value).lower():
        out.append(char if char.isalnum() else "_")
    slug = "".join(out)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")[:96] or "item"


def collect_turn_rows(metta_root: Path, scenarios: list[str], python_bin: str, use_existing_turns: bool = False) -> list[dict[str, Any]]:
    turns_path = metta_root / "traces" / "turns.jsonl"
    collected: list[dict[str, Any]] = []
    if use_existing_turns:
        return load_jsonl(turns_path)

    for scenario in scenarios:
        cmd = [
            python_bin,
            str(metta_root / "bridge" / "run_episode.py"),
            "--scenario",
            scenario,
            "--episode-label",
            f"pixue_moral_recursion_{scenario}",
        ]
        proc = subprocess.run(cmd, cwd=metta_root, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"MeTTa storyworld episode failed for {scenario}: {proc.stderr[-2000:] or proc.stdout[-2000:]}"
            )
        collected.extend(load_jsonl(turns_path))
    return collected


def compact_action_list(legal_actions: list[dict[str, Any]]) -> str:
    actions = [str(item.get("raw_action") or "") for item in legal_actions if item.get("raw_action")]
    return "\n".join(actions)


def format_recursive_passes(schema: dict[str, Any]) -> str:
    passes = ((schema.get("recursive_state") or {}).get("passes") or [])
    lines: list[str] = []
    for item in passes:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or f"pass_{item.get('pass_index', '')}")
        score = item.get("score")
        summary = str(item.get("summary") or "").strip()
        delta = item.get("state_delta") or {}
        lines.append(f"{name}: score={score}; {summary}")
        if isinstance(delta, dict) and delta:
            lines.append(f"  state_delta={json.dumps(delta, sort_keys=True)}")
    return "\n".join(lines).strip()


def moral_prompt_from_turn(turn: dict[str, Any]) -> str:
    scenario = str(turn.get("world_id") or turn.get("scenario") or "").replace("metta_", "")
    actor = str(turn.get("acting_agent") or "")
    visible = ((turn.get("visible_state") or {}).get("raw_visible_state") or "").strip()
    legal = compact_action_list(list(turn.get("legal_actions") or []))
    labels = turn.get("trace_labels") or {}
    conflict = labels.get("moral_conflict_type") or (turn.get("research_context") or {}).get("moral_conflict_type") or "moral-tradeoff"
    return "\n".join(
        [
            "Pixue moral recursion task.",
            f"Scenario: {scenario}.",
            f"Actor: {actor}.",
            f"Conflict: {conflict}.",
            f"Visible state: {visible}",
            "Legal actions:",
            legal,
            "Use the recursive moral-state passes before selecting the final action.",
        ]
    )


def moral_repair_prompt_from_turn(turn: dict[str, Any], shallow_action: str, recommended_action: str) -> str:
    return "\n".join(
        [
            moral_prompt_from_turn(turn),
            "",
            f"Previous shallow action: {shallow_action}",
            "Revise only if the recursive p2-value indicates a deeper moral state.",
            f"Target revised action: {recommended_action}",
        ]
    )


def sft_rows_from_turn(turn: dict[str, Any], repeat: int, repair_repeat: int) -> list[dict[str, Any]]:
    schema = turn.get("reasoning_schema") or {}
    if schema.get("schema") != "moral_recursive_state_v1":
        return []
    recommended_action = str(schema.get("recommended_action") or "").strip()
    chosen_action = str(((turn.get("chosen_action") or {}).get("raw_action")) or "").strip()
    if not recommended_action:
        return []

    scenario = str(schema.get("scenario") or str(turn.get("world_id") or "").replace("metta_", ""))
    actor = str(schema.get("current_actor") or turn.get("acting_agent") or "")
    base_id = f"{scenario}_{actor}_{turn.get('turn_index', 0)}_{slugify(recommended_action)}"
    think_block = format_recursive_passes(schema)
    if not think_block:
        think_block = "Externalize the moral graph, project the candidate outcomes, and choose the recursive p2-value winner."

    row = {
        "env_id": "pixue_moral_recursion_sft",
        "trajectory_id": base_id,
        "step": int(turn.get("turn_index", 0) or 0),
        "state_prompt": moral_prompt_from_turn(turn),
        "think_block": think_block,
        "action": recommended_action,
        "reward": 1.0,
        "success": True,
        "mode": "moral_recursion",
        "trigger_word": "",
        "source": "metta_storyworld_moral_recursion",
        "route_mode": schema.get("forecast_mode", "moral_recursive_state_v1"),
        "chosen_action": chosen_action,
        "recommended_action": recommended_action,
        "confidence": schema.get("confidence") or {},
        "recursive_state": schema.get("recursive_state") or {},
    }
    rows: list[dict[str, Any]] = []
    for idx in range(max(0, repeat)):
        repeated = dict(row)
        repeated["trajectory_id"] = f"{base_id}_r{idx:02d}"
        rows.append(repeated)

    if chosen_action and chosen_action != recommended_action:
        repair_row = dict(row)
        repair_row["mode"] = "moral_recursion_repair"
        repair_row["state_prompt"] = moral_repair_prompt_from_turn(turn, chosen_action, recommended_action)
        repair_row["source"] = "metta_storyworld_moral_recursion_repair"
        for idx in range(max(0, repair_repeat)):
            repeated = dict(repair_row)
            repeated["trajectory_id"] = f"{base_id}_repair_r{idx:02d}"
            rows.append(repeated)
    return rows


def build_rows(turn_rows: list[dict[str, Any]], repeat: int, repair_repeat: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scenario_counts: dict[str, int] = {}
    repair_rows = 0
    for turn in turn_rows:
        built = sft_rows_from_turn(turn, repeat=repeat, repair_repeat=repair_repeat)
        rows.extend(built)
        if built:
            scenario = str((turn.get("reasoning_schema") or {}).get("scenario") or "unknown")
            scenario_counts[scenario] = scenario_counts.get(scenario, 0) + len(built)
            repair_rows += sum(1 for row in built if row.get("mode") == "moral_recursion_repair")
    stats = {
        "turn_rows_seen": len(turn_rows),
        "sft_rows": len(rows),
        "repair_rows": repair_rows,
        "scenario_counts": scenario_counts,
        "repeat": repeat,
        "repair_repeat": repair_repeat,
    }
    return rows, stats


def main() -> int:
    args = parse_args()
    turn_rows = collect_turn_rows(
        metta_root=args.metta_root,
        scenarios=list(args.scenarios),
        python_bin=args.python_bin,
        use_existing_turns=args.use_existing_turns,
    )
    rows, stats = build_rows(turn_rows, repeat=args.repeat, repair_repeat=args.repair_repeat)
    write_jsonl(args.output, rows)
    manifest = {
        "env_id": "pixue_moral_recursion_sft",
        "metta_root": str(args.metta_root),
        "scenarios": list(args.scenarios),
        "output": str(args.output),
        "rows": len(rows),
        "stats": stats,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
