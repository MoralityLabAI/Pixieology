from __future__ import annotations

import unittest

from run_pixie_overnight_local import parse_args


class RunPixieOvernightLocalTests(unittest.TestCase):
    def test_parse_args_uses_stable_dest_names_for_1_7b_flags(self) -> None:
        args = parse_args(["--skip-1.7b", "--force-1.7b"])
        self.assertTrue(args.skip_1_7b)
        self.assertTrue(args.force_1_7b)


if __name__ == "__main__":
    unittest.main()
