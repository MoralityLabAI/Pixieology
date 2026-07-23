"""Command line for staged Pixie TinyLoRA/QLoRA feedback jobs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pixie_etale_motifs.corpus import build_corpus
from pixie_etale_motifs.io import atomic_json, sha256_file
from pixie_etale_motifs.protocol import load_repo_config, resolve_config_path

from .authorization import authorization_template, validate_authorization
from .jobs import build_job_queue, publish_queue_js, validate_job, validate_queue
from .protocol import load_protocol, verify
from .reporting import compile_feedback_report, finalize_execution
from .runner import evaluate_feedback_job, train_feedback_job


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify")
    commands.add_parser("output-root")

    propose = commands.add_parser("propose")
    propose.add_argument("--catalog", type=Path)
    propose.add_argument("--model", type=Path)
    propose.add_argument("--output", type=Path, required=True)

    extract = commands.add_parser("extract-job")
    extract.add_argument("--queue", type=Path, required=True)
    extract.add_argument("--job-id", required=True)
    extract.add_argument("--output", type=Path, required=True)

    publish = commands.add_parser("publish-queue")
    publish.add_argument("--queue", type=Path, required=True)
    publish.add_argument("--output", type=Path, required=True)

    auth_template_parser = commands.add_parser("authorization-template")
    auth_template_parser.add_argument("--job", type=Path, required=True)
    auth_check = commands.add_parser("authorization-check")
    auth_check.add_argument("--job", type=Path, required=True)
    auth_check.add_argument("--authorization", type=Path, required=True)

    train = commands.add_parser("train")
    train.add_argument("--job", type=Path, required=True)
    train.add_argument("--authorization", type=Path, required=True)

    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--job", type=Path, required=True)
    evaluate.add_argument("--authorization", type=Path, required=True)
    evaluate.add_argument("--adapter", type=Path)

    report = commands.add_parser("report")
    report.add_argument("--evaluation", type=Path, action="append", required=True)
    report.add_argument("--topology", type=Path, action="append", default=[])
    report.add_argument("--output", type=Path, required=True)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--job", type=Path, required=True)
    finalize.add_argument("--resource-summary", type=Path, required=True)
    finalize.add_argument("--cleanup-summary", type=Path, required=True)
    finalize.add_argument("--output", type=Path, required=True)

    arguments = parser.parse_args(argv)
    experiment_root = Path(__file__).resolve().parents[1]
    repo_root = arguments.repo_root.resolve() if arguments.repo_root else experiment_root.parents[1]
    protocol = load_protocol(experiment_root)
    if arguments.command == "verify":
        result = verify(repo_root, experiment_root)
        _print(result)
        return 0 if result["ok"] else 1
    if arguments.command == "output-root":
        config = load_repo_config(repo_root)
        print(resolve_config_path(repo_root, config, "pixie_lora_feedback_output_root"))
        return 0
    if arguments.command == "propose":
        if (arguments.catalog is None) != (arguments.model is None):
            raise ValueError("--catalog and --model must be supplied together")
        catalog = None if arguments.catalog is None else json.loads(arguments.catalog.read_text(encoding="utf-8"))
        model = None if arguments.model is None else json.loads(arguments.model.read_text(encoding="utf-8"))
        queue = build_job_queue(
            protocol=protocol,
            protocol_sha256=sha256_file(experiment_root / "protocol.json"),
            implementation_lock_sha256=sha256_file(experiment_root / "protocol.lock.json"),
            corpus_rows=build_corpus(root_seed=2026072301),
            catalog=catalog,
            model=model,
        )
        atomic_json(arguments.output, queue)
        _print({
            "status": queue["status"],
            "job_count": queue["job_count"],
            "training_slot_status": queue["training_slot_status"],
            "artifact": str(arguments.output),
            "artifact_sha256": sha256_file(arguments.output),
        })
        return 0
    if arguments.command == "extract-job":
        queue = validate_queue(json.loads(arguments.queue.read_text(encoding="utf-8")))
        job = next((item for item in queue["jobs"] if item["job_id"] == arguments.job_id), None)
        if job is None:
            raise ValueError(f"queue has no job {arguments.job_id}")
        atomic_json(arguments.output, job)
        _print({"status": job["status"], "job_id": job["job_id"], "artifact": str(arguments.output)})
        return 0 if job["status"] == "PROPOSED" else 2
    if arguments.command == "publish-queue":
        queue = json.loads(arguments.queue.read_text(encoding="utf-8"))
        publish_queue_js(queue, arguments.output)
        _print({"status": "PUBLISHED", "artifact": str(arguments.output), "artifact_sha256": sha256_file(arguments.output)})
        return 0
    if arguments.command == "authorization-template":
        job = validate_job(json.loads(arguments.job.read_text(encoding="utf-8")))
        _print(authorization_template(experiment_root, protocol, job))
        return 0
    if arguments.command == "authorization-check":
        job = validate_job(json.loads(arguments.job.read_text(encoding="utf-8")))
        value = validate_authorization(
            arguments.authorization,
            experiment_root,
            protocol,
            job,
            require_active_wrapper=False,
        )
        _print({"status": "PASS", "run_id": value.run_id, "attempt_id": value.attempt_id, "job_id": job["job_id"]})
        return 0
    if arguments.command == "train":
        _print(train_feedback_job(repo_root, experiment_root, arguments.job, arguments.authorization))
        return 0
    if arguments.command == "evaluate":
        _print(
            evaluate_feedback_job(
                repo_root,
                experiment_root,
                arguments.job,
                arguments.authorization,
                adapter_path=arguments.adapter,
            )
        )
        return 0
    if arguments.command == "report":
        result = compile_feedback_report(
            [json.loads(path.read_text(encoding="utf-8")) for path in arguments.evaluation],
            topology_receipts=[json.loads(path.read_text(encoding="utf-8")) for path in arguments.topology],
        )
        atomic_json(arguments.output, result)
        _print(result)
        return 0 if result["status"] in {"FEEDBACK_CANDIDATE", "AWAITING_CANDIDATE_TOPOLOGY", "BASELINES_COMPLETE_AWAITING_CANDIDATES"} else 2
    if arguments.command == "finalize":
        job = validate_job(json.loads(arguments.job.read_text(encoding="utf-8")))
        result = finalize_execution(
            job=job,
            resource_summary_path=arguments.resource_summary,
            cleanup_summary_path=arguments.cleanup_summary,
            output_path=arguments.output,
        )
        _print(result)
        return 0 if result["status"] == "COMPLETE" else 2
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
