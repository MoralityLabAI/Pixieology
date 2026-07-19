#!/usr/bin/env python3
"""Serve two attested LoRA residents from one bounded llama.cpp base process."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parents[1]
for root in (APP_ROOT, REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import existing_adapter_pair  # noqa: E402
import multi_adapter_matrix  # noqa: E402
from attested_llama_proxy import (  # noqa: E402
    LOOPBACK,
    LauncherError,
    _terminate_owned,
    gpu_snapshot,
    reserve_port,
    resolve_executable,
)
from server import append_jsonl_fsync, atomic_json, canonical_json, sha256_value, utc_now  # noqa: E402


RUNTIME_ID = "pixie_attested_multi_lora_proxy_v1"
MAX_PROXY_BODY = 2 * 1024 * 1024
BACKEND_ALIAS = "josie-shared-base"
ROUTE_LABELS = ("companion", "storyworld")
DEFAULT_MATRIX = APP_ROOT / "config" / "multi_adapter_matrix_v1.json"


class DualRouteError(LauncherError):
    """The shared-base, per-request LoRA route contract failed."""


def build_llama_command(
    executable: Path,
    base_model: Path,
    adapters: list[Path],
    *,
    upstream_port: int,
    context_size: int,
    threads: int,
    gpu_layers: int,
) -> list[str]:
    if len(adapters) != 2 or len({path.resolve() for path in adapters}) != 2:
        raise DualRouteError("exactly two distinct LoRA adapter files are required")
    if any("," in str(path) for path in adapters):
        raise DualRouteError("adapter paths containing commas are unsupported by llama.cpp --lora")
    if not 128 <= context_size <= 8192 or threads < 1 or gpu_layers < 0:
        raise DualRouteError("invalid context, thread, or GPU-layer setting")
    return [
        str(executable),
        "-m",
        str(base_model),
        "--lora",
        ",".join(str(path) for path in adapters),
        "--lora-init-without-apply",
        "--alias",
        BACKEND_ALIAS,
        "--host",
        "127.0.0.1",
        "--port",
        str(upstream_port),
        "--ctx-size",
        str(context_size),
        "--parallel",
        "1",
        "--batch-size",
        "128",
        "--ubatch-size",
        "128",
        "--threads",
        str(threads),
        "--threads-batch",
        str(threads),
        "--n-gpu-layers",
        str(gpu_layers),
        "--jinja",
        "--seed",
        "17",
        "--temp",
        "0",
        "--reasoning",
        "off",
        "--cache-ram",
        "0",
        "--no-warmup",
    ]


def prepare_forward_payload(
    payload: dict[str, Any], route_by_model: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    model = str(payload.get("model") or "")
    if model not in route_by_model:
        raise DualRouteError(f"unknown logical resident model: {model!r}")
    if payload.get("stream") is True:
        raise DualRouteError("streaming responses are not supported by the attested village proxy")
    route = route_by_model[model]
    forwarded = dict(payload)
    forwarded["model"] = BACKEND_ALIAS
    forwarded["stream"] = False
    forwarded["cache_prompt"] = False
    chat_template_kwargs = dict(forwarded.get("chat_template_kwargs") or {})
    chat_template_kwargs["enable_thinking"] = False
    forwarded["chat_template_kwargs"] = chat_template_kwargs
    if "lora_scales" in route:
        forwarded["lora"] = [dict(row) for row in route["lora_scales"]]
    else:
        forwarded["lora"] = [
            {"id": adapter_id, "scale": 1.0 if route.get("adapter_id") == adapter_id else 0.0}
            for adapter_id in sorted({int(candidate["adapter_id"]) for candidate in route_by_model.values()})
        ]
    return forwarded, route


def _json_request(url: str, *, payload: Any = None, timeout: float = 30) -> Any:
    body = None if payload is None else canonical_json(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_backend(
    base_url: str,
    child: subprocess.Popen[Any],
    adapters: list[Path],
    *,
    timeout: float,
    probe_log: Path | None = None,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    last_error = "no response"
    contract_mismatches = 0
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise DualRouteError(f"llama-server exited during startup with code {child.returncode}")
        try:
            models = _json_request(base_url + "/v1/models", timeout=min(10, timeout))
            model_ids = [str(row.get("id")) for row in models.get("data", []) if isinstance(row, dict)]
            observed = _json_request(base_url + "/lora-adapters", timeout=min(10, timeout))
            probe = {
                "schema_version": "pixie_dual_lora_startup_probe_v1",
                "utc": utc_now(),
                "model_ids": model_ids,
                "lora_adapters": observed,
            }
            if probe_log is not None:
                append_jsonl_fsync(probe_log, probe)
            if BACKEND_ALIAS not in model_ids:
                last_error = "backend alias is not advertised"
            elif not isinstance(observed, list) or len(observed) != 2:
                last_error = f"expected two loaded adapters, got {observed!r}"
            else:
                expected_paths = [str(path.resolve()).casefold() for path in adapters]
                observed_paths = [str(Path(str(row.get("path"))).resolve()).casefold() for row in observed]
                observed_ids = [int(row.get("id", -1)) for row in observed]
                observed_scales = [float(row.get("scale", -1)) for row in observed]
                if observed_paths != expected_paths:
                    last_error = f"adapter path order mismatch: {observed_paths!r}"
                elif observed_ids != [0, 1]:
                    last_error = f"unexpected adapter IDs: {observed!r}"
                else:
                    if observed_scales != [0.0, 0.0]:
                        _json_request(
                            base_url + "/lora-adapters",
                            payload=[{"id": 0, "scale": 0.0}, {"id": 1, "scale": 0.0}],
                            timeout=min(10, timeout),
                        )
                        observed = _json_request(base_url + "/lora-adapters", timeout=min(10, timeout))
                        if probe_log is not None:
                            append_jsonl_fsync(
                                probe_log,
                                {
                                    "schema_version": "pixie_dual_lora_startup_probe_v1",
                                    "utc": utc_now(),
                                    "event": "global_scales_zeroed",
                                    "model_ids": model_ids,
                                    "lora_adapters": observed,
                                },
                            )
                    final_ids = [int(row.get("id", -1)) for row in observed]
                    final_scales = [float(row.get("scale", -1)) for row in observed]
                    if final_ids == [0, 1] and final_scales == [0.0, 0.0]:
                        return observed
                    last_error = f"unable to zero global adapter scales: {observed!r}"
            contract_mismatches += 1
            if contract_mismatches >= 5:
                raise DualRouteError(f"llama-server adapter contract mismatch: {last_error}")
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError, TypeError, ValueError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise DualRouteError(f"llama-server did not become ready within {timeout:g}s: {last_error}")


@dataclass
class DualProxyState:
    upstream_base_url: str
    route_by_model: dict[str, dict[str, Any]]
    identity_by_label: dict[str, dict[str, Any]]
    request_log: Path
    shutdown_token: str
    lock: threading.Lock


class DualProxyHandler(BaseHTTPRequestHandler):
    server_version = "PixieAttestedDualLoraProxy/1.0"

    @property
    def state(self) -> DualProxyState:
        return self.server.state  # type: ignore[attr-defined]

    def _json(self, status: int, value: Any) -> None:
        body = (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/models":
            self._json(
                HTTPStatus.OK,
                {
                    "object": "list",
                    "data": [
                        {"id": model, "object": "model", "owned_by": "pixie-local"}
                        for model in self.state.route_by_model
                    ],
                },
            )
            return
        if self.path.startswith("/pixie/identity/"):
            label = self.path.rsplit("/", 1)[-1]
            identity = self.state.identity_by_label.get(label)
            self._json(HTTPStatus.OK if identity else HTTPStatus.NOT_FOUND, identity or {"error": "not_found"})
            return
        if self.path == "/health":
            try:
                value = _json_request(self.state.upstream_base_url + "/health", timeout=10)
                self._json(HTTPStatus.OK, value)
            except Exception as exc:  # health boundary returns a structured 502
                self._json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_unavailable", "detail": str(exc)})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/pixie/shutdown":
            observed = self.headers.get("X-Pixie-Shutdown-Token", "")
            if not hmac.compare_digest(observed, self.state.shutdown_token):
                self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
                return
            self._json(HTTPStatus.ACCEPTED, {"status": "shutting_down"})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path != "/v1/chat/completions":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_PROXY_BODY:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "invalid_request_size"})
            return
        try:
            original = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(original, dict):
                raise DualRouteError("request body must be a JSON object")
            forwarded, route = prepare_forward_payload(original, self.state.route_by_model)
        except (json.JSONDecodeError, UnicodeDecodeError, DualRouteError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "detail": str(exc)})
            return
        started = time.perf_counter()
        try:
            response = _json_request(
                self.state.upstream_base_url + "/v1/chat/completions",
                payload=forwarded,
                timeout=240,
            )
        except urllib.error.HTTPError as exc:
            self._json(exc.code, {"error": "upstream_http_error", "detail": exc.read().decode("utf-8", "replace")})
            return
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_unavailable", "detail": str(exc)})
            return
        if isinstance(response, dict):
            response["model"] = route["model_alias"]
        try:
            raw_message_content = str(response["choices"][0]["message"]["content"])
            reasoning_content_present = bool(response["choices"][0]["message"].get("reasoning_content"))
        except (KeyError, IndexError, TypeError):
            raw_message_content = ""
            reasoning_content_present = False
        event = {
            "schema_version": "pixie_dual_lora_request_v1",
            "utc": utc_now(),
            "model_alias": route["model_alias"],
            "adapter_label": route["label"],
            "adapter_id": route.get("adapter_id"),
            "adapter_sha256": route["adapter_sha256"],
            "combination_sha256": route.get("combination_sha256"),
            "lora_scales": route.get("lora_scales"),
            "request_sha256": sha256_value(original),
            "forwarded_request_sha256": sha256_value(forwarded),
            "response_sha256": sha256_value(response),
            "raw_message_content": raw_message_content,
            "reasoning_content_present": reasoning_content_present,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
        with self.state.lock:
            append_jsonl_fsync(self.state.request_log, event)
        self._json(HTTPStatus.OK, response)

    def log_message(self, format: str, *args: Any) -> None:
        return


def make_server(host: str, port: int, state: DualProxyState) -> ThreadingHTTPServer:
    if host not in LOOPBACK:
        raise DualRouteError("dual adapter proxy is loopback-only")
    server = ThreadingHTTPServer((host, port), DualProxyHandler)
    server.state = state  # type: ignore[attr-defined]
    return server


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--config", type=Path, default=REPO_ROOT / "pixieology.config.json")
    command.add_argument("--run-id", required=True)
    command.add_argument("--host", default="127.0.0.1")
    command.add_argument("--port", type=int, required=True)
    command.add_argument("--upstream-port", type=int, default=0)
    command.add_argument("--ctx-size", type=int, default=1024)
    command.add_argument("--threads", type=int, default=4)
    command.add_argument("--gpu-layers", type=int, default=0)
    command.add_argument("--startup-timeout", type=float, default=300)
    command.add_argument("--max-runtime-seconds", type=float, default=0)
    command.add_argument("--output-root", type=Path)
    command.add_argument("--combination-matrix", type=Path, default=DEFAULT_MATRIX)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if os.environ.get("PIXIE_RESOURCE_CAP_ACTIVE") != "1":
        raise SystemExit("dual_lora_proxy must run inside run_capped_strict.ps1")
    if args.host not in LOOPBACK or not 1 <= args.port <= 65535:
        raise SystemExit("public route must use a valid loopback port")
    if args.max_runtime_seconds < 0:
        raise SystemExit("max-runtime-seconds cannot be negative")
    paths = existing_adapter_pair.resolve_config_paths(args.config.expanduser().resolve())
    executable = resolve_executable(str(paths["lora_pixie_bonsai_llama_server"]))
    base_model = paths["lora_pixie_josie_base_q4_gguf"]
    adapters = [paths["lora_pixie_companion_adapter_gguf"], paths["lora_pixie_storyworld_adapter_gguf"]]
    for path in [base_model, *adapters]:
        if not path.is_file() or path.suffix.lower() != ".gguf":
            raise SystemExit(f"missing GGUF artifact: {path}")
    upstream_port = args.upstream_port or reserve_port()
    if upstream_port == args.port:
        raise SystemExit("public and upstream ports must differ")
    output_root = (
        args.output_root.expanduser().resolve()
        if args.output_root
        else paths["lora_pixie_village_runtime"] / "dual_lora_launches"
    ) / args.run_id
    output_root.mkdir(parents=True, exist_ok=False)
    manifest_path = output_root / "launch_manifest.json"
    request_log = output_root / "requests.jsonl"
    startup_probe_log = output_root / "startup_probes.jsonl"
    shutdown_token_path = output_root / "shutdown.token"
    hashes = {
        "llama_server_sha256": existing_adapter_pair.sha256_file(executable),
        "base_model_sha256": existing_adapter_pair.sha256_file(base_model),
        "adapter_sha256s": [existing_adapter_pair.sha256_file(path) for path in adapters],
    }
    matrix = multi_adapter_matrix.load_matrix(args.combination_matrix.expanduser().resolve())
    if [row["label"] for row in matrix["adapters"]] != list(ROUTE_LABELS):
        raise SystemExit(f"matrix adapter order must be {list(ROUTE_LABELS)}")
    command = build_llama_command(
        executable,
        base_model,
        adapters,
        upstream_port=upstream_port,
        context_size=args.ctx_size,
        threads=args.threads,
        gpu_layers=args.gpu_layers,
    )
    route_by_model = multi_adapter_matrix.build_routes(
        matrix, adapters, hashes["adapter_sha256s"]
    )
    before_gpu = gpu_snapshot()
    stdout_path = output_root / "llama.stdout.log"
    stderr_path = output_root / "llama.stderr.log"
    shutdown_token = secrets.token_urlsafe(32)
    with shutdown_token_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(shutdown_token + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    manifest: dict[str, Any] = {
        "schema_version": "pixie_attested_dual_lora_launch_v1",
        "status": "STARTING",
        "runtime": RUNTIME_ID,
        "started_at": utc_now(),
        "run_id": args.run_id,
        "public_route": {"host": args.host, "port": args.port},
        "upstream": {"host": "127.0.0.1", "port": upstream_port},
        "files": {"llama_server": str(executable), "base_model": str(base_model), "adapters": [str(path) for path in adapters]},
        "hashes": hashes,
        "routes": route_by_model,
        "command": command,
        "gpu_before": before_gpu,
        "resource_cap_attested_by_parent": True,
    }
    atomic_json(manifest_path, manifest)
    child: subprocess.Popen[Any] | None = None
    proxy: ThreadingHTTPServer | None = None
    run_error: str | None = None
    try:
        with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
            child = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                shell=False,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            manifest["owned_pid"] = child.pid
            atomic_json(manifest_path, manifest)
            upstream_base = f"http://127.0.0.1:{upstream_port}"
            observed_adapters = wait_for_backend(
                upstream_base,
                child,
                adapters,
                timeout=args.startup_timeout,
                probe_log=startup_probe_log,
            )
            identities = {
                route["label"]: {
                    "schema_version": "pixie_adapter_identity_v3",
                    "runtime": RUNTIME_ID,
                    "adapter_label": route["label"],
                    "adapter_sha256": route["adapter_sha256"],
                    "adapter_id": route.get("adapter_id"),
                    "base_model_id": "Goekdeniz-Guelmez/Josiefied-Qwen3-1.7B-abliterated-v1",
                    "base_model_sha256": hashes["base_model_sha256"],
                    "llama_server_sha256": hashes["llama_server_sha256"],
                    "model_alias": route["model_alias"],
                    "owned_pid": child.pid,
                    "matrix_id": matrix["matrix_id"],
                    "combination_sha256": route["combination_sha256"],
                    "components": [
                        {key: component[key] for key in ("adapter_id", "label", "sha256", "scale")}
                        for component in route["components"]
                    ],
                    "selection": {"request_lora": route["lora_scales"]},
                }
                for route in route_by_model.values()
            }
            proxy = make_server(
                args.host,
                args.port,
                DualProxyState(upstream_base, route_by_model, identities, request_log, shutdown_token, threading.Lock()),
            )
            manifest["status"] = "READY"
            manifest["ready_at"] = utc_now()
            manifest["observed_lora_adapters"] = observed_adapters
            manifest["identities"] = identities
            manifest["combination_matrix"] = matrix
            manifest["combination_matrix_sha256"] = sha256_value(matrix)
            atomic_json(manifest_path, manifest)
            if args.max_runtime_seconds:
                timer = threading.Timer(args.max_runtime_seconds, proxy.shutdown)
                timer.daemon = True
                timer.start()

            def stop_if_backend_exits() -> None:
                assert child is not None and proxy is not None
                child.wait()
                proxy.shutdown()

            threading.Thread(target=stop_if_backend_exits, daemon=True).start()
            proxy.serve_forever(poll_interval=0.2)
    except Exception as exc:
        run_error = f"{type(exc).__name__}: {exc}"
        manifest["error"] = run_error
        manifest["status"] = "FAILED"
        atomic_json(manifest_path, manifest)
    finally:
        if proxy is not None:
            proxy.server_close()
        cleanup = _terminate_owned(child) if child is not None else {"owned_pid": None, "terminated": True}
        if not cleanup.get("terminated"):
            manifest["status"] = "CLEANUP_FAILED"
        elif run_error is not None:
            manifest["status"] = "FAILED_CLEAN"
        else:
            manifest["status"] = "STOPPED"
        manifest["stopped_at"] = utc_now()
        manifest["cleanup"] = cleanup
        manifest["gpu_after"] = gpu_snapshot()
        manifest["request_count"] = (
            len(request_log.read_text(encoding="utf-8").splitlines()) if request_log.is_file() else 0
        )
        manifest["startup_probe_log"] = str(startup_probe_log)
        atomic_json(manifest_path, manifest)
    return 0 if manifest["status"] == "STOPPED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
