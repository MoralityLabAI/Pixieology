import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class ReachabilityExperimentTests(unittest.TestCase):
    def test_confirmation_exact_gates(self):
        summary = read_json(ROOT / "results_confirmation" / "summary.json")
        task = summary["task_result"]
        reliability = summary["measurement_reliability"]
        self.assertEqual(task["passive_accuracy"], 0.5)
        self.assertEqual(task["control_accuracy"], 1.0)
        self.assertEqual(task["conditional_information_gain_bits"], 1.0)
        self.assertEqual(reliability["passive_identity_leaks"], 0)
        self.assertEqual(reliability["coordinate_invariance_fraction"], 1.0)
        self.assertEqual(summary["claim_support"], "pass")

    def test_confirmation_passive_contract_has_no_oracle_fields(self):
        rows = read_jsonl(ROOT / "results_confirmation" / "passive_observations.jsonl")
        forbidden = {"B", "reachability_matrix", "gramian", "reachability_rank", "class", "oracle_rank"}
        self.assertEqual(len(rows), 512)
        self.assertTrue(all(forbidden.isdisjoint(row) for row in rows))

    def test_confirmation_pair_contract_is_identical_and_unique(self):
        items = read_jsonl(ROOT / "results_confirmation" / "frozen_items.jsonl")
        self.assertEqual(len(items), 256)
        self.assertEqual(len({item["passive_sha256"] for item in items}), 256)
        self.assertTrue(all({candidate["oracle_rank"] for candidate in item["candidates"]} == {1, 2} for item in items))

    def test_audit_accepts_with_complete_reliability(self):
        audit = read_json(ROOT / "review" / "audit_confirmation" / "audit.json")
        self.assertEqual(audit["claim_support"]["status"], "supported")
        self.assertEqual(audit["operational_decision"]["action"], "accept")
        self.assertTrue(audit["measurement_reliability"]["meets_declared_limits"])
        self.assertEqual(audit["measurement_reliability"]["deterministic_coverage_rate"], 1.0)
        self.assertEqual(len(audit["adjudication_queue"]), 0)

    def test_summary_artifact_hashes_match(self):
        summary = read_json(ROOT / "results_confirmation" / "summary.json")
        for name, expected in summary["artifact_sha256"].items():
            actual = hashlib.sha256((ROOT / "results_confirmation" / name).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, name)

    def test_confirmation_manifest_and_runner_match_staged_hashes(self):
        stage = read_json(ROOT / "results_confirmation" / "stage_receipt.json")
        runner_hash = hashlib.sha256((ROOT / "run_experiment.py").read_bytes()).hexdigest()
        manifest_hash = hashlib.sha256((ROOT / "manifest_confirmation.yaml").read_bytes()).hexdigest()
        self.assertEqual(stage["runner_sha256"], runner_hash)
        self.assertEqual(stage["manifest_sha256"], manifest_hash)

    def test_noise_sweep_preserves_pair_order_longer_than_absolute_class(self):
        summary = read_json(ROOT / "results_confirmation" / "summary.json")
        rows = summary["metric_robustness"]["noise_sweep"]
        self.assertTrue(all(row["pair_accuracy"] >= row["candidate_accuracy"] for row in rows))
        at_one_percent = next(row for row in rows if row["sigma"] == 0.01)
        self.assertGreater(at_one_percent["pair_accuracy"], 0.99)
        self.assertLess(at_one_percent["candidate_accuracy"], 0.7)


if __name__ == "__main__":
    unittest.main()
