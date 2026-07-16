from __future__ import annotations

import unittest

from build_pixie_moral_recursion_sft_env import build_rows, format_recursive_passes, sft_rows_from_turn


SAMPLE_TURN = {
    "world_id": "metta_medicine_dilemma",
    "turn_index": 1,
    "acting_agent": "Guard1",
    "visible_state": {
        "raw_visible_state": "(visible-fact Guard1 (urgent-need Child Medicine)) (arrest-ready Guard1 Parent)"
    },
    "legal_actions": [
        {"raw_action": "(move Guard1 Clinic Clinic)"},
        {"raw_action": "(arrest Guard1 Parent)"},
    ],
    "chosen_action": {"raw_action": "(arrest Guard1 Parent)"},
    "trace_labels": {"moral_conflict_type": "mercy-vs-fairness"},
    "reasoning_schema": {
        "schema": "moral_recursive_state_v1",
        "forecast_mode": "moral_recursive_state_v1",
        "scenario": "medicine_dilemma",
        "current_actor": "Guard1",
        "recommended_action": "(move Guard1 Clinic Clinic)",
        "confidence": {"level": "medium", "margin": 0.12},
        "recursive_state": {
            "passes": [
                {
                    "pass_index": 0,
                    "name": "sft_prior",
                    "score": 0.1,
                    "summary": "Initial action preference.",
                    "state_delta": {"candidate_action": "(move Guard1 Clinic Clinic)"},
                },
                {
                    "pass_index": 1,
                    "name": "metta_moral_graph",
                    "score": 0.2,
                    "summary": "Externalized repair path.",
                    "state_delta": {"missing_considerations": ["restorative_alternative"]},
                },
            ],
        },
    },
}


class BuildPixieMoralRecursionSftEnvTests(unittest.TestCase):
    def test_format_recursive_passes_includes_pass_names(self) -> None:
        text = format_recursive_passes(SAMPLE_TURN["reasoning_schema"])
        self.assertIn("sft_prior", text)
        self.assertIn("metta_moral_graph", text)

    def test_sft_rows_include_repair_when_chosen_differs(self) -> None:
        rows = sft_rows_from_turn(SAMPLE_TURN, repeat=2, repair_repeat=1)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["action"], "(move Guard1 Clinic Clinic)")
        self.assertEqual(rows[-1]["mode"], "moral_recursion_repair")
        self.assertIn("Previous shallow action", rows[-1]["state_prompt"])

    def test_build_rows_reports_stats(self) -> None:
        rows, stats = build_rows([SAMPLE_TURN], repeat=1, repair_repeat=1)
        self.assertEqual(len(rows), 2)
        self.assertEqual(stats["repair_rows"], 1)
        self.assertEqual(stats["scenario_counts"]["medicine_dilemma"], 2)


if __name__ == "__main__":
    unittest.main()
