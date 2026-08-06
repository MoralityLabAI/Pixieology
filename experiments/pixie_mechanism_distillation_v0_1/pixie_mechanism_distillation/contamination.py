"""Exact-prompt leakage scan over explicitly declared local corpora."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .io_utils import file_sha256, object_sha256


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def scan_exact_prompts(
    cases: list[dict[str, Any]],
    sources: list[Path],
    *,
    display_root: Path | None = None,
) -> dict[str, Any]:
    if not sources:
        raise ValueError("at least one declared source is required")
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"declared contamination sources are missing: {missing}")
    source_text = {str(path): normalize(path.read_text(encoding="utf-8-sig", errors="replace")) for path in sources}
    overlaps = []
    for case in cases:
        prompt = normalize(case["prompt"])
        for path, text in source_text.items():
            if prompt and prompt in text:
                overlaps.append({"case_id": case["case_id"], "source": path})
    def display(path: Path) -> str:
        if display_root is not None:
            try:
                return path.resolve().relative_to(display_root.resolve()).as_posix()
            except ValueError:
                pass
        return str(path)

    report = {
        "schema": "pixieology_mechanism_contamination_report_v1",
        "status": "COMPLETED_NO_EXACT_OVERLAP" if not overlaps else "EXACT_OVERLAP_FOUND",
        "method": "normalized_exact_prompt_substring_v1",
        "scope": "Declared checked-in Pixie corpora only; broad pretraining familiarity is not excluded.",
        "case_count": len(cases),
        "task_set_sha256": object_sha256(cases),
        "sources": [{"path": display(path), "sha256": file_sha256(path)} for path in sources],
        "overlaps": overlaps,
    }
    return report
