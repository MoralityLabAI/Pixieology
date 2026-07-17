from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
CONFIG_FILENAME = "pixieology.config.json"


def repo_path(*parts: str) -> Path:
    root = Path(os.environ.get("PIXIE_ROOT") or REPO_ROOT).expanduser()
    return root.joinpath(*parts)


def config_file() -> Path:
    override = (os.environ.get("PIXIE_CONFIG") or "").strip()
    if override:
        path = Path(override).expanduser()
        return path if path.is_absolute() else repo_path(*path.parts)
    return repo_path(CONFIG_FILENAME)


@lru_cache(maxsize=8)
def _load_config_at(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != "pixieology_config_v1":
        raise ValueError(f"Unsupported Pixieology config schema in {path}")
    return payload


def load_config() -> dict[str, Any]:
    return _load_config_at(str(config_file().resolve()))


def config_value(section: str, key: str) -> Any:
    values = load_config().get(section)
    if not isinstance(values, dict) or key not in values:
        raise KeyError(f"Missing config value {section}.{key} in {config_file()}")
    return values[key]


def _path_from_value(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else repo_path(*path.parts)


def config_path(key: str) -> Path:
    value = config_value("paths", key)
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Config paths.{key} must be a non-empty string")
    if value.startswith("${data_root}/"):
        return data_root() / Path(value.removeprefix("${data_root}/"))
    if value.startswith("${model_cache_dir}/"):
        return model_cache_dir() / Path(value.removeprefix("${model_cache_dir}/"))
    if "${" in value:
        raise ValueError(f"Unsupported path interpolation in paths.{key}: {value}")
    return _path_from_value(value)


def model_id(key: str) -> str:
    value = config_value("models", key)
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Config models.{key} must be a non-empty string")
    value = value.strip()
    if value.startswith("${model_cache_dir}/"):
        return str(model_cache_dir() / Path(value.removeprefix("${model_cache_dir}/")))
    if value.startswith("${data_root}/"):
        return str(data_root() / Path(value.removeprefix("${data_root}/")))
    if "${" in value:
        raise ValueError(f"Unsupported path interpolation in models.{key}: {value}")
    path = Path(value).expanduser()
    if value.startswith((".", "data/", "data\\", "inputs/", "inputs\\", "external/", "external\\")):
        return str(path if path.is_absolute() else repo_path(*path.parts))
    return value


def steering_layer() -> int:
    value = config_value("steering", "layer")
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("Config steering.layer must be an integer")
    return value


def steering_strength() -> float:
    value = config_value("steering", "strength")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("Config steering.strength must be numeric")
    return float(value)


def steering_sweep_strengths() -> tuple[float, ...]:
    values = config_value("steering", "sweep_strengths")
    if not isinstance(values, list) or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise TypeError("Config steering.sweep_strengths must be a numeric list")
    return tuple(float(value) for value in values)


def resolve_path(env_name: str | None, *candidates: str | Path) -> Path:
    if env_name:
        env_value = (os.environ.get(env_name) or "").strip()
        if env_value:
            return Path(env_value).expanduser()
    if not candidates:
        raise ValueError("resolve_path requires at least one candidate path")
    normalized = [Path(candidate).expanduser() for candidate in candidates]
    for candidate in normalized:
        if candidate.exists():
            return candidate
    return normalized[-1]


# Kept as public names for older callers/tests; values are portable config entries.
DEFAULT_DATA_ROOT = Path(str(config_value("paths", "data_root")))
DEFAULT_MODEL_CACHE_DIR = Path(str(config_value("paths", "model_cache_dir")))
DEFAULT_HF_HOME = Path(str(config_value("paths", "hf_home")))


def _configured_or_repo(path: Path, fallback: Path) -> Path:
    configured = path if path.is_absolute() else repo_path(*path.parts)
    return resolve_path(None, configured, fallback)


def data_root() -> Path:
    return resolve_path("PIXIE_DATA_ROOT", _configured_or_repo(DEFAULT_DATA_ROOT, repo_path("data")))


def normalized_trajectory_path(filename: str) -> Path:
    return data_root() / "normalized_trajectories" / filename


def research_output_path(filename: str) -> Path:
    return data_root() / "pixie_research" / filename


def model_cache_dir() -> Path:
    configured = DEFAULT_MODEL_CACHE_DIR if DEFAULT_MODEL_CACHE_DIR.is_absolute() else repo_path(*DEFAULT_MODEL_CACHE_DIR.parts)
    return resolve_path("PIXIE_MODEL_CACHE_DIR", configured, data_root() / "model_cache")


def hf_home() -> Path:
    configured = DEFAULT_HF_HOME if DEFAULT_HF_HOME.is_absolute() else repo_path(*DEFAULT_HF_HOME.parts)
    return resolve_path("HF_HOME", configured, data_root() / "hf_home")


def constitution_seed_path() -> Path:
    return resolve_path("PIXIE_CONSTITUTION_PATH", repo_path("fae_constitution_seed.jsonl"))


def soul_path() -> Path:
    return resolve_path("PIXIE_SOUL_PATH", config_path("soul_path"))


def storyworld_comparison_path() -> Path:
    return resolve_path("PIXIE_STORYWORLD_COMPARISON_PATH", config_path("storyworld_comparison_path"))


def godel_globes_experiment_root() -> Path:
    return resolve_path("PIXIE_GODEL_GLOBES_ROOT", config_path("godel_globes_experiment_root"))


def godel_globes_character_space_path() -> Path:
    return resolve_path("PIXIE_GODEL_GLOBES_CHARACTER_SPACE", config_path("godel_globes_character_space"))


def godel_globes_study_receipts_path() -> Path:
    return resolve_path("PIXIE_GODEL_GLOBES_RECEIPTS", config_path("godel_globes_study_receipts"))


def godel_globes_ab_result_path() -> Path:
    return resolve_path("PIXIE_GODEL_GLOBES_RESULT", config_path("godel_globes_ab_result"))


def tesseract_train_script() -> Path:
    return resolve_path("PIXIE_TESSERACT_TRAIN", config_path("tesseract_train_script"))


def tesseract_loop_script() -> Path:
    return resolve_path("PIXIE_TESSERACT_LOOP", config_path("tesseract_loop_script"))


def bridge_run_script() -> Path:
    return resolve_path("PIXIE_BRIDGE_RUN", config_path("bridge_run_script"))


def metta_root() -> Path:
    return resolve_path("PIXIE_METTA_ROOT", config_path("metta_root"))


def configure_hf_home() -> Path:
    resolved = hf_home()
    os.environ["HF_HOME"] = str(resolved)
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(resolved))
    os.environ.setdefault("HF_HUB_CACHE", str(resolved))
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved
