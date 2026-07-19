from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
import re
from unittest.mock import patch

import pixie_env


class PixieEnvTests(unittest.TestCase):
    def test_resolve_path_prefers_env_override(self) -> None:
        with patch.dict(os.environ, {"PIXIE_DATA_ROOT": "Z:/pixie-data"}, clear=False):
            self.assertEqual(pixie_env.data_root(), Path("Z:/pixie-data"))

    def test_resolve_path_prefers_existing_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing"
            existing = Path(tmpdir) / "existing"
            existing.mkdir()
            resolved = pixie_env.resolve_path(None, missing, existing, Path(tmpdir) / "fallback")
            self.assertEqual(resolved, existing)

    def test_data_root_falls_back_to_repo_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"PIXIE_ROOT": tmpdir}, clear=False):
                with patch.object(pixie_env, "DEFAULT_DATA_ROOT", Path(tmpdir) / "does-not-exist"):
                    self.assertEqual(pixie_env.data_root(), Path(tmpdir) / "data")

    def test_single_config_has_portability_contract(self) -> None:
        config = pixie_env.load_config()
        self.assertEqual(config["schema"], "pixieology_config_v1")
        self.assertIn("data_root", config["paths"])
        self.assertIn("chronicle_corpus", config["paths"])
        self.assertIn("chronicle_sft_output_dir", config["paths"])
        self.assertIn("godel_globes_character_space", config["paths"])
        self.assertIn("godel_globes_study_receipts", config["paths"])
        self.assertIn("pixie_1_7b", config["models"])
        self.assertIsInstance(config["steering"]["layer"], int)
        self.assertIsInstance(config["steering"]["strength"], (int, float))

    def test_data_and_model_placeholders_follow_root_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data = Path(tmpdir) / "portable-data"
            models = Path(tmpdir) / "portable-models"
            with patch.dict(
                os.environ,
                {"PIXIE_DATA_ROOT": str(data), "PIXIE_MODEL_CACHE_DIR": str(models)},
                clear=False,
            ):
                self.assertEqual(
                    pixie_env.config_path("fae_switch_synth"),
                    data / "normalized_trajectories" / "fae_switch_synth.jsonl",
                )
                self.assertEqual(
                    Path(pixie_env.model_id("base_0_8b")),
                    models / "Qwen3.5" / "Qwen3.5-0.8B-Base-HF",
                )
                self.assertEqual(
                    pixie_env.godel_globes_study_receipts_path(),
                    data / "godel_globes_5d_character_lab" / "study_receipts",
                )

    def test_godel_globes_game_contract_is_repo_relative(self) -> None:
        root = pixie_env.godel_globes_experiment_root()
        self.assertEqual(root, pixie_env.REPO_ROOT / "experiments" / "godel_globes_5d_character_lab")
        self.assertEqual(pixie_env.godel_globes_character_space_path(), root / "character_space_v1.json")
        self.assertTrue(pixie_env.godel_globes_character_space_path().is_file())

    def test_scripts_contain_no_windows_drive_paths(self) -> None:
        drive_path = re.compile(r"(?i)[CD]:[\\/]")
        offenders = []
        for suffix in ("*.py", "*.ps1", "*.sh"):
            for path in pixie_env.REPO_ROOT.glob(suffix):
                if drive_path.search(path.read_text(encoding="utf-8")):
                    offenders.append(path.name)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
