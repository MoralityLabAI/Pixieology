from collections import Counter
from pathlib import Path

from pixie_etale_motifs.corpus import build_corpus
from pixie_etale_motifs.io import object_sha256
from pixie_etale_motifs.protocol import load_protocol, protocol_lock_checks, verify_protocol_shape


ROOT = Path(__file__).resolve().parents[1]


def test_controlled_corpus_has_grouped_splits_and_frozen_hash():
    protocol = load_protocol(ROOT)
    rows = build_corpus(
        root_seed=protocol["seeds"]["corpus"],
        family_names=protocol["corpus"]["families"],
    )
    assert len(rows) == 192
    assert Counter(row["split"] for row in rows) == {
        "discovery": 96,
        "confirmation": 48,
        "transfer": 48,
    }
    by_group = {}
    for row in rows:
        by_group.setdefault(row["semantic_group_id"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in by_group.values())
    assert object_sha256(rows) == protocol["corpus"]["generated_sha256"]


def test_protocol_freezes_resource_and_geometry_contracts():
    protocol = load_protocol(ROOT)
    assert verify_protocol_shape(protocol) == []
    assert protocol["coordinates"]["window_dependent"] is False
    assert protocol["controls"]["random_adapter_count"] == 19
    assert protocol["status"] == "STAGED_NOT_AUTHORIZED"
    assert all(protocol_lock_checks(ROOT).values())
