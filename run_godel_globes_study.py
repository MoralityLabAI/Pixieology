from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any, Sequence

from pixie_env import (
    godel_globes_ab_result_path,
    godel_globes_experiment_root,
    godel_globes_study_receipts_path,
)


PARTICIPANT_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class StudyRunnerError(RuntimeError):
    """Raised when the local study cannot be launched or analyzed safely."""


def build_study_url(index_path: Path, participant: str, round_number: int, condition: str | None = None) -> str:
    participant = participant.strip()
    if not PARTICIPANT_RE.fullmatch(participant):
        raise StudyRunnerError("participant must be a 1-64 character anonymous code using letters, numbers, _ or -")
    if round_number not in {1, 2}:
        raise StudyRunnerError("round must be 1 or 2")
    if condition not in {None, "embodied", "flat"}:
        raise StudyRunnerError("condition must be embodied or flat")
    query: dict[str, str | int] = {"participant": participant, "round": round_number}
    if condition:
        query["condition"] = condition
    return f"{index_path.resolve().as_uri()}?{urllib.parse.urlencode(query)}"


def receipt_files(receipt_dir: Path) -> list[Path]:
    if not receipt_dir.exists():
        return []
    if not receipt_dir.is_dir():
        raise StudyRunnerError(f"receipt path is not a directory: {receipt_dir}")
    return sorted(path for path in receipt_dir.glob("*.json") if path.is_file())


def resolve_node(executable: str) -> str:
    candidate = Path(executable).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    resolved = shutil.which(executable)
    if not resolved:
        raise StudyRunnerError(f"Node.js executable not found: {executable}")
    return resolved


def run_analysis(receipt_dir: Path, analyzer_path: Path, node_executable: str = "node") -> dict[str, Any]:
    if not analyzer_path.is_file():
        raise StudyRunnerError(f"study analyzer not found: {analyzer_path}")
    command = [resolve_node(node_executable), str(analyzer_path), *(str(path) for path in receipt_files(receipt_dir))]
    completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    if completed.returncode != 0:
        error = (completed.stderr or completed.stdout).strip()
        raise StudyRunnerError(f"study analysis failed ({completed.returncode}): {error}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise StudyRunnerError("study analyzer returned invalid JSON") from exc
    if not isinstance(payload, dict) or payload.get("study_id") != "godel_globes_5d_character_ab_v1":
        raise StudyRunnerError("study analyzer returned an unexpected result schema")
    return payload


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_name = handle.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name:
            temporary = Path(temporary_name)
            if temporary.exists():
                temporary.unlink()


def ingest_receipt(source: Path, receipt_dir: Path) -> Path:
    if not source.is_file():
        raise StudyRunnerError(f"receipt file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StudyRunnerError(f"receipt is not valid UTF-8 JSON: {source}") from exc
    if not isinstance(payload, dict) or payload.get("study_id") != "godel_globes_5d_character_ab_v1":
        raise StudyRunnerError("receipt has an unexpected study_id")
    participant = str(payload.get("participant_id") or "")
    if not PARTICIPANT_RE.fullmatch(participant):
        raise StudyRunnerError("receipt participant_id is not an anonymous study code")
    round_number = payload.get("round")
    condition = payload.get("condition")
    if round_number not in {1, 2} or condition not in {"embodied", "flat"}:
        raise StudyRunnerError("receipt has an invalid round or condition")
    task_results = payload.get("task_results")
    if not isinstance(task_results, list) or len(task_results) != 5:
        raise StudyRunnerError("receipt is incomplete: exactly five task results are required")
    debrief = payload.get("debrief")
    if not isinstance(debrief, dict) or not debrief.get("reflection_location") or not debrief.get("map_meaning"):
        raise StudyRunnerError("receipt is incomplete: the debrief must be saved before export")
    destination = receipt_dir / f"{participant}-round-{round_number}-{condition}.json"
    if destination.exists():
        try:
            existing = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StudyRunnerError(f"existing receipt is unreadable: {destination}") from exc
        if existing != payload:
            raise StudyRunnerError(f"refusing to overwrite a different receipt: {destination}")
        return destination
    write_json_atomic(destination, payload)
    return destination


def parser() -> argparse.ArgumentParser:
    root = godel_globes_experiment_root()
    cli = argparse.ArgumentParser(description="Launch and analyze the local five-dimensional Gödel Globes study.")
    cli.add_argument("--experiment-root", type=Path, default=root)
    cli.add_argument("--receipts", type=Path, default=godel_globes_study_receipts_path())
    cli.add_argument("--result", type=Path, default=godel_globes_ab_result_path())
    cli.add_argument("--node", default="node")
    commands = cli.add_subparsers(dest="command", required=True)

    launch = commands.add_parser("launch", help="Open one anonymous participant round in the default browser.")
    launch.add_argument("--participant", required=True)
    launch.add_argument("--round", type=int, choices=(1, 2), required=True)
    launch.add_argument("--condition", choices=("embodied", "flat"))
    launch.add_argument("--dry-run", action="store_true")

    ingest = commands.add_parser("ingest", help="Validate and copy one exported receipt into the configured store.")
    ingest.add_argument("--file", type=Path, required=True)
    commands.add_parser("status", help="Analyze current receipts without writing a result.")
    commands.add_parser("analyze", help="Analyze current receipts and atomically write the configured result.")
    return cli


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    analyzer = args.experiment_root / "analyze_study.mjs"
    try:
        if args.command == "launch":
            index = args.experiment_root / "index.html"
            if not index.is_file():
                raise StudyRunnerError(f"study page not found: {index}")
            url = build_study_url(index, args.participant, args.round, args.condition)
            print(url)
            if not args.dry_run and not webbrowser.open(url, new=2):
                raise StudyRunnerError("the default browser did not accept the local study URL")
            return 0

        if args.command == "ingest":
            destination = ingest_receipt(args.file, args.receipts)
            print(destination)
            return 0

        payload = run_analysis(args.receipts, analyzer, args.node)
        if args.command == "analyze":
            write_json_atomic(args.result, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    except StudyRunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
