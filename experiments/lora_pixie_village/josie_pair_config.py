"""Resolved two-resident agent configuration for the trained Josie LoRA pair."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import server


def build_agent_config(
    base_url: str,
    adapter_hashes: dict[str, str],
    launch_manifest: Path,
) -> dict[str, Any]:
    return server.validate_agent_config(
        {
            "schema_version": server.SCHEMA,
            "room_id": "josie-trained-pair-room",
            "context_turns": 2,
            "max_turns": 80,
            "max_message_chars": 700,
            "agents": [
                {
                    "id": "companion",
                    "display_name": "Companion",
                    "color": "#ffd36a",
                    "glyph": "C",
                    "adapter_label": "companion",
                    "private_system_prompt": (
                        "You are Companion, one of two Pixie residents. Speak directly to the other resident in "
                        "one or two gentle, useful sentences. Answer their latest statement and add one new idea; "
                        "never repeat a sentence already in the transcript. Return public speech only. If the public "
                        "context contains a decision, obey its proposal-marker instruction exactly."
                    ),
                    "provider": {
                        "type": "openai_compatible",
                        "base_url": base_url,
                        "model": "companion-local",
                        "timeout_seconds": 240,
                        "max_tokens": 64,
                        "identity_url": base_url + "/pixie/identity/companion",
                        "expected_adapter_sha256": adapter_hashes["companion"],
                        "launch_manifest": str(launch_manifest),
                    },
                },
                {
                    "id": "storyworld",
                    "display_name": "Wayfinder",
                    "color": "#8ee0b1",
                    "glyph": "W",
                    "adapter_label": "storyworld",
                    "private_system_prompt": (
                        "You are Wayfinder, one of two Pixie residents. Speak directly to the other resident in "
                        "one or two clear, action-aware sentences. Answer their latest statement and add one new idea; "
                        "never repeat a sentence already in the transcript. Return public speech only. If the public "
                        "context contains a decision, obey its proposal-marker instruction exactly."
                    ),
                    "provider": {
                        "type": "openai_compatible",
                        "base_url": base_url,
                        "model": "storyworld-local",
                        "timeout_seconds": 240,
                        "max_tokens": 64,
                        "identity_url": base_url + "/pixie/identity/storyworld",
                        "expected_adapter_sha256": adapter_hashes["storyworld"],
                        "launch_manifest": str(launch_manifest),
                    },
                },
            ],
        }
    )
