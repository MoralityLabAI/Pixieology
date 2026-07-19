#!/usr/bin/env python3
"""Development-only OpenAI-compatible endpoint with adapter identity receipt.

It contains no model and must never be reported as LoRA behavior. It exists to
exercise two real HTTP routes, model discovery, attestation, and village parsing.
"""

from __future__ import annotations

import argparse
import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


PROPOSAL_IDS = ("propose", "ally", "betray", "wait")


class MockHandler(BaseHTTPRequestHandler):
    server_version = "PixieMockOpenAI/1.0"

    @property
    def settings(self) -> dict[str, Any]:
        return self.server.settings  # type: ignore[attr-defined]

    def _send(self, status: int, payload: Any) -> None:
        body = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        value = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        return value if isinstance(value, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/models":
            self._send(HTTPStatus.OK, {"object": "list", "data": [{"id": self.settings["model"], "object": "model"}]})
            return
        if self.path == "/pixie/identity":
            identity = {
                "adapter_label": self.settings["adapter_label"],
                "adapter_sha256": self.settings["adapter_sha256"],
                "base_model_id": self.settings["base_model_id"],
                "runtime": self.settings.get("runtime", "development_mock_no_model"),
            }
            for key in (
                "schema_version",
                "base_model_sha256",
                "llama_server_sha256",
                "model_alias",
                "owned_pid",
            ):
                if key in self.settings:
                    identity[key] = self.settings[key]
            self._send(HTTPStatus.OK, identity)
            return
        self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        payload = self._body()
        if payload.get("model") != self.settings["model"]:
            self._send(HTTPStatus.BAD_REQUEST, {"error": "wrong_model"})
            return
        messages = payload.get("messages", [])
        prompt = "\n".join(str(row.get("content") or "") for row in messages if isinstance(row, dict))
        legal_match = re.search(r"Legal ACTION_ID values: ([^.]+)", prompt)
        marker = ""
        if legal_match:
            legal = [part.strip() for part in legal_match.group(1).split(",")]
            chosen = next((item for item in legal if item in PROPOSAL_IDS), legal[0])
            marker = f" [proposal:{chosen}]"
        content = f"{self.settings['voice']} HTTP route is present and speaking publicly.{marker}"
        self._send(
            HTTPStatus.OK,
            {
                "id": f"mock-{self.settings['model']}",
                "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "model": self.settings["model"],
            },
        )

    def log_message(self, format: str, *args: Any) -> None:
        return


def make_server(host: str, port: int, settings: dict[str, Any]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), MockHandler)
    server.settings = settings  # type: ignore[attr-defined]
    return server


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--host", default="127.0.0.1")
    command.add_argument("--port", type=int, required=True)
    command.add_argument("--model", required=True)
    command.add_argument("--adapter-label", required=True)
    command.add_argument("--adapter-sha256", required=True)
    command.add_argument("--base-model-id", default="mock-base")
    command.add_argument("--voice", required=True)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    settings = {
        "model": args.model,
        "adapter_label": args.adapter_label,
        "adapter_sha256": args.adapter_sha256.lower(),
        "base_model_id": args.base_model_id,
        "voice": args.voice,
    }
    server = make_server(args.host, args.port, settings)
    print(f"Development mock {args.model} listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
