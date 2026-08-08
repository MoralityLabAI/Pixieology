"""Fail-closed continuation entrypoint for the Captain Rowan registered corpus."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
FEEDBACK = REPO / "experiments" / "pixie_lora_feedback_loop_v0_2"
MOTIFS = REPO / "experiments" / "pixie_etale_motif_search_v0_1"
sys.path.insert(0, str(FEEDBACK))
sys.path.insert(0, str(MOTIFS))

from pixie_lora_feedback import runner as feedback_runner  # noqa: E402
from pixie_lora_feedback.jobs import validate_job as validate_feedback_job  # noqa: E402
from pixie_lora_feedback.protocol import verify as verify_feedback  # noqa: E402
from pixie_lora_feedback.reporting import finalize_execution  # noqa: E402


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def object_sha(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_registered(path_value: str) -> Path:
    path = (REPO / path_value).resolve()
    try:
        path.relative_to(REPO.resolve())
    except ValueError as error:
        raise ValueError("registered path escapes repository") from error
    return path


def load_outer(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "captain_rowan_tinylora_job.v1":
        raise ValueError("invalid Captain Rowan job schema")
    copy = dict(value)
    expected = copy.pop("job_sha256", None)
    if expected != object_sha(copy):
        raise ValueError("Captain Rowan job hash mismatch")
    if value.get("status") != "STAGED_NOT_AUTHORIZED" or value.get("automatic_authorization") is not False:
        raise ValueError("Captain Rowan job is not a fail-closed staged proposal")
    return value


def load_rows(job: dict) -> list[dict]:
    path = resolve_registered(job["dataset"]["path"])
    if file_sha(path) != job["dataset"]["sha256"]:
        raise ValueError("registered Captain Rowan corpus hash mismatch")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    identifiers = [str(row.get("id", "")) for row in rows]
    if len(identifiers) != len(set(identifiers)) or not all(identifiers):
        raise ValueError("registered corpus IDs are missing or duplicated")
    if sum(row.get("split") == "discovery" for row in rows) != 10:
        raise ValueError("registered corpus must contain exactly ten discovery rows")
    if sum(row.get("split") == "transfer" for row in rows) != 10:
        raise ValueError("registered corpus must contain exactly ten transfer rows")
    if not all(row.get("outcome_eligible") is True and row.get("expected_completion") for row in rows):
        raise ValueError("registered corpus contains an ineligible row")
    return rows


def verify_bound_files(job: dict) -> dict:
    checks = {}
    for label, path_key, hash_key in (
        ("prompt_adapter", "prompt_adapter", "prompt_adapter_sha256"),
        ("metta_facts", "metta_facts", "metta_facts_sha256"),
    ):
        path = resolve_registered(job["source_artifacts"][path_key])
        checks[label] = path.is_file() and file_sha(path) == job["source_artifacts"][hash_key]
    runner_path = Path(__file__).resolve()
    wrapper_path = ROOT / "scripts" / "run_capped.ps1"
    checks["continuation_runner"] = file_sha(runner_path) == job["execution"]["continuation_runner_sha256"]
    checks["continuation_wrapper"] = file_sha(wrapper_path) == job["execution"]["continuation_wrapper_sha256"]
    feedback_job = ROOT / "feedback_job.json"
    checks["feedback_job"] = feedback_job.is_file() and file_sha(feedback_job) == job["execution"]["feedback_job_file_sha256"]
    load_rows(job)
    checks["registered_corpus"] = True
    return checks


def validate_authorization(path: Path, job: dict, require_wrapper: bool) -> SimpleNamespace:
    value = json.loads(path.read_text(encoding="utf-8"))
    template = json.loads((ROOT / "authorization.template.json").read_text(encoding="utf-8"))
    if value.get("schema") != template["schema"] or value.get("authorized") is not True:
        raise ValueError("Captain Rowan authorization is not active")
    if value.get("statement") != template["required_statement"]:
        raise ValueError("Captain Rowan authorization statement differs from the bound template")
    if value.get("job_id") != job["job_id"] or value.get("job_sha256") != job["job_sha256"]:
        raise ValueError("Captain Rowan authorization belongs to another job")
    if value.get("caps") != job["resources"] or value.get("gpu_guard") != job["gpu_guard"]:
        raise ValueError("Captain Rowan authorization resource guards differ from the job")
    acknowledgements = value.get("acknowledgements", {})
    required = {
        "model_load", "rank2_gate_training", "frozen_splits", "checkpointing",
        "abort_is_valid_outcome", "pid_scoped_cleanup", "no_automatic_authorization",
    }
    if not all(acknowledgements.get(key) is True for key in required):
        raise ValueError("Captain Rowan authorization acknowledgements are incomplete")
    expires = datetime.fromisoformat(str(value.get("expires_utc", "")).replace("Z", "+00:00"))
    if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
        raise ValueError("Captain Rowan authorization is expired")
    run_id = str(value.get("run_id", "")).strip()
    attempt_id = str(value.get("attempt_id", "")).strip()
    if not run_id or not attempt_id or "replace-me" in {run_id, attempt_id}:
        raise ValueError("Captain Rowan authorization requires concrete run and attempt IDs")
    if require_wrapper:
        expected = {
            "PIXIE_RESOURCE_CAP_ACTIVE": "1",
            "PIXIE_RUN_ID": run_id,
            "PIXIE_CAP_RAM_MB": str(job["resources"]["ram_mb"]),
            "PIXIE_CAP_CPU_PCT": str(job["resources"]["cpu_pct"]),
            "PIXIE_CAP_IO_MB_S": str(job["resources"]["io_mb_s"]),
            "PIXIE_CAP_TIMEOUT_SECONDS": str(job["resources"]["timeout_seconds"]),
        }
        for name, expected_value in expected.items():
            if os.environ.get(name) != expected_value:
                raise ValueError(f"wrapper environment {name} differs from authorization")
    return SimpleNamespace(run_id=run_id, attempt_id=attempt_id, receipt=value)


def patch_feedback_runner(job: dict, authorization_path: Path) -> None:
    rows = load_rows(job)
    feedback_runner.build_corpus = lambda root_seed: rows

    def bound_authorization(path, experiment_root, protocol, feedback_job, *, require_active_wrapper):
        return validate_authorization(authorization_path, job, require_active_wrapper)

    feedback_runner.validate_authorization = bound_authorization


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    sub = value.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--job", type=Path, default=ROOT / "job.json")
    verify.add_argument("--require-model", action="store_true")
    auth = sub.add_parser("authorization-check")
    auth.add_argument("--job", type=Path, required=True)
    auth.add_argument("--authorization", type=Path, required=True)
    train = sub.add_parser("train")
    train.add_argument("--job", type=Path, required=True)
    train.add_argument("--authorization", type=Path, required=True)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--job", type=Path, required=True)
    evaluate.add_argument("--authorization", type=Path, required=True)
    evaluate.add_argument("--adapter", type=Path, required=True)
    finalize = sub.add_parser("finalize")
    finalize.add_argument("--job", type=Path, required=True)
    finalize.add_argument("--resource-summary", type=Path, required=True)
    finalize.add_argument("--cleanup-summary", type=Path, required=True)
    finalize.add_argument("--output", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    job = load_outer(args.job)
    checks = verify_bound_files(job)
    if args.command == "verify":
        frozen = verify_feedback(REPO, FEEDBACK, require_model_weights=args.require_model)
        result = {"status": "PASS" if all(checks.values()) and frozen["ok"] else "FAIL", "checks": checks, "frozen_feedback": frozen}
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "PASS" else 2
    if args.command == "authorization-check":
        value = validate_authorization(args.authorization, job, False)
        print(json.dumps({"status": "PASS", "run_id": value.run_id, "attempt_id": value.attempt_id}, indent=2))
        return 0
    feedback_job_path = ROOT / "feedback_job.json"
    feedback_job = validate_feedback_job(json.loads(feedback_job_path.read_text(encoding="utf-8")))
    if feedback_job["dataset"]["registered_corpus_sha256"] != job["dataset"]["sha256"]:
        raise ValueError("feedback job is bound to another registered corpus")
    if args.command in {"train", "evaluate"}:
        validate_authorization(args.authorization, job, True)
        patch_feedback_runner(job, args.authorization)
    if args.command == "train":
        print(json.dumps(feedback_runner.train_feedback_job(REPO, FEEDBACK, feedback_job_path, args.authorization), indent=2))
        return 0
    if args.command == "evaluate":
        print(json.dumps(feedback_runner.evaluate_feedback_job(REPO, FEEDBACK, feedback_job_path, args.authorization, adapter_path=args.adapter), indent=2))
        return 0
    if args.command == "finalize":
        result = finalize_execution(job=feedback_job, resource_summary_path=args.resource_summary, cleanup_summary_path=args.cleanup_summary, output_path=args.output)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "COMPLETE" else 2
    raise AssertionError("unreachable")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(json.dumps({"status": "REJECTED", "error": str(error)}, indent=2))
        raise SystemExit(2)
