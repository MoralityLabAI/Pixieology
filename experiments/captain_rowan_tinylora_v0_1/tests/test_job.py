import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("captain_job", ROOT / "build_job.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class CaptainRowanJobContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = MODULE.build()
        cls.job = cls.packet["job"]

    def test_packet_is_current_and_hash_bound(self):
        saved = json.loads((ROOT / "job.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, self.job)
        without_hash = dict(self.job)
        without_hash.pop("job_sha256")
        self.assertEqual(self.job["job_sha256"], MODULE.object_sha(without_hash))

    def test_splits_and_five_facts_are_frozen(self):
        train = [row for row in self.packet["rows"] if row["split"] == "discovery"]
        transfer = [row for row in self.packet["rows"] if row["split"] == "transfer"]
        self.assertEqual(len(train), 10)
        self.assertEqual(len(transfer), 10)
        self.assertTrue({"identity", "scene_goal", "voice", "values", "boundary"}.issubset({row["family"] for row in train}))
        self.assertFalse({row["id"] for row in train} & {row["id"] for row in transfer})

    def test_adapter_and_caps_are_exact(self):
        self.assertEqual(self.job["adapter"]["target_modules"], ["gate_proj"])
        self.assertEqual(self.job["adapter"]["layers_to_transform"], [21, 22, 23, 24, 25])
        self.assertEqual(self.job["training"]["checkpoint_steps"], 5)
        self.assertEqual(self.job["training"]["checkpoint_seconds"], 60)
        self.assertEqual(self.job["resources"], {"ram_mb": 8192, "cpu_pct": 50, "io_mb_s": 50, "timeout_seconds": 1800})
        self.assertEqual(self.job["gpu_guard"]["maximum_peak_memory_mib"], 3900)

    def test_authorization_is_fail_closed(self):
        auth = self.packet["authorization"]
        self.assertFalse(auth["authorized"])
        self.assertEqual(auth["job_sha256"], self.job["job_sha256"])
        self.assertIn(self.job["job_sha256"], auth["required_statement"])
        self.assertIn("no automatic authorization", auth["required_statement"])
        self.assertEqual(self.job["execution"]["state"], "READY_AWAITING_EXACT_AUTHORIZATION")
        self.assertFalse(all(auth["acknowledgements"].values()))

    def test_continuation_is_bound_without_mutating_v02(self):
        execution = self.job["execution"]
        for path_key, hash_key in (
            ("continuation_runner", "continuation_runner_sha256"),
            ("continuation_wrapper", "continuation_wrapper_sha256"),
            ("feedback_job", "feedback_job_file_sha256"),
        ):
            path = MODULE.REPO / execution[path_key]
            self.assertEqual(MODULE.file_sha(path), execution[hash_key])
        feedback = json.loads((ROOT / "feedback_job.json").read_text(encoding="utf-8"))
        self.assertEqual(feedback["dataset"]["registered_corpus_sha256"], self.job["dataset"]["sha256"])
        self.assertEqual(feedback["authorization"]["status"], "NOT_AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
