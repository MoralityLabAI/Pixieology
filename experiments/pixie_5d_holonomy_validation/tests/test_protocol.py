from __future__ import annotations

from pathlib import Path

from pixie_holonomy5d.protocol import verify_frozen_inputs


def test_registered_local_inputs_and_launchers_match_hashes() -> None:
    experiment_root = Path(__file__).resolve().parents[1]
    repo_root = experiment_root.parents[1]
    result = verify_frozen_inputs(repo_root, experiment_root)
    assert result["ok"], result["checks"]
    assert all(result["checks"].values())
