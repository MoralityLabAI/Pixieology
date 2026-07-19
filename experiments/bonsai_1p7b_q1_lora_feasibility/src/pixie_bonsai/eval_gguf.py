"""Native Q1_0 evaluation through a pinned local llama-server."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from .config import ExperimentConfig
from .data import load_jsonl
from .reporting import layout, utc_now, write_json
from .train import require_resource_cap


class LlamaRuntimeError(RuntimeError):
    """The pinned local llama.cpp runtime failed to load or serve a request."""


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _runtime_manifest(config: ExperimentConfig) -> dict[str, str]:
    path = layout(config).artifacts / "llama_runtime.json"
    if not path.is_file():
        raise LlamaRuntimeError("llama runtime manifest missing; run build-llama")
    return json.loads(path.read_text(encoding="utf-8"))["executables"]


@contextmanager
def llama_server(
    config: ExperimentConfig,
    model_path: Path,
    log_path: Path,
    adapter_path: Path | None = None,
) -> Iterator[tuple[str, Path, list[str]]]:
    manifest = _runtime_manifest(config)
    errors: list[str] = []
    for flavor in ("cuda", "cpu"):
        executable = Path(manifest[f"server_{flavor}"])
        port = _port()
        url = f"http://127.0.0.1:{port}"
        argv = [
            str(executable), "--model", str(model_path), "--host", "127.0.0.1",
            "--port", str(port), "--ctx-size", "1024", "--seed", str(config.values["seed"]),
            "--temp", "0", "--jinja", "--n-gpu-layers", "99" if flavor == "cuda" else "0",
        ]
        if adapter_path is not None:
            argv.extend(["--lora", str(adapter_path)])
        candidate_log = log_path.with_name(f"{log_path.stem}.{flavor}{log_path.suffix}")
        candidate_log.parent.mkdir(parents=True, exist_ok=True)
        with candidate_log.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, text=True, shell=False)
            try:
                deadline = time.monotonic() + 120
                ready = False
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        break
                    try:
                        with urllib.request.urlopen(f"{url}/health", timeout=2) as response:
                            if response.status == 200:
                                ready = True
                                break
                    except (urllib.error.URLError, TimeoutError):
                        time.sleep(0.5)
                if not ready:
                    errors.append(f"{flavor}: server failed to become healthy; log={candidate_log}")
                    continue
                yield url, candidate_log, argv
                return
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
    raise LlamaRuntimeError("; ".join(errors))


def request_chat(url: str, messages: Sequence[dict[str, str]], config: ExperimentConfig) -> dict[str, Any]:
    body = json.dumps({
        "model": "local", "messages": list(messages), "temperature": 0,
        "seed": int(config.values["seed"]),
        "max_tokens": int(config.section("evaluation")["max_new_tokens"]), "stream": False,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{url}/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        value = json.loads(response.read().decode("utf-8"))
    content = value["choices"][0]["message"]["content"]
    return {"content": content, "response": value}


def loaded_adapters(url: str) -> list[dict[str, Any]]:
    """Read llama-server's authoritative runtime adapter inventory."""
    with urllib.request.urlopen(f"{url}/lora-adapters", timeout=30) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, list):
        raise LlamaRuntimeError(f"unexpected /lora-adapters response: {value!r}")
    return value


def _adapter_is_active(inventory: list[dict[str, Any]], adapter_path: Path) -> bool:
    expected = os.path.normcase(str(adapter_path.resolve()))
    return any(
        os.path.normcase(str(Path(str(item.get("path", ""))).resolve())) == expected
        and float(item.get("scale", 0.0)) != 0.0
        for item in inventory
    )


def _normalized(text: str) -> str:
    value = text.strip()
    if "</think>" in value:
        value = value.split("</think>", 1)[1].strip()
    return value


def zero_adapter_test(config: ExperimentConfig, model_path: Path, adapter_path: Path) -> dict[str, Any]:
    require_resource_cap()
    paths = layout(config)
    root = paths.artifacts / "preflight"
    messages = [
        {"role": "system", "content": "Respond briefly with visible answer text only."},
        {"role": "user", "content": "Say the word cedar."},
    ]
    with llama_server(config, model_path, root / "q1_zero_base.log") as (url, base_log, base_argv):
        base_inventory = loaded_adapters(url)
        base = request_chat(url, messages, config)
    with llama_server(config, model_path, root / "q1_zero_adapter.log", adapter_path) as (url, adapter_log, adapter_argv):
        adapter_inventory = loaded_adapters(url)
        adapted = request_chat(url, messages, config)
    adapter_loaded = _adapter_is_active(adapter_inventory, adapter_path)
    exact = base["content"] == adapted["content"]
    result = {
        "status": "PASS" if adapter_loaded and exact else "FAIL",
        "base_content": base["content"], "adapter_content": adapted["content"],
        "deterministic_exact_match": exact, "adapter_load_confirmed_in_log": adapter_loaded,
        "base_adapter_inventory": base_inventory, "adapter_inventory": adapter_inventory,
        "base_log": str(base_log), "adapter_log": str(adapter_log),
        "base_command": base_argv, "adapter_command": adapter_argv,
    }
    write_json(root / "zero_adapter_q1_test.json", result)
    return result


def _score(rows: list[dict[str, Any]], config: ExperimentConfig) -> dict[str, Any]:
    evaluation = config.section("evaluation")
    canary = evaluation["canary"]
    marker = evaluation["style_marker"].lower()
    canary_rows = [row for row in rows if row["kind"] == "canary"]
    style_rows = [row for row in rows if row["kind"] == "style"]
    canary_hits = sum(_normalized(row["generation"]) == canary for row in canary_rows)
    marker_hits = sum(marker in _normalized(row["generation"]).lower() for row in style_rows)
    return {"canary_hits": canary_hits, "canary_total": len(canary_rows), "marker_hits": marker_hits, "marker_total": len(style_rows)}


def evaluate_q1(config: ExperimentConfig, run_name: str = "smoke-v1") -> dict[str, Any]:
    require_resource_cap()
    paths = layout(config)
    from .export_gguf import ensure_q1_model
    model = ensure_q1_model(config)
    adapter = paths.runs / run_name / "pixie-smoke-f16.gguf"
    if not adapter.is_file():
        raise LlamaRuntimeError(f"converted trained adapter missing: {adapter}")
    records = load_jsonl(config.path("data_root") / "smoke_eval.jsonl")
    modes: dict[str, Any] = {}
    for mode, adapter_path in (("C_q1_base", None), ("D_q1_adapter", adapter)):
        rows: list[dict[str, Any]] = []
        started = time.monotonic()
        with llama_server(config, model, paths.runs / run_name / f"{mode}.server.log", adapter_path) as (url, log_path, argv):
            inventory = loaded_adapters(url)
            for record in records:
                reply = request_chat(url, record.prompt_messages, config)
                rows.append({
                    "id": record.record_id, "kind": record.kind, "expected": record.expected,
                    "generation": reply["content"], "normalized": _normalized(reply["content"]),
                })
        adapter_confirmed = not inventory if adapter_path is None else _adapter_is_active(inventory, adapter_path)
        modes[mode] = {
            "rows": rows, "scores": _score(rows, config), "wall_seconds": time.monotonic() - started,
            "server_log": str(log_path), "command": argv, "adapter_load_confirmed": adapter_confirmed,
            "adapter_inventory": inventory,
        }
        output = paths.runs / run_name / f"{mode}.jsonl"
        output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    hf_path = paths.runs / run_name / "hf_evaluation.json"
    hf = json.loads(hf_path.read_text(encoding="utf-8")) if hf_path.is_file() else {}
    eval_cfg = config.section("evaluation")
    c, d = modes["C_q1_base"]["scores"], modes["D_q1_adapter"]["scores"]
    b = hf.get("modes", {}).get("B_hf_adapter", {}).get("scores", {})
    behavior = (
        d["canary_hits"] >= int(eval_cfg["min_canary_hits"])
        and d["marker_hits"] >= int(eval_cfg["min_marker_hits"])
        and d["canary_hits"] - c["canary_hits"] >= int(eval_cfg["min_improvement"])
        and d["marker_hits"] - c["marker_hits"] >= int(eval_cfg["min_improvement"])
        and (not b or b.get("canary_hits", 0) - d["canary_hits"] <= int(eval_cfg["max_q1_regression"]))
        and (not b or b.get("marker_hits", 0) - d["marker_hits"] <= int(eval_cfg["max_q1_regression"]))
        and modes["D_q1_adapter"]["adapter_load_confirmed"]
    )
    result = {"schema_version": 1, "created_utc": utc_now(), "status": "PASS" if behavior else "FAIL", "modes": modes, "behavior_survived": behavior}
    write_json(paths.runs / run_name / "q1_evaluation.json", result)
    return result
