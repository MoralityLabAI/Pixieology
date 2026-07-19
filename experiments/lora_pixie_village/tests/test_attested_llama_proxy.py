from __future__ import annotations

import json
import sys
import threading
import urllib.request
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import attested_llama_proxy as launcher  # noqa: E402
import mock_openai_endpoint  # noqa: E402


class RunningChild:
    returncode = None

    def poll(self):
        return self.returncode


def test_file_hash_and_llama_command_are_exact(tmp_path: Path) -> None:
    executable = tmp_path / "llama-server.exe"
    base = tmp_path / "base.gguf"
    adapter = tmp_path / "resident.gguf"
    executable.write_bytes(b"runtime")
    base.write_bytes(b"base")
    adapter.write_bytes(b"adapter")
    assert launcher.sha256_file(adapter) == "ae1eae1d76e5b7c865c4122ce366a08025842566d2d96c75cc13e6353a73db0d"
    command = launcher.build_llama_command(
        executable,
        base,
        adapter,
        model_alias="lumen-route",
        upstream_port=18081,
        context_size=1024,
        threads=2,
        gpu_layers=12,
    )
    assert command[0] == str(executable)
    assert command[command.index("-m") + 1] == str(base)
    assert command[command.index("--lora") + 1] == str(adapter)
    assert command[command.index("--alias") + 1] == "lumen-route"
    assert command[command.index("--n-gpu-layers") + 1] == "12"
    assert "shell" not in command


def test_attested_proxy_forwards_only_model_api_and_owns_identity() -> None:
    upstream = mock_openai_endpoint.make_server(
        "127.0.0.1",
        0,
        {
            "model": "lumen-route",
            "adapter_label": "ignored-upstream-label",
            "adapter_sha256": "0" * 64,
            "base_model_id": "mock-base",
            "voice": "LUMEN_HTTP",
        },
    )
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    identity = {
        "runtime": launcher.RUNTIME_ID,
        "adapter_label": "lumen-real",
        "adapter_sha256": "a" * 64,
        "base_model_id": "base-17",
    }
    proxy = launcher.make_proxy_server(
        "127.0.0.1",
        0,
        launcher.ProxyState(
            f"http://127.0.0.1:{upstream.server_address[1]}",
            identity,
            shutdown_token="test-secret",
        ),
    )
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    base = f"http://127.0.0.1:{proxy.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/pixie/identity", timeout=5) as response:
            observed = json.loads(response.read().decode("utf-8"))
        assert observed == identity
        with urllib.request.urlopen(base + "/v1/models", timeout=5) as response:
            models = json.loads(response.read().decode("utf-8"))
        assert models["data"][0]["id"] == "lumen-route"
        request = urllib.request.Request(
            base + "/v1/chat/completions",
            data=json.dumps(
                {
                    "model": "lumen-route",
                    "messages": [{"role": "user", "content": "hello"}],
                    "temperature": 0,
                    "max_tokens": 16,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            chat = json.loads(response.read().decode("utf-8"))
        assert chat["choices"][0]["message"]["content"].startswith("LUMEN_HTTP")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(base + "/private", timeout=5)
        assert error.value.code == 404
        bad_shutdown = urllib.request.Request(base + "/pixie/shutdown", data=b"{}", method="POST")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(bad_shutdown, timeout=5)
        assert error.value.code == 403
        good_shutdown = urllib.request.Request(
            base + "/pixie/shutdown",
            data=b"{}",
            headers={"X-Pixie-Shutdown-Token": "test-secret"},
            method="POST",
        )
        with urllib.request.urlopen(good_shutdown, timeout=5) as response:
            assert response.status == 202
        proxy_thread.join(timeout=5)
        assert not proxy_thread.is_alive()
    finally:
        proxy.shutdown()
        proxy.server_close()
        upstream.shutdown()
        upstream.server_close()
        proxy_thread.join(timeout=5)
        upstream_thread.join(timeout=5)


def test_launcher_is_loopback_only_and_readiness_checks_model_alias() -> None:
    with pytest.raises(launcher.LauncherError, match="loopback-only"):
        launcher.make_proxy_server("0.0.0.0", 0, launcher.ProxyState("http://127.0.0.1:9", {}))
    child = RunningChild()
    child.returncode = 2
    with pytest.raises(launcher.LauncherError, match="exited during startup"):
        launcher.wait_for_upstream("http://127.0.0.1:9", "missing", child, 0.1)  # type: ignore[arg-type]


def test_command_rejects_ambiguous_alias_and_invalid_resources(tmp_path: Path) -> None:
    file = tmp_path / "x"
    file.write_bytes(b"x")
    with pytest.raises(launcher.LauncherError, match="alias"):
        launcher.build_llama_command(
            file,
            file,
            file,
            model_alias="two words",
            upstream_port=8000,
            context_size=1024,
            threads=1,
            gpu_layers=0,
        )
    with pytest.raises(launcher.LauncherError, match="context"):
        launcher.build_llama_command(
            file,
            file,
            file,
            model_alias="route",
            upstream_port=8000,
            context_size=16,
            threads=1,
            gpu_layers=0,
        )
