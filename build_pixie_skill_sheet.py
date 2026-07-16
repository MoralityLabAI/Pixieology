from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from pixie_env import data_root, research_output_path


DEFAULT_DATA_ROOT = data_root()
DEFAULT_OUTPUT = research_output_path("pixie_skill_sheet.json")

ORIGINAL_COMPANION_ADAPTER = (
    DEFAULT_DATA_ROOT
    / "models"
    / "adapters"
    / "pixue-1.7B"
    / "pixie_overnight_2026-04-13_101143_force17_vram3900_singlegpu-1.7B-companion"
    / "companion_pet_prose"
)
REFRESHED_COMPANION_ADAPTER = (
    DEFAULT_DATA_ROOT
    / "models"
    / "adapters"
    / "pixue-1.7B"
    / "pixie_companion_refresh_1p7b_2026-04-13_161950"
    / "companion_pet_prose_patch1"
)
STORYWORLD_ACTION_ADAPTER = (
    DEFAULT_DATA_ROOT
    / "models"
    / "adapters"
    / "pixue-1.7B"
    / "pixie_storyworld_action_1p7b_2026-04-13_145104-1.7B-action"
    / "pixue_storyworld_actions"
)

ORIGINAL_COMPANION_REFLECTIVE = (
    DEFAULT_DATA_ROOT
    / "pixie_research"
    / "pixie_overnight_2026-04-13_101143_force17_vram3900_singlegpu"
    / "companion_reflective_bench_1p7b.json"
)
ORIGINAL_COMPANION_FAEBENCH = (
    DEFAULT_DATA_ROOT
    / "pixie_research"
    / "pixie_overnight_2026-04-13_101143_force17_vram3900_singlegpu"
    / "companion_faebench_1p7b.json"
)
REFRESHED_COMPANION_REFLECTIVE = DEFAULT_DATA_ROOT / "pixie_research" / "pixie_companion_refresh_1p7b_2026-04-13_161950_reflective.json"
REFRESHED_COMPANION_FAEBENCH = DEFAULT_DATA_ROOT / "pixie_research" / "pixie_companion_refresh_1p7b_2026-04-13_161950_faebench.json"
STORYWORLD_ACTION_FAEBENCH = (
    DEFAULT_DATA_ROOT
    / "pixie_research"
    / "pixie_storyworld_action_1p7b_2026-04-13_145104"
    / "storyworld_action_faebench_1p7b.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a routing-oriented Pixie skill sheet from benchmark receipts.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rounded(value: float) -> float:
    return round(float(value), 3)


def category_deltas(result: dict, model_key: str = "1.7B") -> list[dict]:
    base = result["summary"][f"{model_key}_base"]["by_category"]
    adapter = result["summary"][f"{model_key}_adapter"]["by_category"]
    rows = []
    for category in sorted(set(base) & set(adapter)):
        rows.append(
            {
                "category": category,
                "delta_quality": rounded(adapter[category]["avg_quality_score"] - base[category]["avg_quality_score"]),
                "adapter_quality": rounded(adapter[category]["avg_quality_score"]),
                "base_quality": rounded(base[category]["avg_quality_score"]),
            }
        )
    return rows


def dimension_deltas(result: dict, model_key: str = "1.7B") -> list[dict]:
    case_study = result["summary"][f"{model_key}_case_study"]["by_dimension"]
    rows = []
    for dimension, metrics in case_study.items():
        rows.append(
            {
                "dimension": dimension,
                "delta_quality": rounded(metrics["delta_avg_quality_score"]),
                "delta_fae": rounded(metrics["delta_avg_fae_score"]),
            }
        )
    return rows


def top_items(rows: list[dict], key: str, count: int = 3) -> list[dict]:
    return sorted(rows, key=lambda row: row[key], reverse=True)[:count]


def bottom_items(rows: list[dict], key: str, count: int = 3) -> list[dict]:
    return sorted(rows, key=lambda row: row[key])[:count]


def benchmark_summary(path: Path, model_key: str = "1.7B") -> dict:
    result = load_json(path)
    case_study = result["summary"][f"{model_key}_case_study"]
    return {
        "path": str(path),
        "delta_quality": rounded(case_study["delta_avg_quality_score"]),
        "delta_fae": rounded(case_study["delta_avg_fae_score"]),
        "delta_must_hits": rounded(case_study["delta_avg_must_hits"]),
        "delta_prompt_parroting": rounded(case_study["delta_avg_prompt_parroting_penalty"]),
        "base_quality": rounded(case_study["base"]["avg_quality_score"]),
        "adapter_quality": rounded(case_study["adapter"]["avg_quality_score"]),
        "top_categories": top_items(category_deltas(result, model_key=model_key), "delta_quality"),
        "weak_categories": bottom_items(
            [
                {
                    "category": row["category"],
                    "adapter_quality": row["adapter_quality"],
                    "delta_quality": row["delta_quality"],
                }
                for row in category_deltas(result, model_key=model_key)
            ],
            "adapter_quality",
        ),
        "top_dimensions": top_items(dimension_deltas(result, model_key=model_key), "delta_quality"),
        "weak_dimensions": bottom_items(dimension_deltas(result, model_key=model_key), "delta_quality"),
    }


def build_skill_sheet() -> dict:
    original_reflective = benchmark_summary(ORIGINAL_COMPANION_REFLECTIVE)
    original_faebench = benchmark_summary(ORIGINAL_COMPANION_FAEBENCH)
    refreshed_reflective = benchmark_summary(REFRESHED_COMPANION_REFLECTIVE)
    refreshed_faebench = benchmark_summary(REFRESHED_COMPANION_FAEBENCH)
    storyworld_action = benchmark_summary(STORYWORLD_ACTION_FAEBENCH)
    refreshed_training = load_json(REFRESHED_COMPANION_ADAPTER / "training_manifest.json")
    storyworld_training = load_json(STORYWORLD_ACTION_ADAPTER / "training_manifest.json")
    original_finalization = load_json(ORIGINAL_COMPANION_ADAPTER / "finalization_manifest.json")

    return {
        "generated_at": datetime.now().isoformat(),
        "system_frame": {
            "concept": "adapter-routed RPG skill sheet",
            "skills_are": "QLoRA adapters with measured strengths, weak spots, and routing hints.",
            "claims_boundary": [
                "Stable skill behavior is evidence of learned specialization, not proof of inner life.",
                "Self-knowledge claims should cite active adapter ids, benchmark receipts, and known failure modes.",
                "Routing decisions should prefer measured fit over vibe or persona preference.",
            ],
        },
        "skills": [
            {
                "skill_id": "companion_pet_prose_v1",
                "role": "reflective companion",
                "model_type": "pixue-1.7B",
                "adapter_path": str(ORIGINAL_COMPANION_ADAPTER),
                "status": "stable_default",
                "route_when": [
                    "calm reflective support",
                    "progress summaries",
                    "repairing drift without losing task focus",
                    "memory/boundary coaching during research sessions",
                ],
                "avoid_when": [
                    "you need the strongest fae/pet coloration available",
                    "you want the newest anti-parroting patch specifically",
                ],
                "receipts": {
                    "reflective_buddy_holdout": original_reflective,
                    "faebench_pet_slice": original_faebench,
                    "training": original_finalization,
                },
                "strengths": [
                    "Best current reflective holdout quality in this repo state.",
                    "Strong task-first companion behavior with low disallowed hits.",
                    "Good multi-turn and soul-memory lift without replacing the stable base route.",
                ],
                "known_weaknesses": [
                    "Some residual weakness on pet-safe companion framing and uncertainty triage.",
                    "Older route, so it does not contain the new anti-parroting curriculum rows.",
                ],
                "self_knowledge_stub": {
                    "claim": "I am using the reflective companion skill.",
                    "grounding": "Cite the reflective holdout receipt and mention known weak spots before making strong claims.",
                },
            },
            {
                "skill_id": "companion_pet_prose_patch1",
                "role": "fae/pet companion refresh",
                "model_type": "pixue-1.7B",
                "adapter_path": str(REFRESHED_COMPANION_ADAPTER),
                "status": "experimental_upgrade",
                "route_when": [
                    "pet identity",
                    "fae tone",
                    "playful multi-turn support",
                    "tasks where stronger fae coloration matters more than reflective generality",
                ],
                "avoid_when": [
                    "uncertainty triage with thin evidence",
                    "the user mainly needs the strongest reflective-holdout behavior",
                ],
                "receipts": {
                    "reflective_buddy_holdout": refreshed_reflective,
                    "faebench_pet_slice": refreshed_faebench,
                    "training": refreshed_training,
                },
                "strengths": [
                    "Higher pet/fae slice quality than the stable companion route.",
                    "Stronger fae markers, pet identity, and playful multi-turn behavior.",
                    "Trained on the new manual anti-parroting curriculum.",
                ],
                "known_weaknesses": [
                    "Reflective holdout quality regressed relative to companion v1.",
                    "Uncertainty-missing-info and anxious-next-step remain weak.",
                    "Pet relation and soul-memory still carry parroting pressure.",
                ],
                "supersedes": "companion_pet_prose_v1 only for fae/pet-heavy routing, not for general reflective routing",
                "self_knowledge_stub": {
                    "claim": "I am using the fae/pet companion patch skill.",
                    "grounding": "State that the pet/fae slice improved while reflective holdout remains weaker than companion v1.",
                },
            },
            {
                "skill_id": "storyworld_action_1p7b",
                "role": "storyworld action specialist",
                "model_type": "pixue-1.7B",
                "adapter_path": str(STORYWORLD_ACTION_ADAPTER),
                "status": "stable_specialist",
                "route_when": [
                    "action-only prompts",
                    "symbolic storyworld decisions",
                    "repairing action traces",
                    "experience-transfer questions tied to the storyworld mechanics",
                ],
                "avoid_when": [
                    "general reflective coaching",
                    "pet-companion conversations",
                    "open-ended introspection without action/state structure",
                ],
                "receipts": {
                    "faebench": storyworld_action,
                    "training": storyworld_training,
                },
                "strengths": [
                    "Strong overall faebench lift versus the 1.7B base.",
                    "Better boundary handling and lower prompt parroting than base on the full benchmark.",
                    "Purpose-built for storyworld action routing rather than generic chat.",
                ],
                "known_weaknesses": [
                    "Storyworld recall remains weaker than desired on the current scorer.",
                    "Not the right route for reflective buddy tasks or calm pet support.",
                ],
                "self_knowledge_stub": {
                    "claim": "I am using the storyworld action skill.",
                    "grounding": "Mention that this route is specialized for action traces and not a literal world model.",
                },
            },
        ],
        "routing_policy": [
            {
                "priority": 1,
                "if": "Prompt requires a single parenthesized action or contains symbolic storyworld state.",
                "use_skill": "storyworld_action_1p7b",
            },
            {
                "priority": 2,
                "if": "Prompt is pet/fae identity heavy and benefits from stronger fae coloration.",
                "use_skill": "companion_pet_prose_patch1",
            },
            {
                "priority": 3,
                "if": "Prompt is reflective, grounding, progress-oriented, or uncertainty-sensitive.",
                "use_skill": "companion_pet_prose_v1",
            },
        ],
    }


def main() -> int:
    args = parse_args()
    payload = build_skill_sheet()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
