import itertools
import sys
import unittest
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import control_proof  # noqa: E402


class ExactControlProofTests(unittest.TestCase):
    def test_strict_witness_checks_all_hold(self):
        certificate = control_proof.build_certificate()
        self.assertTrue(all(certificate["proof_checks"].values()))
        axis, coupled = certificate["systems"]
        self.assertEqual(axis["reachability_matrix"], [[1, 1], [0, 0]])
        self.assertEqual(axis["gramian"], [[2, 0], [0, 0]])
        self.assertEqual(coupled["reachability_matrix"], [[1, 1], [1, 2]])
        self.assertEqual(coupled["gramian"], [[2, 3], [3, 5]])

    def test_gramian_rank_equals_reachability_rank_on_exhaustive_small_grid(self):
        entries = (-1, 0, 1)
        checked = 0
        for a_flat in itertools.product(entries, repeat=4):
            a = [[Fraction(a_flat[0]), Fraction(a_flat[1])], [Fraction(a_flat[2]), Fraction(a_flat[3])]]
            for b_flat in itertools.product(entries, repeat=2):
                if b_flat == (0, 0):
                    continue
                b = [[Fraction(b_flat[0])], [Fraction(b_flat[1])]]
                for horizon in (1, 2, 3):
                    c = control_proof.reachability_matrix(a, b, horizon)
                    w = control_proof.gramian(c)
                    self.assertEqual(control_proof.rank(c), control_proof.rank(w))
                    checked += 1
        self.assertEqual(checked, 1944)

    def test_passive_dynamics_do_not_depend_on_intervention_jacobian(self):
        certificate = control_proof.build_certificate()
        first, second = certificate["systems"]
        self.assertEqual(first["A"], second["A"])
        self.assertNotEqual(first["B"], second["B"])
        self.assertEqual(first["passive_trajectory"], second["passive_trajectory"])


if __name__ == "__main__":
    unittest.main()
