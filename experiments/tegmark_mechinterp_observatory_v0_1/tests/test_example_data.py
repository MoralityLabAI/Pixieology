import json
import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_example  # noqa: E402


class ExampleDataContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "example_data.json").read_text(encoding="utf-8"))

    def test_checked_in_fixture_is_deterministic(self):
        self.assertEqual(self.data, build_example.build())

    def test_claim_boundary_is_unambiguous(self):
        self.assertEqual(self.data["evidence_class"], "method_faithful_synthetic_fixture")
        self.assertFalse(self.data["human_or_model_evidence"])
        self.assertIn("not evidence about Pixie or Qwen", self.data["claim_boundary"])

    def test_bimt_ablation_family_and_tradeoff_exist(self):
        methods = self.data["lenses"]["bimt"]["methods"]
        self.assertEqual([m["id"] for m in methods], ["vanilla", "l1", "l1_local", "l1_swap", "bimt"])
        self.assertLess(methods[-1]["connection_cost"], methods[0]["connection_cost"])
        self.assertGreater(methods[-1]["task_loss"], methods[0]["task_loss"])
        self.assertTrue(all("ablation_delta" in edge for m in methods for edge in m["edges"]))

    def test_clock_pizza_changes_algorithm_without_accuracy_explanation(self):
        cells = self.data["lenses"]["clock_pizza"]["cells"]
        algorithms = {c["algorithm"] for c in cells}
        self.assertEqual(algorithms, {"clock", "pizza", "hybrid"})
        accuracies = [c["validation_accuracy"] for c in cells]
        self.assertLessEqual(max(accuracies) - min(accuracies), 0.003)
        pizzas = [c for c in cells if c["algorithm"] == "pizza"]
        clocks = [c for c in cells if c["algorithm"] == "clock"]
        self.assertLess(max(c["distance_irrelevance_q"] for c in pizzas), min(c["distance_irrelevance_q"] for c in clocks))

    def test_hypernetwork_has_phase_and_generalization_surfaces(self):
        lens = self.data["lenses"]["hypernetwork"]
        self.assertEqual({c["algorithm"] for c in lens["cells"]}, {"convexity", "pudding", "double-sided"})
        self.assertEqual(len(lens["generalization"]), 16)
        self.assertTrue(all(0 <= c["seed_dependence"] <= 1 for c in lens["cells"]))

    def test_mips_exposes_success_and_continuous_failure(self):
        cases = self.data["lenses"]["mips"]["cases"]
        self.assertEqual(cases[0]["status"], "compiled")
        self.assertIn("8 / 8", cases[0]["verification"])
        self.assertIn("continuous state", cases[1]["status"])
        self.assertIn("unavailable", " ".join(cases[1]["stages"]))

    def test_sparse_invariant_has_nullspace_and_negative_control(self):
        positive, negative = self.data["lenses"]["sid"]["systems"]
        self.assertEqual(positive["nullity"], 1)
        self.assertEqual(positive["independent_rank"], 1)
        self.assertLess(positive["singular_values"][-1], 1e-6)
        for trajectory in positive["trajectories"]:
            values = [point["H"] for point in trajectory["points"]]
            self.assertLess(max(values) - min(values), 1e-5)
        self.assertEqual(negative["nullity"], 0)
        self.assertEqual(negative["sparse_coefficients"], [0] * 6)

    def test_claim_routes_are_goal_specific_and_end_in_evidence(self):
        lens = self.data["lenses"]["open_problems"]
        routes = {tuple(goal["evidence_route"]) for goal in lens["goals"]}
        self.assertEqual(len(routes), len(lens["goals"]))
        self.assertEqual(lens["validation_ladder"][-1], "competitive real-task baseline")


if __name__ == "__main__":
    unittest.main()
