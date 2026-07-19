"""Pinned Prism llama.cpp acquisition and PEFT-LoRA to GGUF conversion."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from .config import ExperimentConfig
from .reporting import layout, sha256_file, utc_now, write_json
from .train import cleanup_cuda, load_quantized_base, attach_new_adapter, require_resource_cap, seed_everything, tokenizer_fingerprint


WINDOWS_ASSETS = {
    "llama-prism-b1-62061f9-bin-win-cuda-12.4-x64.zip": "9aa7eddde22dcc16b7294688fddc7ab37580b4941aa7a33d2aa4a3f412bb88f3",
    "cudart-llama-bin-win-cuda-12.4-x64.zip": "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6",
    "llama-bin-win-cpu-x64.zip": "7e11b2fbfb04bc9f1c05c2c5dbe743a0cb8bf231d9a66d9fa16a459cd13d9dde",
}


class ExportError(RuntimeError):
    """Pinned source, binary, model, or adapter conversion validation failed."""


def _download(url: str, destination: Path, expected_sha256: str) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and sha256_file(destination) == expected_sha256:
        return destination
    partial = destination.with_suffix(destination.suffix + ".partial")
    if partial.exists():
        partial.unlink()
    request = urllib.request.Request(url, headers={"User-Agent": "pixie-bonsai-feasibility/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    actual = sha256_file(partial)
    if actual != expected_sha256:
        partial.unlink(missing_ok=True)
        raise ExportError(f"SHA-256 mismatch for {destination.name}: expected {expected_sha256}, got {actual}")
    os.replace(partial, destination)
    return destination


def ensure_llama_source(config: ExperimentConfig) -> Path:
    paths = layout(config)
    source = paths.llama_cpp
    revision = config.section("llama_cpp")["revision"]
    repository = config.section("llama_cpp")["repository"]
    if not (source / ".git").is_dir():
        if source.exists() and any(source.iterdir()):
            raise ExportError(f"LLAMA_CPP_ROOT exists but is not a git checkout: {source}")
        if source.exists():
            source.rmdir()
        source.parent.mkdir(parents=True, exist_ok=True)
        temporary = source.with_name(source.name + ".partial")
        if temporary.exists():
            shutil.rmtree(temporary)
        completed = subprocess.run(
            ["git", "clone", "--filter=blob:none", repository, str(temporary)],
            text=True, capture_output=True, check=False, shell=False,
        )
        if completed.returncode != 0:
            raise ExportError(f"llama.cpp clone failed: {completed.stderr}")
        os.replace(temporary, source)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=source, text=True, capture_output=True, check=False)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source, text=True, capture_output=True, check=False)
    if status.stdout.strip() and head.stdout.strip() != revision:
        raise ExportError(f"refusing to replace dirty llama.cpp checkout at {source}")
    fetch = subprocess.run(["git", "fetch", "--depth", "1", "origin", revision], cwd=source, text=True, capture_output=True, check=False)
    if fetch.returncode != 0:
        raise ExportError(f"llama.cpp fetch failed: {fetch.stderr}")
    checkout = subprocess.run(["git", "checkout", "--detach", revision], cwd=source, text=True, capture_output=True, check=False)
    if checkout.returncode != 0:
        raise ExportError(f"llama.cpp checkout failed: {checkout.stderr}")
    actual = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source, text=True, capture_output=True, check=True).stdout.strip()
    if actual != revision:
        raise ExportError(f"llama.cpp revision mismatch: {actual}")
    converter = source / "convert_lora_to_gguf.py"
    if not converter.is_file():
        raise ExportError(f"converter missing at pinned commit: {converter}")
    return source


def ensure_llama_binaries(config: ExperimentConfig) -> dict[str, Path]:
    paths = layout(config)
    tag = config.section("llama_cpp")["release_tag"]
    release_root = paths.binaries / tag
    archives = paths.downloads / tag
    base_url = f"https://github.com/PrismML-Eng/llama.cpp/releases/download/{tag}"
    for name, digest in WINDOWS_ASSETS.items():
        archive = _download(f"{base_url}/{name}", archives / name, digest)
        target = release_root / ("cpu" if "cpu-x64" in name else "cuda")
        marker = target / f".{name}.extracted"
        if not marker.exists():
            target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(target)
            marker.write_text(f"sha256:{digest}\n", encoding="utf-8")
    result: dict[str, Path] = {}
    for flavor in ("cuda", "cpu"):
        servers = list((release_root / flavor).rglob("llama-server.exe"))
        clients = list((release_root / flavor).rglob("llama-cli.exe"))
        if servers and clients:
            result[f"server_{flavor}"] = servers[0]
            result[f"cli_{flavor}"] = clients[0]
    if "server_cuda" not in result or "server_cpu" not in result:
        raise ExportError(f"release archives did not contain expected llama executables: {release_root}")
    write_json(paths.artifacts / "llama_runtime.json", {
        "schema_version": 1, "created_utc": utc_now(), "tag": tag,
        "revision": config.section("llama_cpp")["revision"],
        "executables": {key: str(value) for key, value in result.items()},
        "archives": {name: {"sha256": digest, "path": str(archives / name)} for name, digest in WINDOWS_ASSETS.items()},
    })
    return result


def build_llama(config: ExperimentConfig) -> dict[str, Any]:
    source = ensure_llama_source(config)
    executables = ensure_llama_binaries(config)
    return {"status": "PASS", "source": str(source), "executables": {key: str(value) for key, value in executables.items()}}


def ensure_q1_model(config: ExperimentConfig) -> Path:
    from huggingface_hub import hf_hub_download
    model = config.section("model")
    path = Path(hf_hub_download(
        repo_id=model["gguf_id"], filename=model["gguf_filename"],
        revision=model["gguf_revision"], cache_dir=config.path("model_cache"),
        local_files_only=os.environ.get("HF_HUB_OFFLINE") == "1",
    ))
    actual = sha256_file(path)
    if actual != model["gguf_sha256"]:
        raise ExportError(f"Q1_0 SHA-256 mismatch: expected {model['gguf_sha256']}, got {actual}")
    return path


def local_base_snapshot(config: ExperimentConfig) -> Path:
    from huggingface_hub import snapshot_download
    model = config.section("model")
    return Path(snapshot_download(
        repo_id=model["unpacked_id"], revision=model["unpacked_revision"],
        cache_dir=config.path("model_cache"), local_files_only=os.environ.get("HF_HUB_OFFLINE") == "1",
        allow_patterns=["config.json", "generation_config.json", "tokenizer*", "*.jinja", "*.model", "*.json"],
    ))


def validate_peft_adapter(adapter_dir: Path) -> dict[str, Any]:
    from safetensors import safe_open
    config_path = adapter_dir / "adapter_config.json"
    weights_path = adapter_dir / "adapter_model.safetensors"
    if not config_path.is_file() or not weights_path.is_file():
        raise ExportError(f"incomplete PEFT adapter at {adapter_dir}")
    adapter_config = json.loads(config_path.read_text(encoding="utf-8"))
    with safe_open(weights_path, framework="pt", device="cpu") as handle:
        keys = list(handle.keys())
    forbidden = [key for key in keys if any(term in key for term in ("embed_tokens", "word_embeddings", "lm_head"))]
    if forbidden:
        raise ExportError(f"adapter contains forbidden embeddings/lm_head tensors: {forbidden[:5]}")
    if not keys or any("lora_" not in key for key in keys):
        raise ExportError("adapter contains non-LoRA or no tensors")
    return {
        "adapter_config": adapter_config, "tensor_count": len(keys), "tensor_names": keys,
        "forbidden_tensors": forbidden, "weights_bytes": weights_path.stat().st_size,
        "weights_sha256": sha256_file(weights_path),
    }


def convert_adapter(config: ExperimentConfig, adapter_dir: Path, output_path: Path, log_path: Path) -> dict[str, Any]:
    source = ensure_llama_source(config)
    base = local_base_snapshot(config)
    validation = validate_peft_adapter(adapter_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".partial")
    temporary.unlink(missing_ok=True)
    argv = [
        sys.executable, str(source / "convert_lora_to_gguf.py"),
        "--base", str(base), "--outfile", str(temporary),
        "--outtype", "f16", str(adapter_dir),
    ]
    env = os.environ.copy()
    gguf_python = str(source / "gguf-py")
    env["PYTHONPATH"] = gguf_python + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    completed = subprocess.run(argv, cwd=source, env=env, text=True, capture_output=True, check=False, shell=False, timeout=600)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "COMMAND\n" + json.dumps(argv) + "\n\nSTDOUT\n" + completed.stdout + "\nSTDERR\n" + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0 or not temporary.is_file():
        raise ExportError(f"PEFT-to-GGUF conversion failed ({completed.returncode}); see {log_path}: {completed.stderr[-2000:]}")
    os.replace(temporary, output_path)
    result = {
        "status": "PASS", "created_utc": utc_now(), "command": argv,
        "converter_revision": config.section("llama_cpp")["revision"],
        "peft_validation": validation, "output_path": str(output_path),
        "output_bytes": output_path.stat().st_size, "output_sha256": sha256_file(output_path),
        "log_path": str(log_path),
    }
    write_json(output_path.with_suffix(".manifest.json"), result)
    return result


def create_zero_adapter(config: ExperimentConfig) -> dict[str, Any]:
    require_resource_cap()
    paths = layout(config)
    root = paths.artifacts / "preflight"
    adapter_dir = root / "zero_peft_adapter"
    tokenizer = base = model = None
    try:
        seed_everything(int(config.values["seed"]))
        tokenizer, base = load_quantized_base(config)
        before = tokenizer_fingerprint(tokenizer)
        model, adapter_info = attach_new_adapter(base, config)
        temporary = root / "zero_peft_adapter.partial"
        if temporary.exists():
            shutil.rmtree(temporary)
        model.save_pretrained(temporary, safe_serialization=True)
        if adapter_dir.exists():
            shutil.rmtree(adapter_dir)
        os.replace(temporary, adapter_dir)
        validation = validate_peft_adapter(adapter_dir)
        result = {
            "status": "PASS", "created_utc": utc_now(), "adapter_path": str(adapter_dir),
            "adapter": adapter_info, "file_validation": validation,
            "tokenizer_unchanged": before == tokenizer_fingerprint(tokenizer),
        }
        write_json(root / "zero_peft_adapter.json", result)
        return result
    finally:
        try:
            del model, base, tokenizer
        except UnboundLocalError:
            pass
        cleanup_cuda()


def export_trained_adapter(config: ExperimentConfig, run_name: str = "smoke-v1") -> dict[str, Any]:
    paths = layout(config)
    adapter = paths.runs / run_name / "adapter"
    if not adapter.is_dir():
        raise ExportError(f"trained adapter missing: {adapter}")
    output = paths.runs / run_name / "pixie-smoke-f16.gguf"
    result = convert_adapter(config, adapter, output, paths.runs / run_name / "conversion.log")
    write_json(paths.runs / run_name / "conversion.json", result)
    return result


def preflight_adapter(config: ExperimentConfig) -> dict[str, Any]:
    paths = layout(config)
    build = build_llama(config)
    q1 = ensure_q1_model(config)
    zero = create_zero_adapter(config)
    output = paths.artifacts / "preflight" / "zero_adapter_f16.gguf"
    conversion = convert_adapter(
        config, Path(zero["adapter_path"]), output,
        paths.artifacts / "preflight" / "zero_conversion.log",
    )
    from .eval_gguf import zero_adapter_test
    runtime = zero_adapter_test(config, q1, output)
    result = {"status": "PASS" if runtime["status"] == "PASS" else "FAIL", "build": build, "q1_model": str(q1), "zero_adapter": zero, "conversion": conversion, "runtime": runtime}
    write_json(paths.artifacts / "preflight" / "preflight_result.json", result)
    if result["status"] != "PASS":
        raise ExportError(f"zero-adapter hard gate failed: {runtime}")
    return result
