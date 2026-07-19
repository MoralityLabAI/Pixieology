from pathlib import Path

import pytest

from pixie_bonsai.config import ConfigError, ExperimentConfig, choose_profile


def test_profile_selection() -> None:
    assert choose_profile(4096) == (512, 8, 16)
    assert choose_profile(6144) == (768, 8, 16)
    assert choose_profile(8192) == (1024, 16, 8)


def test_inheritance_and_environment_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = str(tmp_path.resolve()).replace("\\", "/")
    monkeypatch.setenv("ROOT", root)
    (tmp_path / "base.yaml").write_text(
        """schema_version: 1
task_id: test
paths:
  hf_home: ${ROOT}/hf
  model_cache: ${ROOT}/models
  data_root: ${ROOT}/data
  output_root: ${ROOT}/output
  llama_cpp_root: ${ROOT}/llama
caps:
  max_optimizer_steps: 100
  max_runtime_minutes: 30
training:
  target_modules: all-linear
  total_steps: 30
  rank: 8
""",
        encoding="utf-8",
    )
    (tmp_path / "child.yaml").write_text(
        "extends: base.yaml\ntraining:\n  rank: 4\n",
        encoding="utf-8",
    )
    config = ExperimentConfig.load(tmp_path / "child.yaml")
    assert config.section("training")["rank"] == 4
    assert config.path("output_root") == tmp_path / "output"


def test_attention_only_primary_config_is_rejected(tmp_path: Path) -> None:
    values = {
        "schema_version": 1, "task_id": "x",
        "paths": {name: str(tmp_path / name) for name in ("hf_home", "model_cache", "data_root", "output_root", "llama_cpp_root")},
        "caps": {"max_optimizer_steps": 100, "max_runtime_minutes": 30},
        "training": {"target_modules": ["q_proj"], "total_steps": 1},
    }
    with pytest.raises(ConfigError, match="all-linear"):
        ExperimentConfig(tmp_path / "x.yaml", values).validate()

