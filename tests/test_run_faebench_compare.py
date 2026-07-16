from __future__ import annotations

import unittest

from run_faebench_compare import extract_action, parse_adapter_overrides


class RunFaebenchCompareTests(unittest.TestCase):
    def test_parse_adapter_overrides(self) -> None:
        parsed = parse_adapter_overrides(["1.7B=/tmp/a", "0.8B=/tmp/b"])
        self.assertEqual(parsed["1.7B"], "/tmp/a")
        self.assertEqual(parsed["0.8B"], "/tmp/b")

    def test_extract_action_prefers_parenthesized_command(self) -> None:
        self.assertEqual(extract_action("Use this: (buy Bob Alice Bread Coin)"), "(buy Bob Alice Bread Coin)")

    def test_extract_action_uses_trade_heuristic(self) -> None:
        text = "Bob trades with Alice and pays Alice coin for bread."
        self.assertEqual(extract_action(text), "(buy Bob Alice Bread Coin)")


if __name__ == "__main__":
    unittest.main()
