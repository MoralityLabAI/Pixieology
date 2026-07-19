from __future__ import annotations

import sys
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import dual_lora_proxy as dual  # noqa: E402


def routes() -> dict[str, dict]:
    return {
        "companion-local": {"label": "companion", "model_alias": "companion-local", "adapter_id": 0},
        "storyworld-local": {"label": "storyworld", "model_alias": "storyworld-local", "adapter_id": 1},
    }


def test_request_selects_exactly_one_lora_and_disables_cache() -> None:
    forwarded, route = dual.prepare_forward_payload(
        {"model": "storyworld-local", "messages": [{"role": "user", "content": "hello"}]},
        routes(),
    )
    assert route["label"] == "storyworld"
    assert forwarded["model"] == dual.BACKEND_ALIAS
    assert forwarded["lora"] == [{"id": 0, "scale": 0.0}, {"id": 1, "scale": 1.0}]
    assert forwarded["cache_prompt"] is False
    assert forwarded["stream"] is False
    assert forwarded["chat_template_kwargs"] == {"enable_thinking": False}


def test_request_rejects_unknown_model_and_streaming() -> None:
    with pytest.raises(dual.DualRouteError, match="unknown logical resident"):
        dual.prepare_forward_payload({"model": "base"}, routes())
    with pytest.raises(dual.DualRouteError, match="streaming responses"):
        dual.prepare_forward_payload({"model": "companion-local", "stream": True}, routes())


def test_request_can_activate_both_loras_from_frozen_route() -> None:
    matrix = dual.multi_adapter_matrix.load_matrix(dual.DEFAULT_MATRIX)
    routed = dual.multi_adapter_matrix.build_routes(
        matrix,
        [Path("companion.gguf"), Path("storyworld.gguf")],
        ["a" * 64, "b" * 64],
    )
    forwarded, route = dual.prepare_forward_payload(
        {"model": "stacked-local", "messages": [{"role": "user", "content": "hello"}]},
        routed,
    )
    assert route["condition_id"] == "stacked"
    assert forwarded["lora"] == [{"id": 0, "scale": 1.0}, {"id": 1, "scale": 1.0}]


def test_llama_command_loads_both_loras_inactive() -> None:
    command = dual.build_llama_command(
        Path("llama-server.exe"),
        Path("base.gguf"),
        [Path("companion.gguf"), Path("storyworld.gguf")],
        upstream_port=9001,
        context_size=1024,
        threads=4,
        gpu_layers=0,
    )
    assert command[command.index("--lora") + 1] == "companion.gguf,storyworld.gguf"
    assert "--lora-init-without-apply" in command
    assert command[command.index("--n-gpu-layers") + 1] == "0"
    assert command[command.index("--parallel") + 1] == "1"
    assert command[command.index("--reasoning") + 1] == "off"
    assert command[command.index("--cache-ram") + 1] == "0"
