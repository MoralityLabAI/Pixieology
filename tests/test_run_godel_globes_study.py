from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pixie_env
from run_godel_globes_study import (
    StudyRunnerError,
    build_study_url,
    ingest_receipt,
    receipt_files,
    run_analysis,
    write_json_atomic,
)


class GodelGlobesStudyRunnerTests(unittest.TestCase):
    def test_build_study_url_uses_anonymous_local_parameters(self) -> None:
        index = pixie_env.godel_globes_experiment_root() / "index.html"
        url = build_study_url(index, "P01", 2)
        self.assertTrue(url.startswith("file:///"))
        self.assertIn("participant=P01", url)
        self.assertIn("round=2", url)
        self.assertNotIn("condition=", url)

    def test_build_study_url_rejects_names_and_invalid_rounds(self) -> None:
        index = Path("index.html")
        with self.assertRaises(StudyRunnerError):
            build_study_url(index, "participant@example.com", 1)
        with self.assertRaises(StudyRunnerError):
            build_study_url(index, "P01", 3)

    def test_receipt_files_are_json_only_and_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "b.json").write_text("{}", encoding="utf-8")
            (root / "a.json").write_text("{}", encoding="utf-8")
            (root / "note.txt").write_text("ignore", encoding="utf-8")
            self.assertEqual([path.name for path in receipt_files(root)], ["a.json", "b.json"])

    def test_no_data_analysis_round_trips_through_atomic_output(self) -> None:
        analyzer = pixie_env.godel_globes_experiment_root() / "analyze_study.mjs"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = run_analysis(root / "missing-receipts", analyzer)
            self.assertEqual(payload["status"], "NOT_RUN")
            result = root / "nested" / "result.json"
            write_json_atomic(result, payload)
            self.assertEqual(json.loads(result.read_text(encoding="utf-8")), payload)

    def test_ingest_is_idempotent_but_refuses_conflicting_receipts(self) -> None:
        payload = {
            "study_id": "godel_globes_5d_character_ab_v1",
            "participant_id": "P01",
            "round": 1,
            "condition": "flat",
            "task_results": [{"status": "SKIP"} for _ in range(5)],
            "debrief": {
                "reflection_location": "head",
                "map_meaning": "approximate_similarity",
                "preference": "not_asked",
                "comments": "",
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "download.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            receipt_dir = root / "receipts"
            destination = ingest_receipt(source, receipt_dir)
            self.assertEqual(destination.name, "P01-round-1-flat.json")
            self.assertEqual(ingest_receipt(source, receipt_dir), destination)
            payload["task_results"] = [{"status": "PASS"} for _ in range(5)]
            source.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(StudyRunnerError, "refusing to overwrite"):
                ingest_receipt(source, receipt_dir)

    def test_ingest_rejects_incomplete_exports(self) -> None:
        payload = {
            "study_id": "godel_globes_5d_character_ab_v1",
            "participant_id": "P02",
            "round": 1,
            "condition": "embodied",
            "task_results": [],
            "debrief": None,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "incomplete.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(StudyRunnerError, "incomplete"):
                ingest_receipt(source, Path(tmpdir) / "receipts")


if __name__ == "__main__":
    unittest.main()
