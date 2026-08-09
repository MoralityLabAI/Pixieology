import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def canonical_sha(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CaptainRowanRetryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads((ROOT / "job.json").read_text(encoding="utf-8"))
        cls.retry = json.loads((ROOT / "job_v0_1_1.json").read_text(encoding="utf-8"))
        cls.authorization = json.loads((ROOT / "authorization_v0_1_1.template.json").read_text(encoding="utf-8"))

    def test_retry_hash_and_predecessor_are_bound(self):
        unhashed = dict(self.retry)
        unhashed.pop("job_sha256")
        self.assertEqual(self.retry["job_sha256"], canonical_sha(unhashed))
        self.assertEqual(self.retry["retry"]["predecessor_job_sha256"], self.original["job_sha256"])
        receipt = REPO / self.retry["retry"]["prior_attempt_receipt"]
        self.assertEqual(file_sha(receipt), self.retry["retry"]["prior_attempt_receipt_sha256"])

    def test_only_resource_change_is_approved_ram_cap(self):
        self.assertEqual(self.original["resources"]["ram_mb"], 8192)
        self.assertEqual(self.retry["resources"]["ram_mb"], 10240)
        for key in ("cpu_pct", "io_mb_s", "timeout_seconds"):
            self.assertEqual(self.retry["resources"][key], self.original["resources"][key])
        self.assertEqual(self.retry["gpu_guard"], self.original["gpu_guard"])
        self.assertEqual(self.retry["dataset"], self.original["dataset"])
        self.assertEqual(self.retry["adapter"], self.original["adapter"])
        self.assertEqual(self.retry["training"], self.original["training"])

    def test_retry_launcher_and_wrapper_are_bound(self):
        execution = self.retry["execution"]
        self.assertEqual(file_sha(REPO / execution["retry_launcher"]), execution["retry_launcher_sha256"])
        self.assertEqual(file_sha(REPO / execution["retry_wrapper"]), execution["retry_wrapper_sha256"])
        self.assertEqual(execution["hard_cap_paths"], [execution["retry_wrapper"]])

    def test_authorization_is_exact_and_fail_closed(self):
        self.assertFalse(self.authorization["authorized"])
        self.assertEqual(self.authorization["job_sha256"], self.retry["job_sha256"])
        self.assertIn(self.retry["job_sha256"], self.authorization["required_statement"])
        self.assertIn("10240 MiB RAM", self.authorization["required_statement"])
        self.assertIn("prior 8 GiB memory-cap abort", self.authorization["required_statement"])
        self.assertFalse(all(self.authorization["acknowledgements"].values()))


if __name__ == "__main__":
    unittest.main()
