from __future__ import annotations

import json
from pathlib import Path
import tarfile

from experiments.fae_tax_epistemics_v1 import stage_pod_source


def test_source_bundle_is_deterministic_and_excludes_runtime_data(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    first = stage_pod_source.build_archive(repo_root, tmp_path / "first.tar.gz")
    second = stage_pod_source.build_archive(repo_root, tmp_path / "second.tar.gz")
    assert stage_pod_source.sha256_file(first) == stage_pod_source.sha256_file(second)

    with tarfile.open(first, "r:gz") as archive:
        names = archive.getnames()
        assert "Pixieology/SOURCE_MANIFEST.json" in names
        assert "Pixieology/fae_tax_epistemics.py" in names
        assert "Pixieology/experiments/fae_tax_epistemics_v1/run_single_a100.sh" in names
        assert not any(name.startswith("Pixieology/data/") for name in names)
        assert not any(name.startswith("Pixieology/external/") for name in names)
        manifest_file = archive.extractfile("Pixieology/SOURCE_MANIFEST.json")
        assert manifest_file is not None
        manifest = json.load(manifest_file)
        assert manifest["schema"] == stage_pod_source.SCHEMA
        assert manifest["file_count"] == len(manifest["files"])
