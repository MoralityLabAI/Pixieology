from __future__ import annotations

import unittest

from build_pixie_storyworld_sft_env import action_policy_score, build_clean_prose_repeat_prompt


class BuildPixieStoryworldSftEnvTests(unittest.TestCase):
    def test_action_policy_score_rewards_lawful_trade(self) -> None:
        visible_state = "(visible-fact Bob (offer Alice Bread Coin))"
        self.assertEqual(action_policy_score("(buy Bob Alice Bread Coin)", visible_state), 5)
        self.assertEqual(action_policy_score("(steal Bob Alice Bread)", visible_state), -3)

    def test_build_clean_prose_repeat_prompt_appends_suffix(self) -> None:
        prompt = build_clean_prose_repeat_prompt("Stay grounded.", 0)
        self.assertIn("Stay grounded.", prompt)
        self.assertIn("Now answer in one short sentence.", prompt)


if __name__ == "__main__":
    unittest.main()
