from __future__ import annotations

import json
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import josie_pair_config  # noqa: E402
import provider_preflight  # noqa: E402
import server  # noqa: E402


def test_real_pair_config_has_two_distinct_attested_routes_and_redacts_them(tmp_path: Path) -> None:
    config = josie_pair_config.build_agent_config(
        "http://127.0.0.1:8081",
        {"companion": "a" * 64, "storyworld": "b" * 64},
        tmp_path / "launch_manifest.json",
    )
    routes = provider_preflight.validate_unique_routes(config)
    assert [row["model"] for row in routes] == ["companion-local", "storyworld-local"]
    assert {row["adapter_label"] for row in config["agents"]} == {"companion", "storyworld"}
    public = json.dumps(server.public_config(config))
    assert "127.0.0.1" not in public
    assert "expected_adapter_sha256" not in public
    assert "private_system_prompt" not in public
