#!/usr/bin/env python3
"""Run, score, and package the frozen Fae Tax on Epistemics study."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from fae_tax_epistemics import (
    PERSONAS,
    OpenAIChatClient,
    StudyError,
    build_results_bundle,
    build_task_specs,
    evaluate_smoke_gate,
    load_alife_module,
    load_study_manifest,
    read_json,
    record_budget_gate,
    run_model_batch,
    run_port_gate,
    score_full_results,
    snapshot_run_config,
    verify_results_bundle,
    write_seed_manifest,
)
from pixie_env import config_path, repo_path


DEFAULT_MANIFEST = repo_path("experiments", "fae_tax_epistemics_v1", "manifest.json")


def _emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _require_passed(results_root: Path, gate_name: str) -> dict[str, Any]:
    path = results_root / "gates" / gate_name
    if not path.is_file():
        raise StudyError(f"required gate receipt is missing: {path}")
    receipt = read_json(path)
    if receipt.get("status") != "passed":
        raise StudyError(f"required gate has not passed: {path}")
    return receipt


def _effective_samples(args: argparse.Namespace, manifest: Mapping[str, Any]) -> int:
    samples = (
        int(args.samples)
        if getattr(args, "samples", None) is not None
        else int(manifest["design"]["samples_per_task"])
    )
    allowed = {
        int(manifest["design"]["samples_per_task"]),
        int(manifest["design"]["cost_fallback_samples_per_task"]),
    }
    if samples not in allowed:
        raise StudyError(f"samples must be one of the frozen choices: {sorted(allowed)}")
    return samples


def _snapshot(
    args: argparse.Namespace,
    manifest: Mapping[str, Any],
    samples: int,
    *,
    endpoint: str | None = None,
) -> dict[str, Any]:
    write_seed_manifest(
        manifest,
        alife_root=args.alife_root,
        results_root=args.results_root,
        samples=samples,
    )
    return snapshot_run_config(
        args.manifest,
        results_root=args.results_root,
        alife_root=args.alife_root,
        effective_samples=samples,
        endpoint=endpoint,
        provider=args.provider,
        estimated_provider_cost_usd=args.estimated_provider_cost_usd,
    )


def command_port(args: argparse.Namespace, manifest: Mapping[str, Any]) -> Any:
    samples = _effective_samples(args, manifest)
    receipt = run_port_gate(
        manifest,
        alife_root=args.alife_root,
        results_root=args.results_root,
    )
    _snapshot(args, manifest, samples)
    return receipt


def _model_client(args: argparse.Namespace) -> OpenAIChatClient:
    api_key = os.environ.get(args.api_key_env) if args.api_key_env else None
    return OpenAIChatClient(
        args.endpoint,
        api_key=api_key,
        timeout_seconds=float(args.timeout_seconds),
    )


def command_smoke_run(args: argparse.Namespace, manifest: Mapping[str, Any]) -> Any:
    _require_passed(args.results_root, "port_gate_diff.json")
    smoke = manifest["design"]["smoke"]
    model_key = str(smoke["model"])
    alife_module = load_alife_module(args.alife_root)
    alife_manifest = read_json(
        args.alife_root / str(manifest["alife"]["curriculum_manifest"])
    )
    specs = build_task_specs(
        alife_module,
        alife_manifest,
        splits=(str(smoke["split"]),),
        families=tuple(smoke["families"]),
        one_seed=int(smoke["task_seed"]),
    )
    samples = _effective_samples(args, manifest)
    if samples != int(smoke["samples_per_task"]):
        raise StudyError("the smoke gate always uses its frozen three samples per task")
    _snapshot(args, manifest, samples, endpoint=args.endpoint)
    return run_model_batch(
        client=_model_client(args),
        alife_module=alife_module,
        manifest=manifest,
        model_key=model_key,
        personas=PERSONAS,
        specs=specs,
        samples=int(smoke["samples_per_task"]),
        phase="smoke",
        results_root=args.results_root,
    )


def command_smoke_check(args: argparse.Namespace, manifest: Mapping[str, Any]) -> Any:
    _require_passed(args.results_root, "port_gate_diff.json")
    return evaluate_smoke_gate(manifest, results_root=args.results_root)


def command_full_run(args: argparse.Namespace, manifest: Mapping[str, Any]) -> Any:
    _require_passed(args.results_root, "port_gate_diff.json")
    _require_passed(args.results_root, "smoke_receipt.json")
    samples = _effective_samples(args, manifest)
    if args.model_key not in manifest["design"]["models"]:
        raise StudyError(f"unknown frozen model key: {args.model_key}")
    alife_module = load_alife_module(args.alife_root)
    alife_manifest = read_json(
        args.alife_root / str(manifest["alife"]["curriculum_manifest"])
    )
    specs = build_task_specs(alife_module, alife_manifest)
    _snapshot(args, manifest, samples, endpoint=args.endpoint)
    return run_model_batch(
        client=_model_client(args),
        alife_module=alife_module,
        manifest=manifest,
        model_key=args.model_key,
        personas=PERSONAS,
        specs=specs,
        samples=samples,
        phase="full",
        results_root=args.results_root,
    )


def command_score(args: argparse.Namespace, manifest: Mapping[str, Any]) -> Any:
    samples = _effective_samples(args, manifest)
    _snapshot(args, manifest, samples)
    return score_full_results(
        manifest,
        alife_root=args.alife_root,
        results_root=args.results_root,
        samples=samples,
    )


def command_bundle(args: argparse.Namespace, manifest: Mapping[str, Any]) -> Any:
    bundle = build_results_bundle(
        manifest,
        results_root=args.results_root,
        destination=args.destination,
    )
    return {"bundle": str(bundle), "verification": verify_results_bundle(bundle)}


def command_verify_bundle(args: argparse.Namespace, _manifest: Mapping[str, Any]) -> Any:
    return verify_results_bundle(args.bundle)


def command_budget_check(args: argparse.Namespace, manifest: Mapping[str, Any]) -> Any:
    return record_budget_gate(
        manifest,
        results_root=args.results_root,
        provider=args.provider,
        pod_started_epoch_seconds=args.pod_started_epoch_seconds,
        pod_hourly_usd=args.pod_hourly_usd,
        projected_remaining_seconds=args.projected_remaining_seconds,
        stage=args.stage,
        selected_samples=args.samples,
        observed_seconds_per_episode=args.observed_seconds_per_episode,
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    result.add_argument("--alife-root", type=Path, default=config_path("alife_root"))
    result.add_argument(
        "--results-root", type=Path, default=config_path("fae_tax_results_root")
    )
    result.add_argument("--provider", default="local")
    result.add_argument("--estimated-provider-cost-usd", type=float)
    subparsers = result.add_subparsers(dest="command", required=True)

    port = subparsers.add_parser("port", help="run the blocking ALife portability gate")
    port.add_argument("--samples", type=int)
    port.set_defaults(handler=command_port)

    for name, handler in (("smoke-run", command_smoke_run), ("full-run", command_full_run)):
        command = subparsers.add_parser(name)
        command.add_argument("--endpoint", default="http://127.0.0.1:8000")
        command.add_argument("--api-key-env", default="OPENAI_API_KEY")
        command.add_argument("--timeout-seconds", type=float, default=180.0)
        command.add_argument("--samples", type=int)
        if name == "full-run":
            command.add_argument("--model-key", required=True, choices=("1.7B", "4B", "8B"))
        command.set_defaults(handler=handler)

    smoke_check = subparsers.add_parser("smoke-check")
    smoke_check.set_defaults(handler=command_smoke_check)

    score = subparsers.add_parser("score")
    score.add_argument("--samples", type=int)
    score.set_defaults(handler=command_score)

    bundle = subparsers.add_parser("bundle")
    bundle.add_argument("--destination", type=Path)
    bundle.set_defaults(handler=command_bundle)

    verify = subparsers.add_parser("verify-bundle")
    verify.add_argument("bundle", type=Path)
    verify.set_defaults(handler=command_verify_bundle)

    budget = subparsers.add_parser("budget-check")
    budget.add_argument("--pod-started-epoch-seconds", type=float, required=True)
    budget.add_argument("--pod-hourly-usd", type=float, required=True)
    budget.add_argument("--projected-remaining-seconds", type=float, required=True)
    budget.add_argument("--stage", required=True)
    budget.add_argument("--samples", type=int)
    budget.add_argument("--observed-seconds-per-episode", type=float)
    budget.set_defaults(handler=command_budget_check)
    return result


def main() -> int:
    args = parser().parse_args()
    args.manifest = args.manifest.expanduser().resolve()
    args.alife_root = args.alife_root.expanduser().resolve()
    args.results_root = args.results_root.expanduser().resolve()
    try:
        manifest = load_study_manifest(args.manifest)
        _emit(args.handler(args, manifest))
        return 0
    except (StudyError, FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
