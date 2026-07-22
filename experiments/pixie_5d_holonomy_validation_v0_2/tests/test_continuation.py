from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pixie_holonomy5d_v02.continuation import _chunk_complete, _final_complete


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_chunk_and_final_markers_have_distinct_schemas(tmp_path: Path) -> None:
    artifacts = [tmp_path / name / "context_03.npz" for name in ("zero", "trained", "random_00")]
    for index, artifact in enumerate(artifacts):
        artifact.parent.mkdir()
        artifact.write_bytes(f"artifact-{index}".encode())
    hashes = {path.relative_to(tmp_path).as_posix(): _hash(path) for path in artifacts}
    marker = tmp_path / "context_03.complete.json"
    marker.write_text(
        json.dumps(
            {
                "schema": "pixie_5d_context3_complete_v2",
                "protocol_sha256": "protocol",
                "rows": 64,
                "artifacts": hashes,
            }
        ),
        encoding="utf-8",
    )
    assert _final_complete(marker, artifacts, tmp_path, "protocol")
    assert not _chunk_complete(marker, artifacts, tmp_path, "protocol")


def test_marker_rejects_changed_artifact(tmp_path: Path) -> None:
    artifacts = [tmp_path / f"artifact-{index}.npz" for index in range(3)]
    for artifact in artifacts:
        artifact.write_bytes(b"before")
    marker = tmp_path / "marker.json"
    marker.write_text(
        json.dumps(
            {
                "schema": "pixie_5d_context3_chunk_v2",
                "protocol_sha256": "protocol",
                "artifacts": {path.name: _hash(path) for path in artifacts},
            }
        ),
        encoding="utf-8",
    )
    assert _chunk_complete(marker, artifacts, tmp_path, "protocol")
    artifacts[0].write_bytes(b"after")
    assert not _chunk_complete(marker, artifacts, tmp_path, "protocol")
