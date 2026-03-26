from __future__ import annotations

import os
from pathlib import Path


DEFAULT_HF_HOME = Path("D:/Research_Engine/hf_cache")


def configure_hf_home() -> Path:
    hf_home = Path(os.environ.get("HF_HOME") or DEFAULT_HF_HOME)
    os.environ["HF_HOME"] = str(hf_home)
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hf_home))
    os.environ.setdefault("HF_HUB_CACHE", str(hf_home))
    hf_home.mkdir(parents=True, exist_ok=True)
    return hf_home
