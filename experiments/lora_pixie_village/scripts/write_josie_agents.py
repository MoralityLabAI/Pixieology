#!/usr/bin/env python3
"""Write an attested village agent config for a named live dual-LoRA run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
for root in (APP_ROOT, REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import existing_adapter_pair  # noqa: E402
import josie_pair_config  # noqa: E402
import server  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "pixieology.config.json")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8081")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    config_path = args.config.expanduser().resolve()
    paths = existing_adapter_pair.resolve_config_paths(config_path)
    adapters = {
        "companion": paths["lora_pixie_companion_adapter_gguf"],
        "storyworld": paths["lora_pixie_storyworld_adapter_gguf"],
    }
    for label, path in adapters.items():
        if not path.is_file():
            raise SystemExit(f"missing {label} GGUF adapter: {path}")
    launch_manifest = (
        paths["lora_pixie_village_runtime"]
        / "dual_lora_launches"
        / args.run_id
        / "launch_manifest.json"
    )
    output = (
        args.out.expanduser().resolve()
        if args.out
        else paths["lora_pixie_village_runtime"] / "live_configs" / f"{args.run_id}.agents.json"
    )
    config = josie_pair_config.build_agent_config(
        args.base_url.rstrip("/"),
        {label: existing_adapter_pair.sha256_file(path) for label, path in adapters.items()},
        launch_manifest,
    )
    server.atomic_json(output, config)
    result = {
        "status": "PASS",
        "run_id": args.run_id,
        "agents": str(output),
        "config_sha256": config["config_hash"],
        "launch_manifest": str(launch_manifest),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
