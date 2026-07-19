#!/usr/bin/env python3
"""Own one llama.cpp base-plus-LoRA process and attest its exact launch inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import hmac
import os
import secrets
import shutil
import socket
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

from server import atomic_json, canonical_json, configured_paths, utc_now


RUNTIME_ID = "pixie_attested_llama_proxy_v1"
MAX_PROXY_BODY = 2 * 1024 * 1024
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class LauncherError(RuntimeError):
    """The attested launcher could not safely establish a resident route."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_executable(value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return candidate.resolve()
    located = shutil.which(value)
    if not located:
        raise LauncherError(f"llama-server executable not found: {value}")
    return Path(located).resolve()


def reserve_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def build_llama_command(
    executable: Path,
    base_model: Path,
    adapter: Path,
    *,
    model_alias: str,
    upstream_port: int,
    context_size: int,
    threads: int,
    gpu_layers: int,
) -> list[str]:
    if not model_alias or any(character.isspace() for character in model_alias):
        raise LauncherError("model alias must be a nonempty token without whitespace")
    if not 1 <= upstream_port <= 65535:
        raise LauncherError("upstream port is invalid")
    if not 128 <= context_size <= 131072 or threads < 1 or gpu_layers < 0:
        raise LauncherError("invalid llama.cpp context, thread, or GPU-layer setting")
    return [
        str(executable),
        "-m",
        str(base_model),
        "--lora",
        str(adapter),
        "--alias",
        model_alias,
        "--host",
        "127.0.0.1",
        "--port",
        str(upstream_port),
        "--ctx-size",
        str(context_size),
        "--threads",
        str(threads),
        "--n-gpu-layers",
        str(gpu_layers),
        "--jinja",
        "--seed",
        "17",
        "--temp",
        "0",
    ]


def gpu_snapshot() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"available": False, "gpus": []}
    completed = subprocess.run(
        [
            executable,
            "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    rows = []
    if completed.returncode == 0:
        for line in completed.stdout.splitlines():
            values = [part.strip() for part in line.split(",")]
            if len(values) == 6:
                rows.append(
                    {
                        "name": values[0],
                        "memory_total_mib": int(values[1]),
                        "memory_used_mib": int(values[2]),
                        "memory_free_mib": int(values[3]),
                        "utilization_percent": int(values[4]),
                        "temperature_c": int(values[5]),
                    }
                )
    return {"available": completed.returncode == 0, "gpus": rows, "stderr": completed.stderr.strip()}


@dataclass(frozen=True)
class ProxyState:
    upstream_base_url: str
    identity: dict[str, Any]
    shutdown_token: str | None = None


class AttestedProxyHandler(BaseHTTPRequestHandler):
    server_version = "PixieAttestedLlamaProxy/1.0"

    @property
    def state(self) -> ProxyState:
        return self.server.state  # type: ignore[attr-defined]

    def _json(self, status: int, value: Any) -> None:
        body = (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _forward(self, method: str) -> None:
        if self.path not in {"/v1/models", "/v1/chat/completions", "/health"}:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > MAX_PROXY_BODY:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request_too_large"})
            return
        body = self.rfile.read(length) if length else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        target = self.state.upstream_base_url.rstrip("/") + self.path
        request = urllib.request.Request(target, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                payload = response.read()
                status = response.status
                content_type = response.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            status = exc.code
            content_type = exc.headers.get("Content-Type", "application/json")
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            self._json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_unavailable", "detail": str(exc)})
            return
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/pixie/identity":
            self._json(HTTPStatus.OK, self.state.identity)
            return
        self._forward("GET")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/pixie/shutdown":
            expected = self.state.shutdown_token
            observed = self.headers.get("X-Pixie-Shutdown-Token", "")
            if not expected or not hmac.compare_digest(observed, expected):
                self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
                return
            self._json(HTTPStatus.ACCEPTED, {"status": "shutting_down"})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self._forward("POST")

    def log_message(self, format: str, *args: Any) -> None:
        return


def make_proxy_server(host: str, port: int, state: ProxyState) -> ThreadingHTTPServer:
    if host not in LOOPBACK:
        raise LauncherError("attested adapter proxy is loopback-only")
    server = ThreadingHTTPServer((host, port), AttestedProxyHandler)
    server.state = state  # type: ignore[attr-defined]
    return server


def _json_request(url: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    body = canonical_json(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise LauncherError(f"upstream returned non-object JSON: {url}")
    return value


def wait_for_upstream(base_url: str, model_alias: str, child: subprocess.Popen[Any], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error = "no response"
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise LauncherError(f"llama-server exited during startup with code {child.returncode}")
        try:
            models = _json_request(base_url + "/v1/models", None, min(5, timeout))
            ids = [str(row.get("id")) for row in models.get("data", []) if isinstance(row, dict)]
            if model_alias not in ids:
                last_error = f"model alias {model_alias!r} not advertised"
            else:
                chat = _json_request(
                    base_url + "/v1/chat/completions",
                    {
                        "model": model_alias,
                        "messages": [{"role": "user", "content": "Reply with the word ready."}],
                        "temperature": 0,
                        "max_tokens": 8,
                    },
                    min(30, timeout),
                )
                content = str(chat.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
                if content:
                    return
                last_error = "startup chat completion was empty"
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError, IndexError, TypeError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise LauncherError(f"llama-server did not become ready within {timeout:g}s: {last_error}")


def _terminate_owned(child: subprocess.Popen[Any], timeout: float = 15) -> dict[str, Any]:
    was_running = child.poll() is None
    forced = False
    if was_running:
        child.terminate()
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            forced = True
            child.kill()
            child.wait(timeout=timeout)
    return {
        "owned_pid": child.pid,
        "was_running": was_running,
        "terminated": child.poll() is not None,
        "forced_kill": forced,
        "exit_code": child.returncode,
    }


def parser() -> argparse.ArgumentParser:
    _, runtime_root, _, _, _ = configured_paths()
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--llama-server", required=True)
    command.add_argument("--base-model", type=Path, required=True)
    command.add_argument("--base-model-id", required=True)
    command.add_argument("--adapter", type=Path, required=True)
    command.add_argument("--adapter-label", required=True)
    command.add_argument("--model-alias", required=True)
    command.add_argument("--host", default="127.0.0.1")
    command.add_argument("--port", type=int, required=True)
    command.add_argument("--upstream-port", type=int, default=0)
    command.add_argument("--ctx-size", type=int, default=2048)
    command.add_argument("--threads", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    command.add_argument("--gpu-layers", type=int, default=0)
    command.add_argument("--startup-timeout", type=float, default=180)
    command.add_argument(
        "--max-runtime-seconds",
        type=float,
        default=0,
        help="stop cleanly after this many ready-state seconds; zero runs until interrupted",
    )
    command.add_argument("--output-root", type=Path, default=runtime_root / "attested_launches")
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.host not in LOOPBACK:
        raise SystemExit("attested adapter proxy is loopback-only")
    if args.max_runtime_seconds < 0:
        raise SystemExit("max-runtime-seconds cannot be negative")
    executable = resolve_executable(args.llama_server)
    base_model = args.base_model.expanduser().resolve()
    adapter = args.adapter.expanduser().resolve()
    if not base_model.is_file() or not adapter.is_file():
        raise SystemExit("base model and adapter must be existing files")
    if base_model.suffix.lower() != ".gguf" or adapter.suffix.lower() != ".gguf":
        raise SystemExit("the attested llama.cpp path requires GGUF base and adapter files")
    upstream_port = args.upstream_port or reserve_port()
    if upstream_port == args.port:
        raise SystemExit("public and upstream ports must differ")
    output_root = args.output_root.expanduser().resolve() / args.adapter_label
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "launch_manifest.json"
    shutdown_token_path = output_root / "shutdown.token"
    if manifest_path.exists():
        raise SystemExit(f"refusing to overwrite an existing launch manifest: {manifest_path}")
    hashes = {
        "llama_server_sha256": sha256_file(executable),
        "base_model_sha256": sha256_file(base_model),
        "adapter_sha256": sha256_file(adapter),
    }
    command = build_llama_command(
        executable,
        base_model,
        adapter,
        model_alias=args.model_alias,
        upstream_port=upstream_port,
        context_size=args.ctx_size,
        threads=args.threads,
        gpu_layers=args.gpu_layers,
    )
    before_gpu = gpu_snapshot()
    stdout_path = output_root / "llama.stdout.log"
    stderr_path = output_root / "llama.stderr.log"
    child: subprocess.Popen[Any] | None = None
    proxy: ThreadingHTTPServer | None = None
    shutdown_token = secrets.token_urlsafe(32)
    with shutdown_token_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(shutdown_token + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    manifest: dict[str, Any] = {
        "schema_version": "pixie_attested_llama_launch_v1",
        "status": "STARTING",
        "runtime": RUNTIME_ID,
        "started_at": utc_now(),
        "adapter_label": args.adapter_label,
        "base_model_id": args.base_model_id,
        "model_alias": args.model_alias,
        "public_route": {"host": args.host, "port": args.port},
        "upstream": {"host": "127.0.0.1", "port": upstream_port},
        "files": {
            "llama_server": str(executable),
            "base_model": str(base_model),
            "adapter": str(adapter),
        },
        "hashes": hashes,
        "command": command,
        "gpu_before": before_gpu,
    }
    atomic_json(manifest_path, manifest)
    try:
        with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            child = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                shell=False,
                creationflags=creationflags,
            )
            manifest["owned_pid"] = child.pid
            atomic_json(manifest_path, manifest)
            upstream_base = f"http://127.0.0.1:{upstream_port}"
            wait_for_upstream(upstream_base, args.model_alias, child, args.startup_timeout)
            identity = {
                "schema_version": "pixie_adapter_identity_v1",
                "runtime": RUNTIME_ID,
                "adapter_label": args.adapter_label,
                "adapter_sha256": hashes["adapter_sha256"],
                "base_model_id": args.base_model_id,
                "base_model_sha256": hashes["base_model_sha256"],
                "llama_server_sha256": hashes["llama_server_sha256"],
                "model_alias": args.model_alias,
                "owned_pid": child.pid,
            }
            proxy = make_proxy_server(
                args.host,
                args.port,
                ProxyState(upstream_base, identity, shutdown_token=shutdown_token),
            )
            manifest["status"] = "READY"
            manifest["ready_at"] = utc_now()
            manifest["identity"] = identity
            atomic_json(manifest_path, manifest)

            def stop_when_child_exits() -> None:
                assert child is not None and proxy is not None
                child.wait()
                proxy.shutdown()

            watcher = threading.Thread(target=stop_when_child_exits, daemon=True)
            watcher.start()
            stop_timer = None
            if args.max_runtime_seconds:
                stop_timer = threading.Timer(args.max_runtime_seconds, proxy.shutdown)
                stop_timer.daemon = True
                stop_timer.start()
            print(f"Attested resident {args.adapter_label} listening at http://{args.host}:{args.port}")
            try:
                proxy.serve_forever(poll_interval=0.25)
            finally:
                if stop_timer is not None:
                    stop_timer.cancel()
            if child.poll() is not None:
                manifest["status"] = "FAILED"
                manifest["error"] = f"llama-server exited unexpectedly with code {child.returncode}"
    except KeyboardInterrupt:
        manifest["status"] = "STOPPED"
    except (LauncherError, OSError, subprocess.SubprocessError) as exc:
        manifest["status"] = "FAILED"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        print(manifest["error"], file=sys.stderr)
    finally:
        if proxy is not None:
            proxy.server_close()
        cleanup = _terminate_owned(child) if child is not None else {"owned_pid": None, "terminated": True}
        cleanup["gpu_after"] = gpu_snapshot()
        cleanup["passed"] = bool(cleanup.get("terminated"))
        manifest["cleanup"] = cleanup
        manifest["finished_at"] = utc_now()
        if manifest["status"] == "READY":
            manifest["status"] = "STOPPED" if cleanup["passed"] else "CLEANUP_FAILED"
        atomic_json(manifest_path, manifest)
        shutdown_token_path.unlink(missing_ok=True)
    return 0 if manifest["status"] == "STOPPED" and manifest["cleanup"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
