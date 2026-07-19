from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object integration test")
def test_capped_wrapper_audits_owned_pids_before_propagating_failure(tmp_path: Path) -> None:
    arguments = base64.b64encode(
        json.dumps(["-c", "import sys; sys.exit(7)"], separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    run_id = "pytest-owned-cleanup"
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(APP_ROOT / "persona_training" / "run_capped_strict.ps1"),
            "-Executable",
            sys.executable,
            "-ArgumentsBase64",
            arguments,
            "-RunId",
            run_id,
            "-OutputDirectory",
            str(tmp_path),
            "-MemoryGB",
            "2",
            "-CpuPercent",
            "50",
            "-IoMBPerSecond",
            "50",
            "-TimeoutMinutes",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 7
    summary = json.loads((tmp_path / f"{run_id}.resource_summary.json").read_text(encoding="utf-8-sig"))
    cleanup = json.loads((tmp_path / f"{run_id}.cleanup.json").read_text(encoding="utf-8-sig"))
    assert summary["exit_code"] == 7
    assert summary["cap_verified"] is True
    assert Path(summary["cleanup"]) == tmp_path / f"{run_id}.cleanup.json"
    assert cleanup["cleanup_passed"] is True
    assert cleanup["lingering_owned_pids"] == []
