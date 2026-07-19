"""Configuration loading with explicit, portable path surfaces."""

from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
REQUIRED_PATH_VARS = ("HF_HOME", "MODEL_CACHE", "DATA_ROOT", "OUTPUT_ROOT", "LLAMA_CPP_ROOT")


class ConfigError(ValueError):
    """Raised when a resolved experiment configuration is unsafe or incomplete."""


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_dotenv(path: Path) -> None:
    """Load a minimal KEY=VALUE file without overriding the caller's environment."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(base))
    for key, value in overlay.items():
        if key == "extends":
            continue
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_yaml(path: Path, seen: set[Path] | None = None) -> dict[str, Any]:
    resolved = path.resolve()
    seen = set() if seen is None else seen
    if resolved in seen:
        raise ConfigError(f"cyclic config inheritance at {resolved}")
    seen.add(resolved)
    if not resolved.is_file():
        raise ConfigError(f"configuration not found: {resolved}")
    data = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"configuration root must be a mapping: {resolved}")
    parent = data.get("extends")
    if parent:
        return _deep_merge(_load_yaml(resolved.parent / str(parent), seen), data)
    return data


def _interpolate(value: Any) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in os.environ or not os.environ[name].strip():
                raise ConfigError(f"required environment variable {name} is not set")
            return os.environ[name]
        return ENV_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [_interpolate(item) for item in value]
    if isinstance(value, dict):
        return {key: _interpolate(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class ExperimentConfig:
    source: Path
    values: dict[str, Any]

    @classmethod
    def load(cls, path: Path | None = None) -> "ExperimentConfig":
        root = project_root()
        load_dotenv(root / ".env.local")
        source = (path or root / "configs" / "smoke_auto.yaml").resolve()
        values = _interpolate(_load_yaml(source))
        cfg = cls(source=source, values=values)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.values.get("schema_version") != 1:
            raise ConfigError("schema_version must be 1")
        caps = self.values.get("caps", {})
        steps = int(caps.get("max_optimizer_steps", 0))
        minutes = int(caps.get("max_runtime_minutes", 0))
        if not 1 <= steps <= 100:
            raise ConfigError("caps.max_optimizer_steps must be between 1 and 100")
        if not 1 <= minutes <= 30:
            raise ConfigError("caps.max_runtime_minutes must be between 1 and 30")
        training = self.values.get("training", {})
        if training.get("target_modules") != "all-linear":
            raise ConfigError("the primary experiment requires target_modules=all-linear")
        if int(training.get("total_steps", 0)) > steps:
            raise ConfigError("training.total_steps exceeds caps.max_optimizer_steps")
        for key, raw in self.values.get("paths", {}).items():
            path = Path(str(raw)).expanduser()
            if not path.is_absolute():
                raise ConfigError(f"paths.{key} must resolve to an absolute path: {path}")

    def section(self, name: str) -> dict[str, Any]:
        value = self.values.get(name)
        if not isinstance(value, dict):
            raise ConfigError(f"missing configuration section: {name}")
        return value

    def path(self, name: str) -> Path:
        try:
            return Path(self.section("paths")[name]).resolve()
        except KeyError as exc:
            raise ConfigError(f"missing paths.{name}") from exc

    def with_training(self, **updates: Any) -> "ExperimentConfig":
        values = copy.deepcopy(self.values)
        values["training"].update(updates)
        cfg = ExperimentConfig(self.source, values)
        cfg.validate()
        return cfg

    def resolved_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.values)


def choose_profile(total_vram_mib: int) -> tuple[int, int, int]:
    """Return (sequence length, rank, gradient accumulation) for measured VRAM."""
    if total_vram_mib <= 4608:
        return (512, 8, 16)
    if total_vram_mib <= 6656:
        return (768, 8, 16)
    return (1024, 16, 8)

