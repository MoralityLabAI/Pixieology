"""Command-line conveyor for the versioned motif experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from .analysis import build_catalog, confirm_motifs
from .authorization import authorization_template, validate_authorization
from .capture import capture_chunk
from .evaluation import (
    analyze_human_study,
    intervention_gate,
    predictive_gate,
    random_adapter_max_stat_gate,
)
from .forms import (
    capture_files,
    emit_random_control_forms,
    emit_trained_forms,
    fit_scaler_from_capture,
    scaler_receipt,
)
from .geometry import GlobalScaler
from .io import atomic_json, object_sha256, read_jsonl, sha256_file, write_jsonl
from .interventions import build_intervention_plan, resolve_energy_matched_masks
from .intervention_capture import capture_intervention_task
from .mining import fit_motif_model
from .protocol import (
    build_corpus_from_protocol,
    load_protocol,
    load_repo_config,
    protocol_hash,
    resolve_config_path,
    verify_frozen_inputs,
)
from .reporting import compile_report, publish_catalog_js, write_report_bundle
from .safetensors_raw import materialize_shards, shard_plan
from .synthetic import build_synthetic_forms


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _copy_support_files(source: Path, destination: Path, names: list[str]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        source_path = source / name
        if not source_path.is_file():
            raise FileNotFoundError(f"missing model support file {source_path}")
        target = destination / name
        temporary = target.with_suffix(target.suffix + ".tmp")
        shutil.copyfile(source_path, temporary)
        temporary.replace(target)


def _validate_capture_provenance(
    receipts: list[dict[str, Any]],
    *,
    expected_protocol_sha256: str,
) -> None:
    verified: dict[Path, str] = {}
    for receipt in receipts:
        provenance = receipt.get("provenance", {})
        if receipt.get("condition") != "trained_counterfactual_on_base":
            raise ValueError("trained-form command received a non-trained condition")
        if provenance.get("protocol_sha256") != expected_protocol_sha256:
            raise ValueError("trained form belongs to another protocol")
        artifact = Path(str(provenance.get("capture_artifact", "")))
        expected = str(provenance.get("capture_artifact_sha256", ""))
        marker = artifact.with_suffix(".complete.json")
        if not artifact.is_file() or not marker.is_file():
            raise ValueError(f"form lacks its capture checkpoint or marker: {artifact}")
        if artifact not in verified:
            actual = sha256_file(artifact)
            marker_value = json.loads(marker.read_text(encoding="utf-8"))
            if marker_value.get("artifact_sha256") != actual:
                raise ValueError(f"form capture marker hash mismatch: {artifact}")
            verified[artifact] = actual
        if verified[artifact] != expected:
            raise ValueError(f"form capture provenance hash mismatch: {artifact}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=None)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("verify")
    subcommands.add_parser("corpus")
    subcommands.add_parser("authorization-template")
    authorization_parser = subcommands.add_parser("authorization-check")
    authorization_parser.add_argument("--authorization", type=Path, required=True)
    subcommands.add_parser("output-root")
    subcommands.add_parser("sharded-root")

    shard_plan_parser = subcommands.add_parser("shard-plan")
    shard_plan_parser.add_argument("--source", type=Path)

    shard_parser = subcommands.add_parser("shard-model")
    shard_parser.add_argument("--authorization", type=Path, required=True)

    capture_parser = subcommands.add_parser("capture")
    capture_parser.add_argument("--authorization", type=Path, required=True)
    capture_parser.add_argument("--chunk-index", type=int, required=True)

    intervention_capture_parser = subcommands.add_parser("capture-intervention")
    intervention_capture_parser.add_argument("--authorization", type=Path, required=True)
    intervention_capture_parser.add_argument("--plan", type=Path, required=True)
    intervention_capture_parser.add_argument("--task-index", type=int, required=True)
    intervention_capture_parser.add_argument("--task-count", type=int, default=4)

    scaler_parser = subcommands.add_parser("fit-scaler")
    scaler_parser.add_argument("--capture-root", type=Path, required=True)
    scaler_parser.add_argument("--output", type=Path, required=True)

    forms_parser = subcommands.add_parser("build-forms")
    forms_parser.add_argument("--capture-root", type=Path, required=True)
    forms_parser.add_argument("--scaler", type=Path, required=True)
    forms_parser.add_argument("--output", type=Path, required=True)

    random_parser = subcommands.add_parser("random-controls")
    random_parser.add_argument("--capture-root", type=Path, required=True)
    random_parser.add_argument("--scaler", type=Path, required=True)
    random_parser.add_argument("--output-root", type=Path, required=True)

    mine_parser = subcommands.add_parser("mine")
    mine_parser.add_argument("--forms", type=Path, required=True)
    mine_parser.add_argument("--output", type=Path, required=True)

    confirm_parser = subcommands.add_parser("confirm")
    confirm_parser.add_argument("--forms", type=Path, required=True)
    confirm_parser.add_argument("--model", type=Path, required=True)
    confirm_parser.add_argument("--scaler", type=Path, required=True)
    confirm_parser.add_argument("--output-root", type=Path, required=True)

    predictive_parser = subcommands.add_parser("predictive-gate")
    predictive_parser.add_argument("--forms", type=Path, required=True)
    predictive_parser.add_argument("--output", type=Path, required=True)

    null_parser = subcommands.add_parser("random-null-gate")
    null_parser.add_argument("--trained-forms", type=Path, required=True)
    null_parser.add_argument("--random-root", type=Path, required=True)
    null_parser.add_argument("--model", type=Path, required=True)
    null_parser.add_argument("--output", type=Path, required=True)

    intervention_parser = subcommands.add_parser("intervention-gate")
    intervention_parser.add_argument("--observations", type=Path, required=True)
    intervention_parser.add_argument("--output", type=Path, required=True)

    intervention_plan_parser = subcommands.add_parser("intervention-plan")
    intervention_plan_parser.add_argument("--catalog", type=Path, required=True)
    intervention_plan_parser.add_argument("--output", type=Path, required=True)

    resolve_intervention_parser = subcommands.add_parser("resolve-intervention-plan")
    resolve_intervention_parser.add_argument("--plan", type=Path, required=True)
    resolve_intervention_parser.add_argument("--capture-root", type=Path, required=True)
    resolve_intervention_parser.add_argument("--output", type=Path, required=True)

    study_parser = subcommands.add_parser("human-study")
    study_parser.add_argument("--receipts", type=Path, required=True)
    study_parser.add_argument("--output", type=Path, required=True)

    report_parser = subcommands.add_parser("report")
    report_parser.add_argument("--catalog", type=Path, required=True)
    report_parser.add_argument("--predictive", type=Path)
    report_parser.add_argument("--random-null", type=Path)
    report_parser.add_argument("--intervention", type=Path)
    report_parser.add_argument("--human", type=Path)
    report_parser.add_argument("--output-root", type=Path, required=True)

    publish_parser = subcommands.add_parser("publish-catalog")
    publish_parser.add_argument("--catalog", type=Path, required=True)
    publish_parser.add_argument("--output", type=Path, required=True)

    smoke_parser = subcommands.add_parser("synthetic-smoke")
    smoke_parser.add_argument("--output-root", type=Path, required=True)

    arguments = parser.parse_args(argv)
    experiment_root = Path(__file__).resolve().parents[1]
    repo_root = arguments.repo_root.resolve() if arguments.repo_root else experiment_root.parents[1]
    protocol = load_protocol(experiment_root)
    config = load_repo_config(repo_root)

    if arguments.command == "verify":
        receipt = verify_frozen_inputs(repo_root, experiment_root, require_weights=False)
        _print(receipt)
        return 0 if receipt["ok"] else 1
    if arguments.command == "corpus":
        rows = build_corpus_from_protocol(protocol)
        _print({"schema": "pixieology_etale_corpus_receipt_v1", "rows": len(rows), "sha256": object_sha256(rows)})
        return 0
    if arguments.command == "authorization-template":
        _print(authorization_template(experiment_root, protocol))
        return 0
    if arguments.command == "authorization-check":
        receipt = validate_authorization(
            arguments.authorization,
            experiment_root,
            protocol,
            require_active_wrapper=False,
        )
        _print({"status": "PASS", "run_id": receipt.run_id, "attempt_id": receipt.attempt_id})
        return 0
    if arguments.command == "output-root":
        print(resolve_config_path(repo_root, config, "pixie_etale_motif_output_root"))
        return 0
    if arguments.command == "sharded-root":
        print(resolve_config_path(repo_root, config, "pixie_etale_motif_sharded_model_root"))
        return 0
    if arguments.command == "shard-plan":
        source = arguments.source or (
            resolve_config_path(repo_root, config, "godel_globes_bonsai_unpacked_hf")
            / protocol["model"]["weights_file"]
        )
        _print(shard_plan(source, int(protocol["loader"]["target_shard_bytes"])))
        return 0
    if arguments.command == "shard-model":
        validate_authorization(arguments.authorization, experiment_root, protocol, require_active_wrapper=True)
        frozen = verify_frozen_inputs(repo_root, experiment_root, require_weights=True)
        if not frozen["ok"]:
            raise ValueError(f"frozen inputs failed: {frozen['checks']}")
        source_root = Path(frozen["model"])
        source = source_root / protocol["model"]["weights_file"]
        destination = resolve_config_path(repo_root, config, "pixie_etale_motif_sharded_model_root")
        manifest = materialize_shards(
            source,
            destination,
            target_bytes=int(protocol["loader"]["target_shard_bytes"]),
            expected_source_sha256=protocol["model"]["weights_sha256"],
            protocol_sha256=protocol_hash(experiment_root),
        )
        _copy_support_files(source_root, destination, list(protocol["model"]["support_files"]))
        _print(manifest)
        return 0
    if arguments.command == "capture":
        _print(
            capture_chunk(
                repo_root,
                experiment_root,
                arguments.authorization,
                chunk_index=arguments.chunk_index,
            )
        )
        return 0
    if arguments.command == "capture-intervention":
        _print(
            capture_intervention_task(
                repo_root,
                experiment_root,
                arguments.authorization,
                arguments.plan,
                task_index=arguments.task_index,
                task_count=arguments.task_count,
            )
        )
        return 0
    if arguments.command == "fit-scaler":
        paths = capture_files(arguments.capture_root)
        scaler = fit_scaler_from_capture(paths)
        receipt = scaler_receipt(scaler)
        atomic_json(arguments.output, receipt)
        _print(receipt)
        return 0
    if arguments.command == "build-forms":
        scaler_value = json.loads(arguments.scaler.read_text(encoding="utf-8"))
        scaler = GlobalScaler.from_dict(scaler_value)
        paths = capture_files(arguments.capture_root)
        forms = emit_trained_forms(
            paths,
            arguments.output,
            corpus_rows=build_corpus_from_protocol(protocol),
            module_ids=protocol["module_ids"],
            scaler=scaler,
            scaler_sha256=sha256_file(arguments.scaler),
            protocol_sha256=protocol_hash(experiment_root),
        )
        _print({"status": "COMPLETE", "form_count": len(forms), "artifact": str(arguments.output), "sha256": sha256_file(arguments.output)})
        return 0
    if arguments.command == "random-controls":
        scaler = GlobalScaler.from_dict(json.loads(arguments.scaler.read_text(encoding="utf-8")))
        frozen = verify_frozen_inputs(repo_root, experiment_root)
        if not frozen["ok"]:
            raise ValueError(f"frozen inputs failed: {frozen['checks']}")
        summaries = emit_random_control_forms(
            capture_files(arguments.capture_root),
            arguments.output_root,
            adapter_path=Path(frozen["adapter"]),
            corpus_rows=build_corpus_from_protocol(protocol),
            module_ids=protocol["module_ids"],
            scaler=scaler,
            scaler_sha256=sha256_file(arguments.scaler),
            protocol_sha256=protocol_hash(experiment_root),
            root_seed=int(protocol["seeds"]["random_adapter"]),
            control_count=int(protocol["controls"]["random_adapter_count"]),
        )
        _print({"status": "COMPLETE", "controls": summaries})
        return 0
    if arguments.command == "mine":
        receipts = [row for row in read_jsonl(arguments.forms) if row["input"]["split"] == "discovery"]
        _validate_capture_provenance(receipts, expected_protocol_sha256=protocol_hash(experiment_root))
        model = fit_motif_model(
            receipts,
            silhouette_floor=float(protocol["mining"]["silhouette_floor"]),
            stability_floor=float(protocol["mining"]["stability_floor"]),
            minimum_semantic_groups=int(protocol["mining"]["minimum_semantic_groups"]),
            stability_replicates=int(protocol["mining"]["stability_replicates"]),
            seed=int(protocol["seeds"]["mining"]),
        )
        atomic_json(arguments.output, model)
        _print({"status": model["status"], "motif_count": len(model["motifs"]), "artifact": str(arguments.output)})
        return 0 if model["status"] == "CANDIDATES_FROZEN" else 2
    if arguments.command == "confirm":
        model = json.loads(arguments.model.read_text(encoding="utf-8"))
        receipts = [row for row in read_jsonl(arguments.forms) if row["input"]["split"] == "confirmation"]
        _validate_capture_provenance(receipts, expected_protocol_sha256=protocol_hash(experiment_root))
        confirmation = confirm_motifs(receipts, model)
        arguments.output_root.mkdir(parents=True, exist_ok=True)
        atomic_json(arguments.output_root / "confirmation.json", confirmation)
        catalog = build_catalog(
            confirmation,
            protocol_sha256=protocol_hash(experiment_root),
            scaler_sha256=sha256_file(arguments.scaler),
            confirmation_receipts=receipts,
        )
        atomic_json(arguments.output_root / "motif_catalog.json", catalog)
        _print({"status": catalog["status"], "motif_count": len(catalog["motifs"])})
        return 0 if catalog["motifs"] else 2
    if arguments.command == "predictive-gate":
        forms = read_jsonl(arguments.forms)
        _validate_capture_provenance(forms, expected_protocol_sha256=protocol_hash(experiment_root))
        result = predictive_gate(
            [form for form in forms if form["input"]["split"] == "discovery"],
            [form for form in forms if form["input"]["split"] == "confirmation"],
            minimum_increment=float(protocol["mining"]["predictive_r2_increment"]),
            bootstrap_replicates=int(protocol["evaluation"]["bootstrap_replicates"]),
            seed=int(protocol["seeds"]["bootstrap"]),
        )
        atomic_json(arguments.output, result)
        _print(result)
        return 0 if result["status"] == "PASS" else 2
    if arguments.command == "random-null-gate":
        trained = [
            form for form in read_jsonl(arguments.trained_forms)
            if form["input"]["split"] == "confirmation"
        ]
        _validate_capture_provenance(trained, expected_protocol_sha256=protocol_hash(experiment_root))
        trusted_captures = {
            (
                str(form["provenance"]["capture_artifact"]),
                str(form["provenance"]["capture_artifact_sha256"]),
            )
            for form in trained
        }
        def random_sets():
            for index in range(int(protocol["controls"]["random_adapter_count"])):
                path = arguments.random_root / f"random_{index:02d}.jsonl"
                forms = [
                    form for form in read_jsonl(path)
                    if form["input"]["split"] == "confirmation"
                ]
                for form in forms:
                    provenance = form.get("provenance", {})
                    if form.get("condition") != f"random_{index:02d}":
                        raise ValueError(f"random control condition mismatch in {path}")
                    if (
                        str(provenance.get("capture_artifact", "")),
                        str(provenance.get("capture_artifact_sha256", "")),
                    ) not in trusted_captures:
                        raise ValueError(f"random control capture provenance mismatch in {path}")
                    if provenance.get("random_control", {}).get("index") != index:
                        raise ValueError(f"random control index mismatch in {path}")
                yield forms
        result = random_adapter_max_stat_gate(
            trained,
            random_sets(),
            json.loads(arguments.model.read_text(encoding="utf-8")),
        )
        atomic_json(arguments.output, result)
        _print(result)
        return 0 if result["status"] == "PASS" else 2
    if arguments.command == "intervention-gate":
        result = intervention_gate(
            read_jsonl(arguments.observations),
            effect_floor=float(protocol["mining"]["causal_standardized_effect"]),
            bootstrap_replicates=int(protocol["evaluation"]["bootstrap_replicates"]),
            seed=int(protocol["seeds"]["bootstrap"]),
        )
        atomic_json(arguments.output, result)
        _print(result)
        return 0 if result["status"] == "PASS" else 2
    if arguments.command == "intervention-plan":
        result = build_intervention_plan(json.loads(arguments.catalog.read_text(encoding="utf-8")))
        atomic_json(arguments.output, result)
        _print(result)
        return 0 if result["task_count"] else 2
    if arguments.command == "resolve-intervention-plan":
        result = resolve_energy_matched_masks(
            json.loads(arguments.plan.read_text(encoding="utf-8")),
            capture_files(arguments.capture_root),
            protocol["module_ids"],
        )
        atomic_json(arguments.output, result)
        _print({
            "status": result["execution_status"],
            "task_count": result["task_count"],
            "artifact": str(arguments.output),
            "artifact_sha256": sha256_file(arguments.output),
        })
        return 0
    if arguments.command == "human-study":
        craft = protocol["evaluation"]["craft"]
        learning = protocol["evaluation"]["learning"]
        result = analyze_human_study(
            read_jsonl(arguments.receipts),
            craft_minimum_participants=int(craft["minimum_paired_participants"]),
            craft_correctness_increment=float(craft["correctness_increment"]),
            craft_maximum_time_ratio=float(craft["maximum_median_time_ratio"]),
            craft_maximum_unsupported_increment=float(craft["maximum_unsupported_claim_increment"]),
            learning_minimum_participants=int(learning["minimum_participants"]),
            learning_transfer_increment=float(learning["transfer_accuracy_increment"]),
            learning_retention_fraction=float(learning["retention_fraction"]),
        )
        atomic_json(arguments.output, result)
        _print(result)
        return 0 if result["status"] == "PASS" else 2
    if arguments.command == "report":
        read_optional = lambda path: None if path is None else json.loads(path.read_text(encoding="utf-8"))
        report, catalog = compile_report(
            json.loads(arguments.catalog.read_text(encoding="utf-8")),
            predictive=read_optional(arguments.predictive),
            random_null=read_optional(arguments.random_null),
            intervention=read_optional(arguments.intervention),
            human=read_optional(arguments.human),
        )
        artifacts = write_report_bundle(arguments.output_root, report, catalog)
        _print({**report, "artifacts": artifacts})
        return 0 if report["verdict"] == "MOTIF_CATALOG_VALIDATED" else 2
    if arguments.command == "publish-catalog":
        catalog = json.loads(arguments.catalog.read_text(encoding="utf-8"))
        publish_catalog_js(catalog, arguments.output)
        result = {
            "status": "PUBLISHED",
            "catalog_status": catalog["status"],
            "artifact": str(arguments.output),
            "artifact_sha256": sha256_file(arguments.output),
        }
        _print(result)
        return 0
    if arguments.command == "synthetic-smoke":
        rows = build_corpus_from_protocol(protocol)
        forms = build_synthetic_forms(rows, protocol["module_ids"])
        arguments.output_root.mkdir(parents=True, exist_ok=True)
        forms_path = arguments.output_root / "synthetic_forms.jsonl"
        write_jsonl(forms_path, forms)
        discovery = [form for form in forms if form["input"]["split"] == "discovery"]
        model = fit_motif_model(
            discovery,
            silhouette_floor=-1.0,
            stability_floor=0.0,
            minimum_semantic_groups=2,
            stability_replicates=8,
            seed=int(protocol["seeds"]["mining"]),
        )
        atomic_json(arguments.output_root / "synthetic_model.json", model)
        confirmation = confirm_motifs(
            [form for form in forms if form["input"]["split"] == "confirmation"],
            model,
            minimum_inputs=1,
            minimum_families=1,
            paraphrase_agreement_floor=0.0,
            semantic_gap_floor=-1.0,
        )
        atomic_json(arguments.output_root / "synthetic_confirmation.json", confirmation)
        receipt = {
            "schema": "pixieology_etale_synthetic_smoke_v1",
            "status": "PASS" if model["motifs"] and confirmation["assignments"] else "FAIL",
            "human_evidence": False,
            "real_model_evidence": False,
            "form_count": len(forms),
            "motif_count": len(model["motifs"]),
            "artifacts": {
                "forms": sha256_file(forms_path),
                "model": sha256_file(arguments.output_root / "synthetic_model.json"),
                "confirmation": sha256_file(arguments.output_root / "synthetic_confirmation.json"),
            },
        }
        atomic_json(arguments.output_root / "synthetic_smoke.json", receipt)
        _print(receipt)
        return 0 if receipt["status"] == "PASS" else 1
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
