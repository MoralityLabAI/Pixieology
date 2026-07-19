from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from build_pixie_chronicle_sft_env import (
    CAMPAIGN_SCHEMA,
    EVENT_SCHEMA,
    REPLAY_SCHEMA,
    SOURCE_SFT_SCHEMA,
    VERIFICATION_SCHEMA,
    CorpusVerificationError,
    build_chronicle_sft_env,
    canonical_hash,
    canonical_json,
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _pretty(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _jsonl(rows: list[dict]) -> bytes:
    return "".join(canonical_json(row) + "\n" for row in rows).encode("utf-8")


def _events(episode_id: str) -> list[dict]:
    specs = [
        (1, 2, "birth", [{"id": "ember-1", "role": "subject"}]),
        (2, 3, "bloom", []),
        (3, 3, "bloom", []),
        (4, 4, "bloom", []),
        (5, 5, "gate_crossing", [{"id": "ember-1", "role": "subject"}]),
    ]
    return [
        {
            "schema": EVENT_SCHEMA,
            "episode_id": episode_id,
            "world_id": f"world-{episode_id}",
            "sequence": sequence,
            "tick": tick,
            "event_type": event_type,
            "plane": "GROVE",
            "region": "north",
            "position": [sequence, 0],
            "entities": entities,
            "cause_chain": [{"type": "fixture", "entity_ids": []}],
            "details": {},
        }
        for sequence, tick, event_type, entities in specs
    ]


def _facts() -> list[dict]:
    return [
        {
            "fact_id": "ember-birth",
            "predicate": "born_at_tick",
            "subject": "ember-1",
            "value": 2,
            "evidence_event_sequences": [1],
        },
        {
            "fact_id": "grove-blooms",
            "predicate": "window_event_count",
            "subject": "GROVE/north",
            "value": {"event_type": "bloom", "count": 3},
            "evidence_event_sequences": [2, 3, 4],
        },
        {
            "fact_id": "ember-gate",
            "predicate": "participated_in_event",
            "subject": "ember-1",
            "value": "gate_crossing",
            "evidence_event_sequences": [5],
        },
    ]


def _write_fixture_corpus(
    path: Path,
    *,
    episodes: int = 4,
    verification_status: str = "passed",
    manifest_hash_valid: bool = True,
) -> None:
    source_bytes = b"fixture chronicle source\n"
    source_hashes = {"src/chronicle/fixture.py": _sha(source_bytes)}
    code_sha = canonical_hash(source_hashes)
    frozen_manifest = _pretty({"schema": "alife.knowledge_experiment.v1", "fixture": True})
    manifest_sha = _sha(frozen_manifest)
    members: dict[str, bytes] = {
        "frozen_manifest.json": frozen_manifest,
        "source/src/chronicle/fixture.py": source_bytes,
    }
    receipts: list[dict] = []
    for index in range(episodes):
        episode_id = f"fixture-{index:03d}"
        seed = 700 + index
        prefix = f"episodes/{episode_id}/"
        config = {"schema": "alife.chronicle.episode_config.v1", "episode_id": episode_id, "seed": seed}
        config_bytes = _pretty(config)
        event_rows = _events(episode_id)
        event_bytes = _jsonl(event_rows)
        legends_bytes = _pretty({"schema": "alife.chronicle.legends.v1", "episode_id": episode_id})
        replay = {
            "schema": REPLAY_SCHEMA,
            "episode_id": episode_id,
            "seed": seed,
            "config_sha256": canonical_hash(config),
            "code_sha256": code_sha,
            "event_sha256": _sha(event_bytes),
            "final_state_sha256": _sha(f"state:{episode_id}".encode()),
        }
        replay["receipt_id"] = canonical_hash(replay)
        sft = {
            "schema": SOURCE_SFT_SCHEMA,
            "record_id": f"{episode_id}:chronicle:0",
            "episode_id": episode_id,
            "seed": seed,
            "replay_receipt": dict(replay),
            "window": event_rows,
            "biography_or_chronicle": {
                "type": "chronicle",
                "value": {"plane": "GROVE", "region": "north", "window_index": 0},
            },
            "fact_list": _facts(),
            "narration": None,
        }
        sft_bytes = _jsonl([sft])
        receipt = {
            **replay,
            "status": "ok",
            "manifest_sha256": manifest_sha,
            "event_count": 5,
            "sft_record_count": 1,
            "artifact_hashes": {
                "config.json": _sha(config_bytes),
                "events.jsonl": _sha(event_bytes),
                "legends.json": _sha(legends_bytes),
                "sft.jsonl": _sha(sft_bytes),
            },
        }
        receipts.append(receipt)
        members[prefix + "config.json"] = config_bytes
        members[prefix + "events.jsonl"] = event_bytes
        members[prefix + "legends.json"] = legends_bytes
        members[prefix + "sft.jsonl"] = sft_bytes
        members[prefix + "receipt.json"] = _pretty(receipt)

    campaign = {
        "schema": CAMPAIGN_SCHEMA,
        "status": "ok",
        "episode_count": episodes,
        "manifest_sha256": manifest_sha if manifest_hash_valid else "0" * 64,
        "files": source_hashes,
        "code_sha256": code_sha,
    }
    summary = {"schema": CAMPAIGN_SCHEMA, "status": "ok", "episode_count": episodes}
    verification = {
        "schema": VERIFICATION_SCHEMA,
        "status": verification_status,
        "episode_count": episodes,
        "validated_sft_files": episodes,
        "sampled_episodes": episodes,
        "exact_event_byte_replays_passed": episodes,
        "code_hash_matches": True,
        "errors": [] if verification_status == "passed" else ["fixture failure"],
        "replay_failures": [],
    }
    members.update(
        {
            "campaign_receipt.json": _pretty(campaign),
            "summary.json": _pretty(summary),
            "verification_receipt.json": _pretty(verification),
            "seed_manifest.json": _pretty({"episode_count": episodes, "seeds": [row["seed"] for row in receipts]}),
            "episodes.jsonl": _jsonl(receipts),
        }
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in sorted(members.items()):
            archive.writestr(name, value)


def test_ingest_round_trips_verified_corpus_and_groups_by_episode(tmp_path: Path) -> None:
    corpus = tmp_path / "chronicle.zip"
    output = tmp_path / "env"
    _write_fixture_corpus(corpus)
    manifest = build_chronicle_sft_env(corpus, output)

    assert manifest["env_id"] == "pixie_chronicle_narration"
    assert manifest["episode_count"] == 4
    assert manifest["record_count"] == 4
    assert manifest["integrity"]["episode_leakage"] is False
    assert {name for name in manifest["splits"]} == {"train", "val", "holdout"}
    assert [manifest["splits"][name]["episode_count"] for name in ("train", "val", "holdout")] == [2, 1, 1]

    seen: dict[str, str] = {}
    rows: list[dict] = []
    for split in ("train", "val", "holdout"):
        split_rows = [
            json.loads(line)
            for line in (output / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        rows.extend(split_rows)
        for row in split_rows:
            assert seen.setdefault(row["episode_id"], split) == split
            assert row["split"] == split
            assert row["fact_list"] == _facts()
            assert row["replay_receipt"]["episode_id"] == row["episode_id"]
            assert row["action"] is None and row["narration"] is None
    assert len(rows) == 4


def test_ingest_refuses_failed_producer_manifest_before_writing(tmp_path: Path) -> None:
    corpus = tmp_path / "failed.zip"
    output = tmp_path / "must-not-exist"
    _write_fixture_corpus(corpus, verification_status="failed")
    with pytest.raises(CorpusVerificationError, match="verification did not pass"):
        build_chronicle_sft_env(corpus, output)
    assert not output.exists()


def test_ingest_refuses_tampered_manifest_hash(tmp_path: Path) -> None:
    corpus = tmp_path / "tampered.zip"
    output = tmp_path / "must-not-exist"
    _write_fixture_corpus(corpus, manifest_hash_valid=False)
    with pytest.raises(CorpusVerificationError, match="manifest SHA-256 mismatch"):
        build_chronicle_sft_env(corpus, output)
    assert not output.exists()
