from __future__ import annotations

import unittest

from run_pixie_storyworld_sft import append_device_map_flag, append_max_memory_flag


class RunPixieStoryworldSftTests(unittest.TestCase):
    def test_append_max_memory_flag_skips_zero(self) -> None:
        cmd = ["python", "train.py"]
        self.assertEqual(append_max_memory_flag(cmd[:], 0), ["python", "train.py"])

    def test_append_max_memory_flag_adds_value(self) -> None:
        cmd = ["python", "train.py"]
        self.assertEqual(
            append_max_memory_flag(cmd[:], 3300),
            ["python", "train.py", "--max-memory-mib", "3300"],
        )

    def test_append_device_map_flag_adds_value(self) -> None:
        cmd = ["python", "train.py"]
        self.assertEqual(
            append_device_map_flag(cmd[:], "single-gpu"),
            ["python", "train.py", "--device-map", "single-gpu"],
        )


if __name__ == "__main__":
    unittest.main()
