from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from pixie_env import (
    bridge_run_script,
    constitution_seed_path,
    model_id,
    repo_path,
    research_output_path,
    soul_path,
    tesseract_loop_script,
)

PIXIE_ROOT = repo_path()
TESSERACT_LOOP = tesseract_loop_script()
DICT_SAE = PIXIE_ROOT / "pixie_dictionary_sae_overnight.py"
BRIDGE_RUN = bridge_run_script()
SOUL_PATH = soul_path()
MERGE_ENV = PIXIE_ROOT / "build_pixue_soul_env.py"

MODELS = [
    {
        "name": "0.8B",
        "base_model": model_id("base_0_8b"),
        "probe_model": model_id("base_0_8b"),
        "rounds": 2,
        "max_records_per_round": 96,
        "max_steps": 10,
        "learning_rate": "8e-4",
    },
    {
        "name": "1.7B",
        "base_model": model_id("base_1_7b"),
        "probe_model": model_id("base_1_7b"),
        "rounds": 2,
        "max_records_per_round": 96,
        "max_steps": 10,
        "learning_rate": "8e-4",
    },
    {
        "name": "2B",
        "base_model": model_id("base_2b"),
        "probe_model": model_id("base_2b"),
        "rounds": 2,
        "max_records_per_round": 96,
        "max_steps": 10,
        "learning_rate": "7e-4",
    },
]


def parse_args():
    parser = argparse.ArgumentParser(description="Overnight Pixie hill-climb across 0.8B, 1.7B, and 2B.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=research_output_path("pixie_fae_hillclimb"),
    )
    parser.add_argument("--trigger-word", default="[[FAE_TOGGLE]]")
    parser.add_argument("--max-new-tokens", type=int, default=40)
    return parser.parse_args()


def run_cmd(cmd, cwd, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(json.dumps({"ts": time.time(), "event": "start", "cmd": cmd}) + "\n")
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(json.dumps(
            {
                "ts": time.time(),
                "event": "finish",
                "cmd": cmd,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-12000:],
                "stderr": proc.stderr[-12000:],
            },
            ensure_ascii=False,
        ) + "\n")
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    args = parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    log_path = args.output_root / "overnight_log.jsonl"

    merge_output = args.output_root / "pixue_soul_fae.jsonl"
    merge_manifest = args.output_root / "pixue_soul_fae_manifest.json"
    rc, _, _ = run_cmd(
        [
            "python",
            str(MERGE_ENV),
            "--output",
            str(merge_output),
            "--manifest",
            str(merge_manifest),
        ],
        cwd=str(PIXIE_ROOT),
        log_path=log_path,
    )
    if rc != 0:
        raise SystemExit(rc)

    for model in MODELS:
        model_dir = args.output_root / model["name"]
        model_dir.mkdir(parents=True, exist_ok=True)

        run_cmd(
            [
                "python",
                str(BRIDGE_RUN),
                "--soul-path",
                str(SOUL_PATH),
                "--episode-label",
                f"pixie_pre_{model['name']}",
            ],
            cwd=str(BRIDGE_RUN.parent),
            log_path=log_path,
        )

        loop_root = model_dir / "tinylora_loop"
        cmd = [
            "python",
            str(TESSERACT_LOOP),
            "--source-env",
            str(merge_output),
            "--work-root",
            str(loop_root),
            "--base-model",
            model["base_model"],
            "--constitution-manifest",
            str(repo_path("fae_world_model_manifest.json")),
            "--rounds",
            str(model["rounds"]),
            "--max-records-per-round",
            str(model["max_records_per_round"]),
            "--max-steps",
            str(model["max_steps"]),
            "--learning-rate",
            model["learning_rate"],
            "--batch-size",
            "1",
            "--generation-max-new-tokens",
            str(args.max_new_tokens),
        ]
        run_cmd(cmd, cwd=str(TESSERACT_LOOP.parent), log_path=log_path)

        probe_root = model_dir / "dictionary_sae"
        probe_cmd = [
            "python",
            str(DICT_SAE),
            "--model-id",
            model["probe_model"],
            "--seed-path",
            str(constitution_seed_path()),
            "--synth-path",
            str(repo_path("synthesized_pixie_dataset.jsonl")),
            "--output-root",
            str(probe_root),
        ]
        run_cmd(probe_cmd, cwd=str(PIXIE_ROOT), log_path=log_path)

        run_cmd(
            [
                "python",
                str(BRIDGE_RUN),
                "--soul-path",
                str(SOUL_PATH),
                "--episode-label",
                f"pixie_post_{model['name']}",
            ],
            cwd=str(BRIDGE_RUN.parent),
            log_path=log_path,
        )

    summary = {
        "output_root": str(args.output_root),
        "models": [model["name"] for model in MODELS],
        "merge_output": str(merge_output),
        "log_path": str(log_path),
    }
    (args.output_root / "overnight_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
