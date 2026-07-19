#!/usr/bin/env python3
"""Validate and convert the configured, previously trained Josie LoRA pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parents[1]
EXPECTED_TARGETS = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}
PAIR_KEYS = {
    "companion": "lora_pixie_companion_adapter_peft",
    "storyworld": "lora_pixie_storyworld_adapter_peft",
}


class PairError(RuntimeError):
    """The configured adapter pair is absent, incompatible, or unverifiable."""


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PairError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PairError(f"expected JSON object in {path}")
    return value


def resolve_config_paths(config_path: Path) -> dict[str, Path]:
    config = read_json(config_path)
    raw_paths = config.get("paths")
    if not isinstance(raw_paths, dict):
        raise PairError("pixieology config requires a paths object")
    resolved_strings: dict[str, str] = {}

    def resolve_value(key: str, stack: tuple[str, ...] = ()) -> str:
        if key in resolved_strings:
            return resolved_strings[key]
        if key in stack or key not in raw_paths:
            raise PairError(f"invalid config path reference: {' -> '.join((*stack, key))}")
        value = str(raw_paths[key])
        for candidate in raw_paths:
            marker = "${" + candidate + "}"
            if marker in value:
                value = value.replace(marker, resolve_value(candidate, (*stack, key)))
        resolved_strings[key] = value
        return value

    result: dict[str, Path] = {}
    for key in raw_paths:
        value = Path(resolve_value(key)).expanduser()
        result[key] = value.resolve() if value.is_absolute() else (config_path.parent / value).resolve()
    return result


def inspect_adapter(label: str, root: Path) -> dict[str, Any]:
    config_path = root / "adapter_config.json"
    weights_path = root / "adapter_model.safetensors"
    if not config_path.is_file() or not weights_path.is_file():
        raise PairError(f"{label} adapter is incomplete: {root}")
    config = read_json(config_path)
    targets = {str(value) for value in config.get("target_modules", [])}
    if targets != EXPECTED_TARGETS:
        raise PairError(f"{label} target modules differ: {sorted(targets)}")
    if config.get("modules_to_save") not in (None, []):
        raise PairError(f"{label} unexpectedly saves non-LoRA modules")
    if config.get("bias") != "none" or config.get("peft_type") != "LORA":
        raise PairError(f"{label} is not a bias-free PEFT LoRA")
    if int(config.get("r", 0)) <= 0 or int(config.get("lora_alpha", 0)) <= 0:
        raise PairError(f"{label} has invalid rank or alpha")
    return {
        "label": label,
        "root": str(root),
        "base_model_name_or_path": str(config.get("base_model_name_or_path") or ""),
        "rank": int(config["r"]),
        "alpha": int(config["lora_alpha"]),
        "target_modules": sorted(targets),
        "adapter_config_sha256": sha256_file(config_path),
        "adapter_model_sha256": sha256_file(weights_path),
        "adapter_model_bytes": weights_path.stat().st_size,
    }


def inspect_configured_pair(config_path: Path) -> tuple[dict[str, Path], dict[str, Any]]:
    paths = resolve_config_paths(config_path)
    required = {
        "lora_pixie_josie_1p7b_base_hf",
        "lora_pixie_josie_gguf_root",
        "lora_pixie_prism_llama_cpp_root",
        *PAIR_KEYS.values(),
    }
    missing = sorted(required - paths.keys())
    if missing:
        raise PairError(f"missing config paths: {', '.join(missing)}")
    base = paths["lora_pixie_josie_1p7b_base_hf"]
    if not (base / "config.json").is_file() or not (base / "model.safetensors").is_file():
        raise PairError(f"configured Josie base is incomplete: {base}")
    adapters = {label: inspect_adapter(label, paths[key]) for label, key in PAIR_KEYS.items()}
    declared_bases = {entry["base_model_name_or_path"] for entry in adapters.values()}
    if len(declared_bases) != 1:
        raise PairError(f"adapters declare different bases: {sorted(declared_bases)}")
    hashes = {entry["adapter_model_sha256"] for entry in adapters.values()}
    if len(hashes) != len(adapters):
        raise PairError("configured residents do not have distinct adapter weights")
    return paths, {
        "schema_version": "pixie_existing_josie_pair_v1",
        "status": "PASS_COMPATIBLE_TRAINED_PAIR",
        "base": {
            "path": str(base),
            "config_sha256": sha256_file(base / "config.json"),
            "model_bytes": (base / "model.safetensors").stat().st_size,
        },
        "declared_base_model": next(iter(declared_bases)),
        "adapters": adapters,
    }


def convert_pair(config_path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    paths, receipt = inspect_configured_pair(config_path)
    converter = paths["lora_pixie_prism_llama_cpp_root"] / "convert_lora_to_gguf.py"
    if not converter.is_file():
        raise PairError(f"LoRA converter is missing: {converter}")
    out_root = paths["lora_pixie_josie_gguf_root"]
    out_root.mkdir(parents=True, exist_ok=True)
    conversions: dict[str, Any] = {}
    for label, key in PAIR_KEYS.items():
        output = out_root / f"{label}-f16.gguf"
        argv = [
            sys.executable,
            str(converter),
            "--base",
            str(paths["lora_pixie_josie_1p7b_base_hf"]),
            "--outfile",
            str(output),
            "--outtype",
            "f16",
            str(paths[key]),
        ]
        if dry_run:
            conversions[label] = {"status": "DRY_RUN", "argv": argv, "output": str(output)}
            continue
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=300, check=False)
        log = out_root / f"{label}-conversion.log"
        log.write_text(completed.stdout + "\n--- STDERR ---\n" + completed.stderr, encoding="utf-8")
        if completed.returncode != 0 or not output.is_file():
            raise PairError(f"{label} conversion failed with exit {completed.returncode}; see {log}")
        conversions[label] = {
            "status": "PASS",
            "argv": argv,
            "output": str(output),
            "output_sha256": sha256_file(output),
            "output_bytes": output.stat().st_size,
            "log": str(log),
            "log_sha256": sha256_file(log),
        }
    receipt["converter"] = {
        "path": str(converter),
        "sha256": sha256_file(converter),
    }
    receipt["conversions"] = conversions
    receipt["status"] = "DRY_RUN" if dry_run else "PASS_GGUF_ADAPTER_PAIR"
    receipt_path = out_root / ("pair_conversion.dry_run.json" if dry_run else "pair_conversion.receipt.json")
    atomic_json(receipt_path, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "pixieology.config.json")
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.inspect_only:
        _, result = inspect_configured_pair(args.config.resolve())
    else:
        result = convert_pair(args.config.resolve(), dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
