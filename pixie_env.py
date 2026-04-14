from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_ROOT = Path("D:/Research_Engine/tesseract_persistent/data")
DEFAULT_MODEL_CACHE_DIR = Path("D:/Research_Engine/models")
DEFAULT_HF_HOME = Path("D:/Research_Engine/hf_cache")
DEFAULT_SOUL_PATH = Path("soul.md")
DEFAULT_STORYWORLD_COMPARISON_PATH = Path("route_ablation_comparison.json")
DEFAULT_TESSERACT_TRAIN = Path("external/train_qlora.py")
DEFAULT_BRIDGE_RUN = Path("external/run_episode.py")


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


def repo_path(*parts: str) -> Path:
    root = Path(os.environ.get("PIXIE_ROOT") or REPO_ROOT).expanduser()
    return root.joinpath(*parts)


def _repo_data_root() -> Path:
    return repo_path("data")


def _repo_inputs_root() -> Path:
    return repo_path("inputs")


def data_root() -> Path:
    return resolve_path("PIXIE_DATA_ROOT", DEFAULT_DATA_ROOT, _repo_data_root())


def normalized_trajectory_path(filename: str) -> Path:
    return data_root() / "normalized_trajectories" / filename


def research_output_path(filename: str) -> Path:
    return data_root() / "pixie_research" / filename


def model_cache_dir() -> Path:
    return resolve_path("PIXIE_MODEL_CACHE_DIR", DEFAULT_MODEL_CACHE_DIR, data_root() / "models_cache")


def hf_home() -> Path:
    return resolve_path("HF_HOME", DEFAULT_HF_HOME, data_root() / "hf_home")


def constitution_seed_path() -> Path:
    return resolve_path(
        "PIXIE_CONSTITUTION_PATH",
        repo_path("fae_constitution_seed.jsonl"),
    )


def soul_path() -> Path:
    return resolve_path(
        "PIXIE_SOUL_PATH",
        DEFAULT_SOUL_PATH if DEFAULT_SOUL_PATH.is_absolute() else repo_path(str(DEFAULT_SOUL_PATH)),
        _repo_inputs_root() / "soul.md",
        repo_path("soul.md"),
    )


def storyworld_comparison_path() -> Path:
    return resolve_path(
        "PIXIE_STORYWORLD_COMPARISON_PATH",
        DEFAULT_STORYWORLD_COMPARISON_PATH
        if DEFAULT_STORYWORLD_COMPARISON_PATH.is_absolute()
        else repo_path("inputs", str(DEFAULT_STORYWORLD_COMPARISON_PATH)),
        repo_path("inputs", "route_ablation_comparison.json"),
    )


def tesseract_train_script() -> Path:
    default = DEFAULT_TESSERACT_TRAIN if DEFAULT_TESSERACT_TRAIN.is_absolute() else repo_path(str(DEFAULT_TESSERACT_TRAIN))
    return resolve_path("PIXIE_TESSERACT_TRAIN", default, repo_path("external", "train_qlora.py"))


def bridge_run_script() -> Path:
    default = DEFAULT_BRIDGE_RUN if DEFAULT_BRIDGE_RUN.is_absolute() else repo_path(str(DEFAULT_BRIDGE_RUN))
    return resolve_path("PIXIE_BRIDGE_RUN", default, repo_path("external", "run_episode.py"))


def configure_hf_home() -> Path:
    resolved = hf_home()
    os.environ["HF_HOME"] = str(resolved)
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(resolved))
    os.environ.setdefault("HF_HUB_CACHE", str(resolved))
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved
