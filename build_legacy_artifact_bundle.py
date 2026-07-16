"""Build a cloud-uploadable archive from local-only Pixieology legacy artifacts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from pixie_env import config_path, repo_path


ADAPTER_FILES = (
    "adapter_model.safetensors",
    "adapter_config.json",
    "training_manifest.json",
    "README.md",
    "tokenizer_config.json",
    "chat_template.jinja",
    "special_tokens_map.json",
)
GOLDEN_ROUND = "round_141_1.7B"


@dataclass(frozen=True)
class ArtifactEntry:
    source: Path
    archive_path: str
    producer: str
    record_count: int | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=config_path("fae_switch_synth"))
    parser.add_argument("--overnight-root", type=Path, default=config_path("overnight_work_root"))
    parser.add_argument("--output-dir", type=Path, default=config_path("legacy_bundle_output_dir"))
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--golden-round", default=GOLDEN_ROUND)
    parser.add_argument("--consolidated-checkpoint", type=Path, action="append", default=[])
    return parser.parse_args()


def jsonl_record_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def json_record_count(path: Path) -> int | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return len(payload) if isinstance(payload, list) else None
    for key in ("record_count", "records", "rows", "task_count"):
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, list):
            return len(value)
    stats = payload.get("dataset_stats")
    if isinstance(stats, dict) and isinstance(stats.get("rows_used"), int):
        return int(stats["rows_used"])
    return None


def inferred_record_count(path: Path) -> int | None:
    if path.suffix.casefold() == ".jsonl":
        return jsonl_record_count(path)
    if path.suffix.casefold() == ".json":
        return json_record_count(path)
    return None


def round_sort_key(path: Path) -> tuple[int, str]:
    try:
        number = int(path.name.split("_", 2)[1])
    except (IndexError, ValueError):
        number = sys.maxsize
    return number, path.name


def add_entry(
    entries: dict[str, ArtifactEntry],
    source: Path,
    archive_path: str,
    producer: str,
    record_count: int | None = None,
) -> None:
    if not source.is_file():
        return
    normalized = archive_path.replace("\\", "/")
    if normalized in entries and entries[normalized].source.resolve() != source.resolve():
        raise ValueError(f"Archive path collision for {normalized}")
    entries[normalized] = ArtifactEntry(
        source=source,
        archive_path=normalized,
        producer=producer,
        record_count=inferred_record_count(source) if record_count is None else record_count,
    )


def collect_entries(args: argparse.Namespace) -> tuple[list[ArtifactEntry], list[str]]:
    entries: dict[str, ArtifactEntry] = {}
    notes: list[str] = []
    add_entry(
        entries,
        args.dataset,
        "data/fae_switch_synth.jsonl",
        "Fae switch synthetic trajectory builder (normalized training/eval pairs).",
    )
    if not args.dataset.is_file():
        raise FileNotFoundError(f"Required legacy dataset not found: {args.dataset}")
    if not args.overnight_root.is_dir():
        raise FileNotFoundError(f"Overnight sweep root not found: {args.overnight_root}")

    add_entry(
        entries,
        args.overnight_root / "overnight_log.jsonl",
        "overnight/overnight_log.jsonl",
        "overnight_pixie_loop.py orchestration event log.",
    )
    for name in ("overnight_pixie.log", "overnight_pixie_error.log", "session_summary_2026-03-27.md"):
        add_entry(
            entries,
            repo_path(name),
            f"receipts/{name}",
            "Local Pixieology launcher/session receipt.",
        )

    round_dirs = sorted(
        (path for path in args.overnight_root.glob("round_*") if path.is_dir()),
        key=round_sort_key,
    )
    if not round_dirs:
        raise ValueError(f"No round directories found below {args.overnight_root}")

    for round_dir in round_dirs:
        prefix = f"overnight/{round_dir.name}"
        for name in ("loop_manifest.json", "loop_report.json"):
            add_entry(
                entries,
                round_dir / name,
                f"{prefix}/{name}",
                "auto_research_tinylora_loop.py loop receipt.",
            )
        for path in round_dir.rglob("_run_manifest.json"):
            add_entry(
                entries,
                path,
                f"{prefix}/{path.relative_to(round_dir).as_posix()}",
                "Tesseract QLoRA training run manifest.",
            )
        for path in round_dir.glob("round_*/data/normalized_trajectories/*.jsonl"):
            add_entry(
                entries,
                path,
                f"{prefix}/{path.relative_to(round_dir).as_posix()}",
                "auto_research_tinylora_loop.py normalized trajectory output.",
            )
        for adapter_model in round_dir.glob("round_*/data/models/adapters/**/adapter_model.safetensors"):
            if any(part.startswith("checkpoint-") for part in adapter_model.parts):
                continue
            adapter_dir = adapter_model.parent
            training_count = json_record_count(adapter_dir / "training_manifest.json")
            for name in ADAPTER_FILES:
                path = adapter_dir / name
                add_entry(
                    entries,
                    path,
                    f"{prefix}/{path.relative_to(round_dir).as_posix()}",
                    "Tesseract train_qlora.py final TinyLoRA adapter output.",
                    record_count=training_count,
                )

    golden_dir = args.overnight_root / args.golden_round
    golden_checkpoints = list(golden_dir.glob("round_*/data/models/adapters/**/checkpoint-*"))
    if not golden_checkpoints:
        notes.append(f"No resumable checkpoint found for configured golden round {args.golden_round}.")
    for checkpoint in golden_checkpoints:
        if not checkpoint.is_dir():
            continue
        training_manifest = checkpoint.parent / "training_manifest.json"
        training_count = json_record_count(training_manifest)
        for path in checkpoint.rglob("*"):
            if path.is_file():
                add_entry(
                    entries,
                    path,
                    f"overnight/{golden_dir.name}/{path.relative_to(golden_dir).as_posix()}",
                    "Tesseract train_qlora.py resumable checkpoint for the recorded golden round.",
                    record_count=training_count,
                )

    consolidated_found = 0
    for checkpoint in args.consolidated_checkpoint:
        if not checkpoint.exists():
            notes.append(f"Configured consolidated checkpoint was absent: {checkpoint}")
            continue
        paths = [checkpoint] if checkpoint.is_file() else [path for path in checkpoint.rglob("*") if path.is_file()]
        for path in paths:
            relative = path.name if checkpoint.is_file() else path.relative_to(checkpoint).as_posix()
            add_entry(
                entries,
                path,
                f"consolidated/{checkpoint.name}/{relative}",
                "Consolidated QLoRA checkpoint supplied on the bundle command line.",
            )
            consolidated_found += 1
    if consolidated_found == 0:
        notes.append(
            "No local consolidated QLoRA checkpoint was available; the uploaded merged v1 model was not retained locally. "
            "All final TinyLoRA adapters plus the golden round checkpoint are included instead."
        )

    return sorted(entries.values(), key=lambda entry: entry.archive_path), notes


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_text(entries: list[ArtifactEntry], notes: list[str], args: argparse.Namespace) -> str:
    total_bytes = sum(entry.source.stat().st_size for entry in entries)
    lines = [
        "# Pixieology Legacy Artifacts Manifest",
        "",
        f"- Bundle date: `{args.date}`",
        f"- Generated at: `{datetime.now(timezone.utc).isoformat()}`",
        f"- Files (excluding this manifest): `{len(entries)}`",
        f"- Uncompressed bytes: `{total_bytes}`",
        f"- Overnight round directories: `{len({entry.archive_path.split('/')[1] for entry in entries if entry.archive_path.startswith('overnight/round_')})}`",
        f"- Golden checkpoint selection: `{args.golden_round}` (recorded in `session_summary_2026-03-27.md` as the peak 1.7B adapter)",
        "",
        "## Selection and provenance",
        "",
        "The archive contains the required local-only synthetic JSONL, every overnight loop report and normalized trajectory, "
        "every final TinyLoRA adapter without duplicate per-round base tokenizer payloads, and the full resumable checkpoint "
        "for the recorded golden round. Binary adapter rows inherit the training-record count from their sibling training manifest.",
        "",
    ]
    if notes:
        lines.extend(["## Notes", "", *[f"- {note}" for note in notes], ""])
    lines.extend(
        [
            "## Files",
            "",
            "| Archive path | Produced by | Records | Modified (UTC) | Bytes | SHA-256 |",
            "|---|---|---:|---|---:|---|",
        ]
    )
    for index, entry in enumerate(entries, start=1):
        stat = entry.source.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        records = str(entry.record_count) if entry.record_count is not None else "n/a"
        digest = sha256_file(entry.source)
        producer = entry.producer.replace("|", "\\|")
        lines.append(
            f"| `{entry.archive_path}` | {producer} | {records} | `{modified}` | {stat.st_size} | `{digest}` |"
        )
        if index % 100 == 0 or index == len(entries):
            print(f"Hashed {index}/{len(entries)} files", flush=True)
    lines.append("")
    return "\n".join(lines)


def create_bundle(entries: list[ArtifactEntry], manifest: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing bundle: {output}")
    with zipfile.ZipFile(output, "w", allowZip64=True) as archive:
        archive.writestr("MANIFEST.md", manifest, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        for index, entry in enumerate(entries, start=1):
            stored = entry.source.suffix.casefold() in {".safetensors", ".pt", ".pth", ".bin"}
            archive.write(
                entry.source,
                entry.archive_path,
                compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED,
                compresslevel=None if stored else 6,
            )
            if index % 50 == 0 or index == len(entries):
                print(f"Archived {index}/{len(entries)} files", flush=True)


def main() -> int:
    args = parse_args()
    if not args.date.isdigit() or len(args.date) != 8:
        raise ValueError("--date must be YYYYMMDD")
    entries, notes = collect_entries(args)
    print(f"Collected {len(entries)} files", flush=True)
    manifest = manifest_text(entries, notes, args)
    output = args.output_dir / f"pixieology_legacy_artifacts_{args.date}.zip"
    manifest_path = args.output_dir / f"pixieology_legacy_artifacts_{args.date}_MANIFEST.md"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest, encoding="utf-8", newline="\n")
    create_bundle(entries, manifest, output)
    archive_digest = sha256_file(output)
    checksum_path = output.with_suffix(output.suffix + ".sha256")
    checksum_path.write_text(f"{archive_digest}  {output.name}\n", encoding="ascii")
    print(
        json.dumps(
            {
                "archive": str(output.resolve()),
                "archive_bytes": output.stat().st_size,
                "archive_sha256": archive_digest,
                "manifest": str(manifest_path.resolve()),
                "file_count": len(entries) + 1,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
