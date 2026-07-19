from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import existing_adapter_pair as pair  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def make_adapter(root: Path, base: str, payload: bytes) -> None:
    write_json(
        root / "adapter_config.json",
        {
            "base_model_name_or_path": base,
            "bias": "none",
            "peft_type": "LORA",
            "r": 2,
            "lora_alpha": 4,
            "modules_to_save": None,
            "target_modules": sorted(pair.EXPECTED_TARGETS),
        },
    )
    (root / "adapter_model.safetensors").write_bytes(payload)


def test_pair_requires_distinct_compatible_adapters(tmp_path: Path) -> None:
    base = tmp_path / "base"
    write_json(base / "config.json", {"model_type": "qwen3"})
    (base / "model.safetensors").write_bytes(b"base")
    companion = tmp_path / "companion"
    storyworld = tmp_path / "storyworld"
    make_adapter(companion, "same/base", b"companion")
    make_adapter(storyworld, "same/base", b"storyworld")
    converter_root = tmp_path / "llama.cpp"
    converter_root.mkdir()
    (converter_root / "convert_lora_to_gguf.py").write_text("# fixture", encoding="utf-8")
    config = tmp_path / "pixieology.config.json"
    write_json(
        config,
        {
            "paths": {
                "lora_pixie_josie_1p7b_base_hf": str(base),
                "lora_pixie_companion_adapter_peft": str(companion),
                "lora_pixie_storyworld_adapter_peft": str(storyworld),
                "lora_pixie_josie_gguf_root": "out",
                "lora_pixie_prism_llama_cpp_root": str(converter_root),
            }
        },
    )
    _, result = pair.inspect_configured_pair(config)
    assert result["status"] == "PASS_COMPATIBLE_TRAINED_PAIR"
    assert result["adapters"]["companion"]["adapter_model_sha256"] != result["adapters"]["storyworld"]["adapter_model_sha256"]


def test_pair_rejects_saved_full_modules(tmp_path: Path) -> None:
    root = tmp_path / "adapter"
    make_adapter(root, "same/base", b"weights")
    config_path = root / "adapter_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["modules_to_save"] = ["lm_head"]
    write_json(config_path, config)
    with pytest.raises(pair.PairError, match="non-LoRA modules"):
        pair.inspect_adapter("bad", root)
