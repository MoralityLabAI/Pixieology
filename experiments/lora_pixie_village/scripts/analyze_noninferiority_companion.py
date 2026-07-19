#!/usr/bin/env python3
"""Score the frozen completed companion prefix inside the hard resource cap."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
for root in (APP_ROOT, REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import existing_adapter_pair  # noqa: E402
import multi_adapter_matrix  # noqa: E402
import multi_adapter_noninferiority as study  # noqa: E402
import server  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "pixieology.config.json")
    parser.add_argument("--protocol", type=Path, default=APP_ROOT / "config" / "multi_adapter_noninferiority_v1.json")
    parser.add_argument("--study-id", required=True)
    args = parser.parse_args(argv)
    if os.environ.get("PIXIE_RESOURCE_CAP_ACTIVE") != "1":
        raise SystemExit("companion checkpoint analysis must run inside run_capped_strict.ps1")
    protocol = study.load_protocol(args.protocol.resolve())
    paths = existing_adapter_pair.resolve_config_paths(args.config.resolve())
    root = paths["lora_pixie_village_runtime"] / "multi_adapter_noninferiority" / args.study_id
    output_path = root / "companion_checkpoint_analysis.json"
    receipt_path = root / "companion_checkpoint_receipt.json"
    pointer_path = APP_ROOT / "reports" / "multi_adapter_noninferiority_companion.receipt.json"
    if output_path.exists() or receipt_path.exists():
        raise SystemExit("refusing to overwrite companion checkpoint analysis")
    rows = study.read_generation_rows(root / "raw_generations.jsonl", protocol)
    hf_home = Path(os.environ.get("HF_HOME") or paths["hf_home"]).resolve()
    analysis = study.analyze_companion_checkpoint(rows, protocol, hf_home)
    server.atomic_json(output_path, analysis)
    receipt = {
        "schema_version": "pixie_multi_adapter_companion_checkpoint_receipt_v1",
        "status": analysis["status"],
        "overall_verdict": analysis["overall_verdict"],
        "companion_verdict": analysis["companion_verdict"],
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": multi_adapter_matrix.sha256_value(protocol),
        "analysis": str(output_path),
        "analysis_sha256": existing_adapter_pair.sha256_file(output_path),
        "comparison": analysis["comparison"],
        "means": analysis["means"],
        "limitations": analysis["limitations"],
    }
    server.atomic_json(receipt_path, receipt)
    pointer = {
        "schema_version": study.COMPANION_POINTER_SCHEMA,
        "status": receipt["status"],
        "run_id": args.study_id + "-companion-semantic",
        "overall_verdict": receipt["overall_verdict"],
        "companion_verdict": receipt["companion_verdict"],
        "receipt": str(receipt_path),
        "receipt_sha256": existing_adapter_pair.sha256_file(receipt_path),
        "comparison": receipt["comparison"],
        "means": receipt["means"],
        "limitations": receipt["limitations"],
    }
    server.atomic_json(pointer_path, pointer)
    print(json.dumps(pointer, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
