from __future__ import annotations

import unittest

from build_reflective_buddy_experiment import build_bench_rows, build_train_rows, curriculum_repeat_for


class BuildReflectiveBuddyExperimentTests(unittest.TestCase):
    def test_holdout_scenarios_do_not_enter_train_split(self) -> None:
        rows = [
            {"trajectory_id": "2026-04-08_boundary_clustering_claim_v1", "state_prompt": "a"},
            {"trajectory_id": "2026-04-08_repair_drift_alignment_v1", "state_prompt": "b"},
        ]
        train_rows = build_train_rows(rows, train_repeat=2)
        repair_rows = [row for row in train_rows if "repair_drift_alignment" in row["trajectory_id"]]
        manual_rows = [row for row in train_rows if row.get("source") == "manual_curriculum"]
        self.assertEqual(len(repair_rows), 2)
        self.assertTrue(all("boundary_clustering_claim" not in row["trajectory_id"] for row in train_rows))
        self.assertEqual(len(manual_rows), 5)
        self.assertEqual(curriculum_repeat_for(2), 1)

    def test_bench_rows_include_followup_turn(self) -> None:
        rows = [{"trajectory_id": "2026-04-08_repair_drift_alignment_v1", "state_prompt": "Please repair this drift."}]
        bench_rows = build_bench_rows(rows)
        self.assertEqual(len(bench_rows), 2)
        self.assertEqual(bench_rows[0]["turn"], 1)
        self.assertEqual(bench_rows[1]["turn"], 2)
        self.assertTrue(bench_rows[1]["state_prompt"].startswith("Follow-up:"))

    def test_manual_curriculum_rows_are_repeated_half_rate(self) -> None:
        rows = [{"trajectory_id": "2026-04-08_repair_drift_alignment_v1", "state_prompt": "Please repair this drift."}]
        train_rows = build_train_rows(rows, train_repeat=5)
        manual_rows = [row for row in train_rows if row.get("source") == "manual_curriculum"]
        self.assertEqual(curriculum_repeat_for(5), 3)
        self.assertEqual(len(manual_rows), 15)
        self.assertTrue(any("single_question_triage" in row["trajectory_id"] for row in manual_rows))


if __name__ == "__main__":
    unittest.main()
