import json
from pathlib import Path

from pixie_bonsai.data import dataset_manifest
from pixie_bonsai.reporting import atomic_write_text, file_manifest, sha256_file
from pixie_bonsai.train import reconcile_metrics


def test_hash_manifest_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    atomic_write_text(first, "alpha\n")
    atomic_write_text(second, "beta\n")
    one = file_manifest([second, first], tmp_path)
    two = file_manifest([first, second], tmp_path)
    assert one == two
    assert one[0]["path"] == "a.txt"
    assert one[0]["sha256"] == sha256_file(first)


def test_dataset_manifest_records_bytes_and_hash(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    path.write_text('{"x":1}\n', encoding="utf-8")
    manifest = dataset_manifest([path])
    assert manifest["rows.jsonl"]["bytes"] == path.stat().st_size
    assert len(manifest["rows.jsonl"]["sha256"]) == 64


def test_interrupted_post_checkpoint_metrics_are_preserved_but_not_canonical(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.jsonl"
    metrics.write_text("".join(json.dumps({"global_step": step}) + "\n" for step in range(1, 9)), encoding="utf-8")
    checkpoint = tmp_path / "checkpoints" / "checkpoint-000005"
    checkpoint.mkdir(parents=True)
    assert reconcile_metrics(tmp_path, 5, checkpoint) == 3
    canonical = [json.loads(line)["global_step"] for line in metrics.read_text(encoding="utf-8").splitlines()]
    abandoned = [json.loads(line)["global_step"] for line in (tmp_path / "metrics_abandoned.jsonl").read_text(encoding="utf-8").splitlines()]
    assert canonical == [1, 2, 3, 4, 5]
    assert abandoned == [6, 7, 8]
