"""Load and validate the versioned lexical marker resource."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Mapping

import yaml


MARKER_RESOURCE = "fae_markers_v1.yaml"


@dataclass(frozen=True)
class MarkerSet:
    version: str
    categories: Mapping[str, tuple[str, ...]]

    @property
    def markers(self) -> tuple[str, ...]:
        """Return de-duplicated markers while preserving YAML order."""

        return tuple(dict.fromkeys(marker for values in self.categories.values() for marker in values))


def _validate_payload(payload: object) -> MarkerSet:
    if not isinstance(payload, dict):
        raise ValueError("Fae marker YAML must contain a mapping")
    version = payload.get("version")
    categories = payload.get("categories")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Fae marker YAML needs a non-empty string version")
    if not isinstance(categories, dict) or not categories:
        raise ValueError("Fae marker YAML needs a non-empty categories mapping")

    normalized: dict[str, tuple[str, ...]] = {}
    for category, raw_markers in categories.items():
        if not isinstance(category, str) or not category.strip():
            raise ValueError("Fae marker category names must be non-empty strings")
        if not isinstance(raw_markers, list) or not raw_markers:
            raise ValueError(f"Fae marker category {category!r} must be a non-empty list")
        markers: list[str] = []
        for marker in raw_markers:
            if not isinstance(marker, str) or not marker.strip():
                raise ValueError(f"Fae marker category {category!r} contains an invalid marker")
            markers.append(marker.casefold().strip())
        normalized[category.strip()] = tuple(dict.fromkeys(markers))
    return MarkerSet(version=version.strip(), categories=normalized)


def load_marker_set(path: str | Path | None = None) -> MarkerSet:
    """Load markers from ``path`` or from the package's immutable v1 resource."""

    if path is None:
        resource = files("fae_bench.data").joinpath(MARKER_RESOURCE)
        with resource.open("r", encoding="utf-8") as handle:
            return _validate_payload(yaml.safe_load(handle))
    with Path(path).expanduser().open("r", encoding="utf-8") as handle:
        return _validate_payload(yaml.safe_load(handle))


@lru_cache(maxsize=1)
def default_marker_set() -> MarkerSet:
    return load_marker_set()
