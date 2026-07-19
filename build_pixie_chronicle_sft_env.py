"""Verify an ALife chronicle corpus zip and build episode-grouped SFT splits."""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Iterable, Mapping
import zipfile

from pixie_env import config_path


ENV_ID = "pixie_chronicle_narration"
SOURCE_SFT_SCHEMA = "alife.chronicle.sft.v1"
EVENT_SCHEMA = "alife.chronicle.event.v1"
REPLAY_SCHEMA = "alife.chronicle.replay.v1"
CAMPAIGN_SCHEMA = "alife.chronicle.campaign.v1"
VERIFICATION_SCHEMA = "alife.chronicle.verification.v1"
OUTPUT_MANIFEST_SCHEMA = "pixieology.chronicle_sft_manifest.v1"
SPLIT_SALT = "pixieology-chronicle-episode-split-v1"
MAX_JSON_MEMBER_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 8 * 1024 * 1024 * 1024


class CorpusVerificationError(ValueError):
    """Raised before output is written when an ALife corpus receipt is invalid."""


@dataclass(frozen=True)
class VerifiedCorpus:
    archive_sha256: str
    manifest_sha256: str
    verification_receipt_sha256: str
    code_sha256: str
    episode_receipts: tuple[Mapping[str, Any], ...]
    records: tuple[Mapping[str, Any], ...]


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_stream(handle: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _safe_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    total = 0
    for info in archive.infolist():
        name = info.filename
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or ".." in path.parts
            or any(":" in part for part in path.parts)
        ):
            raise CorpusVerificationError(f"unsafe zip member: {name!r}")
        if name in members:
            raise CorpusVerificationError(f"duplicate zip member: {name}")
        if info.flag_bits & 0x1:
            raise CorpusVerificationError(f"encrypted zip member is not supported: {name}")
        members[name] = info
        total += info.file_size
    if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise CorpusVerificationError("chronicle corpus exceeds the uncompressed size cap")
    return members


def _member_bytes(
    archive: zipfile.ZipFile,
    members: Mapping[str, zipfile.ZipInfo],
    name: str,
    *,
    limit: int = MAX_JSON_MEMBER_BYTES,
) -> bytes:
    info = members.get(name)
    if info is None or info.is_dir():
        raise CorpusVerificationError(f"missing required corpus member: {name}")
    if info.file_size > limit:
        raise CorpusVerificationError(f"corpus member exceeds read limit: {name}")
    with archive.open(info, "r") as handle:
        return handle.read()


def _member_json(
    archive: zipfile.ZipFile, members: Mapping[str, zipfile.ZipInfo], name: str
) -> dict[str, Any]:
    try:
        value = json.loads(_member_bytes(archive, members, name).decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusVerificationError(f"invalid JSON member {name}: {exc}") from exc
    if not isinstance(value, dict):
        raise CorpusVerificationError(f"JSON member must contain an object: {name}")
    return value


def _member_jsonl(
    archive: zipfile.ZipFile, members: Mapping[str, zipfile.ZipInfo], name: str
) -> list[dict[str, Any]]:
    try:
        text = _member_bytes(archive, members, name).decode("utf-8-sig")
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusVerificationError(f"invalid JSONL member {name}: {exc}") from exc
    if any(not isinstance(row, dict) for row in rows):
        raise CorpusVerificationError(f"JSONL member must contain only objects: {name}")
    return rows


def _member_sha256(
    archive: zipfile.ZipFile, members: Mapping[str, zipfile.ZipInfo], name: str
) -> str:
    info = members.get(name)
    if info is None or info.is_dir():
        raise CorpusVerificationError(f"missing required corpus member: {name}")
    with archive.open(info, "r") as handle:
        return _sha256_stream(handle)


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _replay_contract(receipt: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "schema",
        "episode_id",
        "seed",
        "config_sha256",
        "code_sha256",
        "event_sha256",
        "final_state_sha256",
        "receipt_id",
    )
    return {key: receipt.get(key) for key in keys}


def _validate_sft_record(
    record: Mapping[str, Any], receipt: Mapping[str, Any], record_ids: set[str]
) -> list[str]:
    errors: list[str] = []
    required = {
        "schema",
        "record_id",
        "episode_id",
        "seed",
        "replay_receipt",
        "window",
        "biography_or_chronicle",
        "fact_list",
        "narration",
    }
    missing = sorted(required - set(record))
    if missing:
        return [f"missing SFT fields: {', '.join(missing)}"]
    _require(record.get("schema") == SOURCE_SFT_SCHEMA, "invalid SFT schema", errors)
    record_id = record.get("record_id")
    _require(isinstance(record_id, str) and bool(record_id), "invalid record_id", errors)
    if isinstance(record_id, str):
        _require(record_id not in record_ids, f"duplicate record_id: {record_id}", errors)
        record_ids.add(record_id)
    _require(record.get("episode_id") == receipt.get("episode_id"), "SFT episode_id differs from receipt", errors)
    _require(record.get("seed") == receipt.get("seed"), "SFT seed differs from receipt", errors)
    _require(record.get("narration") is None, "source narration must be null", errors)
    _require(record.get("replay_receipt") == _replay_contract(receipt), "SFT replay receipt differs from episode receipt", errors)

    window = record.get("window")
    sequences: set[int] = set()
    if not isinstance(window, list) or not window:
        errors.append("window must be a non-empty list")
    else:
        previous = -1
        for index, event in enumerate(window):
            if not isinstance(event, Mapping):
                errors.append(f"window[{index}] must be an object")
                continue
            _require(event.get("schema") == EVENT_SCHEMA, f"window[{index}] has invalid schema", errors)
            _require(event.get("episode_id") == receipt.get("episode_id"), f"window[{index}] episode mismatch", errors)
            sequence = event.get("sequence")
            if isinstance(sequence, bool) or not isinstance(sequence, int):
                errors.append(f"window[{index}] sequence must be an integer")
                continue
            _require(sequence > previous, "window sequences must be strictly increasing", errors)
            _require(sequence not in sequences, f"duplicate window sequence: {sequence}", errors)
            previous = sequence
            sequences.add(sequence)

    facts = record.get("fact_list")
    fact_ids: set[str] = set()
    if not isinstance(facts, list) or not facts:
        errors.append("fact_list must be a non-empty list")
    else:
        for index, fact in enumerate(facts):
            if not isinstance(fact, Mapping):
                errors.append(f"fact_list[{index}] must be an object")
                continue
            fact_id = fact.get("fact_id")
            predicate = fact.get("predicate")
            subject = fact.get("subject")
            evidence = fact.get("evidence_event_sequences")
            _require(isinstance(fact_id, str) and bool(fact_id), f"fact_list[{index}] invalid fact_id", errors)
            if isinstance(fact_id, str):
                _require(fact_id not in fact_ids, f"duplicate fact_id: {fact_id}", errors)
                fact_ids.add(fact_id)
            _require(isinstance(predicate, str) and bool(predicate), f"fact_list[{index}] invalid predicate", errors)
            _require(isinstance(subject, str) and bool(subject), f"fact_list[{index}] invalid subject", errors)
            _require(isinstance(evidence, list) and bool(evidence), f"fact_list[{index}] lacks evidence", errors)
            if isinstance(evidence, list):
                _require(
                    all(isinstance(value, int) and value in sequences for value in evidence),
                    f"fact_list[{index}] cites evidence outside its window",
                    errors,
                )

    typed = record.get("biography_or_chronicle")
    _require(
        isinstance(typed, Mapping)
        and typed.get("type") in {"biography", "chronicle"}
        and isinstance(typed.get("value"), Mapping),
        "biography_or_chronicle must be a typed object",
        errors,
    )
    return errors


def verify_chronicle_corpus(path: str | Path) -> VerifiedCorpus:
    """Verify ALife's stored SHA-256 receipts and return narration-ready rows.

    This validates stored artifact integrity and the producer's passed replay
    receipt. It does not rerun the ALife simulator; exact replay remains the
    producer-side verifier's responsibility.
    """

    archive_path = Path(path).expanduser()
    if not archive_path.is_file():
        raise FileNotFoundError(f"chronicle corpus zip does not exist: {archive_path}")
    archive_digest = sha256_file(archive_path)
    errors: list[str] = []
    records: list[Mapping[str, Any]] = []
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            members = _safe_members(archive)
            required = {
                "campaign_receipt.json",
                "episodes.jsonl",
                "frozen_manifest.json",
                "seed_manifest.json",
                "summary.json",
                "verification_receipt.json",
            }
            missing = sorted(required - set(members))
            if missing:
                raise CorpusVerificationError("missing required corpus members: " + ", ".join(missing))

            campaign = _member_json(archive, members, "campaign_receipt.json")
            summary = _member_json(archive, members, "summary.json")
            verification = _member_json(archive, members, "verification_receipt.json")
            episode_rows = _member_jsonl(archive, members, "episodes.jsonl")
            manifest_sha256 = _member_sha256(archive, members, "frozen_manifest.json")
            verification_sha256 = _member_sha256(archive, members, "verification_receipt.json")

            _require(campaign.get("schema") == CAMPAIGN_SCHEMA, "invalid campaign receipt schema", errors)
            _require(campaign.get("status") == "ok", "campaign receipt status is not ok", errors)
            _require(summary.get("schema") == CAMPAIGN_SCHEMA, "invalid summary schema", errors)
            _require(summary.get("status") == "ok", "campaign summary status is not ok", errors)
            _require(verification.get("schema") == VERIFICATION_SCHEMA, "invalid verification receipt schema", errors)
            _require(verification.get("status") == "passed", "corpus manifest verification did not pass", errors)
            _require(not verification.get("errors"), "verification receipt contains errors", errors)
            _require(not verification.get("replay_failures"), "verification receipt contains replay failures", errors)
            _require(verification.get("code_hash_matches") is True, "producer code hash did not match during verification", errors)
            _require(campaign.get("manifest_sha256") == manifest_sha256, "frozen manifest SHA-256 mismatch", errors)

            episode_count = len(episode_rows)
            _require(campaign.get("episode_count") == episode_count, "campaign episode count mismatch", errors)
            _require(summary.get("episode_count") == episode_count, "summary episode count mismatch", errors)
            _require(verification.get("episode_count") == episode_count, "verification episode count mismatch", errors)
            _require(
                int(verification.get("validated_sft_files", -1)) == episode_count,
                "not every episode SFT file was producer-validated",
                errors,
            )
            _require(
                verification.get("exact_event_byte_replays_passed") == verification.get("sampled_episodes"),
                "sampled event-byte replay count mismatch",
                errors,
            )

            source_hashes = campaign.get("files")
            if not isinstance(source_hashes, Mapping) or not source_hashes:
                errors.append("campaign receipt lacks source file hashes")
                source_hashes = {}
            verified_source_hashes: dict[str, str] = {}
            for relative, expected in source_hashes.items():
                member = f"source/{relative}"
                actual = _member_sha256(archive, members, member)
                _require(isinstance(expected, str) and actual == expected, f"source SHA-256 mismatch: {relative}", errors)
                verified_source_hashes[str(relative)] = actual
            code_sha256 = canonical_hash(verified_source_hashes)
            _require(code_sha256 == campaign.get("code_sha256"), "aggregate source code SHA-256 mismatch", errors)

            episode_ids: set[str] = set()
            record_ids: set[str] = set()
            for row_index, receipt in enumerate(episode_rows):
                episode_id = receipt.get("episode_id")
                if not isinstance(episode_id, str) or not episode_id:
                    errors.append(f"episode index row {row_index} has invalid episode_id")
                    continue
                _require(episode_id not in episode_ids, f"duplicate episode_id: {episode_id}", errors)
                episode_ids.add(episode_id)
                prefix = f"episodes/{episode_id}/"
                required_episode = {"config.json", "events.jsonl", "legends.json", "sft.jsonl", "receipt.json"}
                for filename in required_episode:
                    _require(prefix + filename in members, f"{episode_id}: missing {filename}", errors)
                if any(prefix + filename not in members for filename in required_episode):
                    continue

                stored_receipt = _member_json(archive, members, prefix + "receipt.json")
                _require(stored_receipt == receipt, f"{episode_id}: index row differs from receipt.json", errors)
                _require(receipt.get("schema") == REPLAY_SCHEMA, f"{episode_id}: invalid replay schema", errors)
                _require(receipt.get("status") == "ok", f"{episode_id}: receipt status is not ok", errors)
                _require(
                    receipt.get("manifest_sha256") == manifest_sha256,
                    f"{episode_id}: frozen manifest SHA-256 mismatch",
                    errors,
                )
                replay_without_id = {
                    key: receipt.get(key)
                    for key in (
                        "schema",
                        "episode_id",
                        "seed",
                        "config_sha256",
                        "code_sha256",
                        "event_sha256",
                        "final_state_sha256",
                    )
                }
                _require(
                    receipt.get("receipt_id") == canonical_hash(replay_without_id),
                    f"{episode_id}: replay receipt_id mismatch",
                    errors,
                )
                _require(receipt.get("code_sha256") == code_sha256, f"{episode_id}: code SHA-256 mismatch", errors)

                config = _member_json(archive, members, prefix + "config.json")
                _require(canonical_hash(config) == receipt.get("config_sha256"), f"{episode_id}: config SHA-256 mismatch", errors)
                artifact_hashes = receipt.get("artifact_hashes")
                if not isinstance(artifact_hashes, Mapping):
                    errors.append(f"{episode_id}: artifact_hashes must be a mapping")
                    artifact_hashes = {}
                for filename in ("config.json", "events.jsonl", "legends.json", "sft.jsonl"):
                    actual = _member_sha256(archive, members, prefix + filename)
                    _require(actual == artifact_hashes.get(filename), f"{episode_id}: artifact SHA-256 mismatch for {filename}", errors)
                    if filename == "events.jsonl":
                        _require(actual == receipt.get("event_sha256"), f"{episode_id}: event SHA-256 mismatch", errors)

                sft_rows = _member_jsonl(archive, members, prefix + "sft.jsonl")
                _require(len(sft_rows) == receipt.get("sft_record_count"), f"{episode_id}: SFT record count mismatch", errors)
                for record_index, record in enumerate(sft_rows):
                    errors.extend(
                        f"{episode_id} SFT row {record_index}: {error}"
                        for error in _validate_sft_record(record, receipt, record_ids)
                    )
                records.extend(sft_rows)

            if errors:
                raise CorpusVerificationError("chronicle corpus verification failed: " + "; ".join(errors[:20]))
            return VerifiedCorpus(
                archive_sha256=archive_digest,
                manifest_sha256=manifest_sha256,
                verification_receipt_sha256=verification_sha256,
                code_sha256=code_sha256,
                episode_receipts=tuple(copy.deepcopy(episode_rows)),
                records=tuple(copy.deepcopy(records)),
            )
    except zipfile.BadZipFile as exc:
        raise CorpusVerificationError(f"invalid chronicle corpus zip: {exc}") from exc


def split_episode_ids(
    episode_ids: Iterable[str], *, train_fraction: float, val_fraction: float, holdout_fraction: float
) -> dict[str, tuple[str, ...]]:
    fractions = (train_fraction, val_fraction, holdout_fraction)
    if any(value < 0 for value in fractions) or abs(sum(fractions) - 1.0) > 1e-9:
        raise ValueError("train/val/holdout fractions must be non-negative and sum to 1")
    unique = sorted(set(episode_ids))
    ranked = sorted(
        unique,
        key=lambda episode_id: (
            hashlib.sha256(f"{SPLIT_SALT}:{episode_id}".encode("utf-8")).hexdigest(),
            episode_id,
        ),
    )
    count = len(ranked)
    if count == 0:
        return {"train": (), "val": (), "holdout": ()}
    if count == 1:
        counts = [1, 0, 0]
    elif count == 2:
        counts = [1, 0, 1]
    else:
        counts = [1, 1, 1]
        for _ in range(count - 3):
            deficits = [fractions[index] * count - counts[index] for index in range(3)]
            winner = max(range(3), key=lambda index: (deficits[index], fractions[index], -index))
            counts[winner] += 1
    train_end = counts[0]
    val_end = train_end + counts[1]
    return {
        "train": tuple(sorted(ranked[:train_end])),
        "val": tuple(sorted(ranked[train_end:val_end])),
        "holdout": tuple(sorted(ranked[val_end:])),
    }


def narration_prompt(record: Mapping[str, Any], mode: str = "fae") -> str:
    toggle = "[[FAE_TOGGLE]]\n" if mode == "fae" else ""
    evidence = {
        "window": record["window"],
        "biography_or_chronicle": record["biography_or_chronicle"],
        "fact_list": record["fact_list"],
    }
    return "\n".join(
        [
            f"{toggle}Pixie chronicle narration task.",
            "Narrate the visible event window in the requested voice.",
            "Every factual assertion must be supported by fact_list.",
            "Do not invent or change entities, counts, ticks, ordering, or causes.",
            "Return only the narration.",
            canonical_json(evidence),
        ]
    )


def _env_row(record: Mapping[str, Any], split: str) -> dict[str, Any]:
    narration = record.get("narration")
    row = {
        "env_id": ENV_ID,
        "trajectory_id": record["record_id"],
        "record_id": record["record_id"],
        "step": 0,
        "state_prompt": narration_prompt(record),
        "action": narration,
        "narration": narration,
        "mode": "fae",
        "condition": "chronicle_narration",
        "trigger_word": "[[FAE_TOGGLE]]",
        "target_field": "narration",
        "split": split,
        "source": "alife_chronicle_corpus",
        "source_schema": record["schema"],
        "episode_id": record["episode_id"],
        "seed": record["seed"],
        "replay_receipt": copy.deepcopy(record["replay_receipt"]),
        "window": copy.deepcopy(record["window"]),
        "biography_or_chronicle": copy.deepcopy(record["biography_or_chronicle"]),
        "fact_list": copy.deepcopy(record["fact_list"]),
    }
    if row["fact_list"] != record["fact_list"]:
        raise AssertionError("fact_list changed while creating an env row")
    return row


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with path.open("wb") as handle:
        for row in rows:
            encoded = (canonical_json(row) + "\n").encode("utf-8")
            handle.write(encoded)
            digest.update(encoded)
    return digest.hexdigest()


def build_chronicle_sft_env(
    archive_path: str | Path,
    output_dir: str | Path,
    *,
    train_fraction: float = 0.8,
    val_fraction: float = 0.1,
    holdout_fraction: float = 0.1,
) -> dict[str, Any]:
    """Verify first, then atomically define episode-grouped JSONL split files."""

    verified = verify_chronicle_corpus(archive_path)
    assignments = split_episode_ids(
        (str(record["episode_id"]) for record in verified.records),
        train_fraction=train_fraction,
        val_fraction=val_fraction,
        holdout_fraction=holdout_fraction,
    )
    episode_to_split = {
        episode_id: split
        for split, episode_ids in assignments.items()
        for episode_id in episode_ids
    }
    rows_by_split: dict[str, list[dict[str, Any]]] = {split: [] for split in assignments}
    for record in verified.records:
        split = episode_to_split[str(record["episode_id"])]
        rows_by_split[split].append(_env_row(record, split))
    destination = Path(output_dir).expanduser()
    split_manifest: dict[str, Any] = {}
    for split in ("train", "val", "holdout"):
        rows = rows_by_split[split]
        output = destination / f"{split}.jsonl"
        digest = _write_jsonl(output, rows)
        split_manifest[split] = {
            "file": output.name,
            "sha256": digest,
            "episode_count": len(assignments[split]),
            "record_count": len(rows),
            "episode_ids": list(assignments[split]),
        }
    manifest = {
        "schema": OUTPUT_MANIFEST_SCHEMA,
        "env_id": ENV_ID,
        "source": {
            "archive_name": Path(archive_path).name,
            "archive_sha256": verified.archive_sha256,
            "alife_manifest_sha256": verified.manifest_sha256,
            "verification_receipt_sha256": verified.verification_receipt_sha256,
            "code_sha256": verified.code_sha256,
        },
        "integrity": {
            "producer_verification_passed": True,
            "stored_sha256_receipts_verified": True,
            "split_unit": "episode_id",
            "episode_leakage": False,
            "fact_list_preserved_verbatim": True,
        },
        "target_field": "narration",
        "split_policy": {
            "version": SPLIT_SALT,
            "train_fraction": train_fraction,
            "val_fraction": val_fraction,
            "holdout_fraction": holdout_fraction,
        },
        "episode_count": len(verified.episode_receipts),
        "record_count": len(verified.records),
        "splits": split_manifest,
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=config_path("chronicle_corpus"))
    parser.add_argument("--output-dir", type=Path, default=config_path("chronicle_sft_output_dir"))
    parser.add_argument("--train-fraction", type=float, default=0.8)
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--holdout-fraction", type=float, default=0.1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_chronicle_sft_env(
        args.archive,
        args.output_dir,
        train_fraction=args.train_fraction,
        val_fraction=args.val_fraction,
        holdout_fraction=args.holdout_fraction,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
