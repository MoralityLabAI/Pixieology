import importlib.util
import json
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_fixture", ROOT / "build_fixture.py")
BUILDER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(BUILDER)


def matmul(left, right):
    return [[sum(left[i][k] * right[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def transpose(matrix):
    return [list(column) for column in zip(*matrix)]


def rms_band(left, right, center, radius=2):
    values = []
    for layer in range(max(0, center - radius), min(27, center + radius) + 1):
        for axis in ("x", "y", "z"):
            values.append((left["depth_points"][layer][axis] - right["depth_points"][layer][axis]) ** 2)
    return math.sqrt(sum(values) / len(values))


class FixtureContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = BUILDER.build()
        cls.saved = json.loads((ROOT / "fixture.json").read_text(encoding="utf-8"))
        cls.by_id = {motif["id"]: motif for motif in cls.data["motifs"]}

    def test_saved_fixture_is_current_and_deterministic(self):
        self.assertEqual(self.data, self.saved)
        self.assertEqual(self.data, BUILDER.build())
        self.assertEqual(len(self.data["fixture_sha256"]), 64)

    def test_closed_loops_and_orthogonal_holonomy(self):
        identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        for motif in self.data["motifs"]:
            self.assertEqual(motif["loop_points"][0], {**motif["loop_points"][-1], "phase": 0.0})
            rotation = motif["holonomy"]["matrix"]
            product = matmul(rotation, transpose(rotation))
            for row in range(3):
                for column in range(3):
                    self.assertAlmostEqual(product[row][column], identity[row][column], places=5)

    def test_declared_depth_convergence_bands_exist(self):
        self.assertLess(rms_band(self.by_id["q_proj"], self.by_id["k_proj"], 9), self.data["etale"]["epsilon"])
        self.assertLess(rms_band(self.by_id["v_proj"], self.by_id["o_proj"], 16), self.data["etale"]["epsilon"])
        self.assertLess(rms_band(self.by_id["gate_proj"], self.by_id["up_proj"], 23), self.data["etale"]["epsilon"])
        self.assertLess(rms_band(self.by_id["up_proj"], self.by_id["down_proj"], 23), self.data["etale"]["epsilon"])

    def test_coupling_is_recomputable(self):
        for motif in self.data["motifs"]:
            gramian = motif["control"]["gramian"]
            rotation = motif["holonomy"]["matrix"]
            returned = matmul(matmul(rotation, gramian), transpose(rotation))
            difference = [[returned[i][j] - gramian[i][j] for j in range(3)] for i in range(3)]
            frob = lambda matrix: math.sqrt(sum(value * value for row in matrix for value in row))
            coupling = frob(difference) / frob(gramian)
            self.assertAlmostEqual(coupling, motif["control"]["holonomy_coupling"], places=5)

    def test_evidence_boundary_and_confirmation_are_explicit(self):
        self.assertTrue(self.data["global_normalization"])
        self.assertIn("not activation evidence", self.data["claim_boundary"])
        self.assertEqual(self.data["confirmation"]["independent_pairs"], 256)
        self.assertEqual(self.data["confirmation"]["audit_action"], "accept")
        self.assertIn("abstention", self.data["confirmation"]["noise_requirement"])

    def test_ablation_case_is_registered_and_not_model_evidence(self):
        case = self.data["ablation_case"]
        self.assertEqual(case["motif_id"], "gate_proj")
        self.assertEqual(case["depth"], 23)
        self.assertEqual(case["operator"], "A(alpha) = I - alpha u u^T")
        self.assertAlmostEqual(sum(value * value for value in case["direction_u"]), 1.0, places=5)
        self.assertIn("not a Qwen or Pixie activation trace", case["claim_boundary"])


if __name__ == "__main__":
    unittest.main()
