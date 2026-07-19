from pathlib import Path

import pytest

from pixie_bonsai.data import DataError, load_jsonl


ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_dataset_shape_and_holdout() -> None:
    train = load_jsonl(ROOT / "data" / "smoke_train.jsonl")
    evaluation = load_jsonl(ROOT / "data" / "smoke_eval.jsonl")
    assert len(train) == 48
    assert len(evaluation) == 16
    assert sum(record.kind == "canary" for record in train) == 24
    assert sum(record.kind == "style" for record in train) == 24
    assert sum(record.kind == "canary" for record in evaluation) == 8
    assert sum(record.kind == "style" for record in evaluation) == 8
    assert {record.record_id for record in train}.isdisjoint(record.record_id for record in evaluation)


def test_target_leak_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(
        '{"id":"x","kind":"canary","messages":[{"role":"user","content":"SECRET"},{"role":"assistant","content":"SECRET"}]}\n',
        encoding="utf-8",
    )
    with pytest.raises(DataError, match="leaked"):
        load_jsonl(path)

