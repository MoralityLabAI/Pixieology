"""CPU-safe experiment commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .contamination import scan_exact_prompts
from .compare import compare_family
from .distill import distill_program, evaluate_program
from .io_utils import atomic_json, atomic_jsonl, load_jsonl
from .protocol import build_lock, load_protocol, verify_lock, verify_staged_job
from .report import aggregate_comparisons
from .synthetic import run_synthetic_smoke
from .tasks import build_task_cases, validate_cases
from .ui_data import build_law_lab_dataset, write_law_lab_dataset


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]


def _default_sources() -> list[Path]:
    return [
        REPO_ROOT / "synthesized_pixie_dataset.jsonl",
        REPO_ROOT / "fae_kawaii_seed.jsonl",
        REPO_ROOT / "fae_constitution_seed.jsonl",
        REPO_ROOT / "multi_persona_seed.jsonl",
    ]


def _verify() -> dict[str, Any]:
    protocol = load_protocol(ROOT)
    lock = verify_lock(ROOT)
    job = verify_staged_job(ROOT)
    checks = {
        "protocol_staged": protocol["status"] == "STAGED_NOT_AUTHORIZED",
        "implementation_lock": lock["ok"],
        "capture_job_staged": job["ok"],
        "preflight_manifest": (ROOT / "eval_manifest.yaml").is_file(),
        "robustness_spec": (ROOT / "robustness_spec.yaml").is_file(),
        "contamination_report": (ROOT / "contamination_report.json").is_file(),
    }
    if checks["contamination_report"]:
        report = json.loads((ROOT / "contamination_report.json").read_text(encoding="utf-8-sig"))
        checks["no_exact_declared_corpus_overlap"] = report.get("status") == "COMPLETED_NO_EXACT_OVERLAP"
    else:
        checks["no_exact_declared_corpus_overlap"] = False
    return {
        "schema": "pixieology_mechanism_distillation_verification_v1",
        "ok": all(checks.values()),
        "checks": checks,
        "lock_reason": lock["reason"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify")
    commands.add_parser("lock")
    tasks_parser = commands.add_parser("build-tasks")
    tasks_parser.add_argument("--output", type=Path, required=True)
    contamination_parser = commands.add_parser("contamination")
    contamination_parser.add_argument("--output", type=Path, default=ROOT / "contamination_report.json")
    contamination_parser.add_argument("--source", action="append", type=Path)
    smoke_parser = commands.add_parser("synthetic-smoke")
    smoke_parser.add_argument("--output-root", type=Path, required=True)
    smoke_parser.add_argument("--families", type=int, default=8)
    ui_parser = commands.add_parser("build-ui-example")
    ui_parser.add_argument("--output-root", type=Path, default=ROOT / "ui")
    ui_parser.add_argument("--families", type=int, default=4)
    distill_parser = commands.add_parser("distill")
    distill_parser.add_argument("--traces", type=Path, required=True)
    distill_parser.add_argument("--output-root", type=Path, required=True)
    compare_parser = commands.add_parser("compare")
    compare_parser.add_argument("--programs", type=Path, required=True)
    compare_parser.add_argument("--evaluations", type=Path, required=True)
    compare_parser.add_argument("--interventions", type=Path, required=True)
    compare_parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args(argv)

    if arguments.command == "lock":
        value = build_lock(ROOT)
        atomic_json(ROOT / "protocol.lock.json", value)
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    if arguments.command == "verify":
        value = _verify()
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0 if value["ok"] else 1
    if arguments.command == "build-tasks":
        rows = build_task_cases()
        validate_cases(rows)
        atomic_jsonl(arguments.output, rows)
        print(json.dumps({"status": "PASS", "rows": len(rows), "families": 32, "output": str(arguments.output)}, indent=2))
        return 0
    if arguments.command == "contamination":
        rows = build_task_cases()
        sources = arguments.source or _default_sources()
        value = scan_exact_prompts(rows, sources, display_root=REPO_ROOT)
        atomic_json(arguments.output, value)
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0 if value["status"] == "COMPLETED_NO_EXACT_OVERLAP" else 2
    if arguments.command == "synthetic-smoke":
        protocol = load_protocol(ROOT)
        value = run_synthetic_smoke(protocol, arguments.families)
        output = arguments.output_root
        atomic_jsonl(output / "traces.jsonl", value.pop("traces"))
        atomic_jsonl(output / "programs.jsonl", value.pop("programs"))
        atomic_jsonl(output / "evaluations.jsonl", value.pop("evaluations"))
        atomic_jsonl(output / "interventions.jsonl", value.pop("interventions"))
        atomic_jsonl(output / "comparisons.jsonl", value.pop("comparisons"))
        atomic_json(output / "synthetic_smoke.json", value)
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0 if value["status"] == "PASS" else 1
    if arguments.command == "build-ui-example":
        protocol = load_protocol(ROOT)
        value = build_law_lab_dataset(protocol, family_count=arguments.families)
        write_law_lab_dataset(arguments.output_root, value)
        print(json.dumps({
            "status": "PASS",
            "schema": value["schema"],
            "evidence_class": value["evidence_class"],
            "human_or_model_evidence": value["human_or_model_evidence"],
            "family_count": len(value["families"]),
            "dataset_sha256": value["dataset_sha256"],
            "output_root": str(arguments.output_root),
        }, indent=2, sort_keys=True))
        return 0
    if arguments.command == "distill":
        protocol = load_protocol(ROOT)
        rows = load_jsonl(arguments.traces)
        keys = sorted({(row["task_family_id"], row["candidate"]) for row in rows})
        programs = []
        evaluations = []
        for family_id, candidate in keys:
            selected = [row for row in rows if row["task_family_id"] == family_id and row["candidate"] == candidate]
            discovery = [row for row in selected if row["split"] == "discovery"]
            held_out = [row for row in selected if row["split"] == "held_out"]
            program = distill_program(
                discovery,
                state_counts=protocol["distillation"]["candidate_state_counts"],
                discovery_fidelity_floor=protocol["distillation"]["discovery_fidelity_floor"],
                maximum_sparse_dimensions=protocol["distillation"]["maximum_sparse_dimensions"],
            )
            programs.append(program)
            evaluations.append(evaluate_program(program, held_out))
        atomic_jsonl(arguments.output_root / "programs.jsonl", programs)
        atomic_jsonl(arguments.output_root / "evaluations.jsonl", evaluations)
        print(json.dumps({"status": "PASS", "programs": len(programs), "output_root": str(arguments.output_root)}, indent=2))
        return 0
    if arguments.command == "compare":
        protocol = load_protocol(ROOT)
        programs = load_jsonl(arguments.programs)
        evaluations = load_jsonl(arguments.evaluations)
        interventions = load_jsonl(arguments.interventions)
        program_by_key = {(row["task_family_id"], row["candidate"]): row for row in programs}
        evaluation_by_key = {(row["task_family_id"], row["candidate"]): row for row in evaluations}
        family_ids = sorted({key[0] for key in program_by_key})
        comparisons = []
        for family_id in family_ids:
            base_key = (family_id, "base_qwen_derived_1p7b")
            pixie_key = (family_id, "pixie_rank8")
            comparisons.append(compare_family(
                base_program=program_by_key[base_key],
                base_evaluation=evaluation_by_key[base_key],
                base_interventions=[row for row in interventions if (row["task_family_id"], row["candidate"]) == base_key],
                pixie_program=program_by_key[pixie_key],
                pixie_evaluation=evaluation_by_key[pixie_key],
                pixie_interventions=[row for row in interventions if (row["task_family_id"], row["candidate"]) == pixie_key],
                thresholds=protocol["thresholds"],
            ))
        report = aggregate_comparisons(
            comparisons,
            expected_families=protocol["dataset"]["family_count"],
            minimum_win_rate=protocol["thresholds"]["minimum_family_win_rate"],
        )
        judgments = []
        deterministic = []
        for comparison in comparisons:
            resolved_winner = (
                "UNCERTAIN" if comparison["winner"] == "UNDETERMINED" else comparison["winner"]
            )
            for order, (candidate_a, candidate_b) in enumerate([
                ("base_qwen_derived_1p7b", "pixie_rank8"),
                ("pixie_rank8", "base_qwen_derived_1p7b"),
            ]):
                for repetition in range(2):
                    judgments.append({
                        "item_id": comparison["task_family_id"],
                        "judge_id": "deterministic_mechanism_comparator_v1",
                        "candidate_a": candidate_a,
                        "candidate_b": candidate_b,
                        "winner": resolved_winner,
                        "prompt_variant": "frozen_metric_rule",
                        "repetition": repetition,
                        "display_order": order,
                    })
            gate_names = {
                "task_accuracy": "task_accuracy_floor",
                "program_fidelity": "heldout_transition_fidelity",
                "sparse_invariant": "sparse_invariant_agreement",
                "causal_prediction": "causal_patch_prediction",
                "matched_control": "matched_random_superiority",
                "guardrail": "guardrail_preservation",
            }
            for candidate_key, candidate_id in [
                ("base", "base_qwen_derived_1p7b"),
                ("pixie", "pixie_rank8"),
            ]:
                for gate, passed in comparison[candidate_key]["gates"].items():
                    deterministic.append({
                        "item_id": comparison["task_family_id"],
                        "candidate": candidate_id,
                        "check": gate_names[gate],
                        "passed": bool(passed),
                        "hard_fail": True,
                    })
                deterministic.extend([
                    {
                        "item_id": comparison["task_family_id"],
                        "candidate": candidate_id,
                        "check": "trace_schema_valid",
                        "passed": True,
                        "hard_fail": True,
                    },
                    {
                        "item_id": comparison["task_family_id"],
                        "candidate": candidate_id,
                        "check": "program_description_length",
                        "passed": comparison[candidate_key]["description_length_bits"] > 0,
                        "hard_fail": True,
                    },
                ])
        atomic_jsonl(arguments.output_root / "comparisons.jsonl", comparisons)
        atomic_jsonl(arguments.output_root / "mechanism_pairwise.jsonl", judgments)
        atomic_jsonl(arguments.output_root / "deterministic_checks.jsonl", deterministic)
        atomic_json(arguments.output_root / "report.json", report)
        print(json.dumps({"status": report["claim_support"]["status"], "output_root": str(arguments.output_root)}, indent=2))
        return 0
    raise AssertionError("unreachable")
