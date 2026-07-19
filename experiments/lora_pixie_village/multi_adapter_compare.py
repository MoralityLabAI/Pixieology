#!/usr/bin/env python3
"""Evaluate the frozen base/singleton/stacked LoRA matrix through an attested proxy.

This is a deterministic, model-free composition smoke. It verifies routing,
identity, non-empty inference, and registered proposal markers. It is not an
NLI or persona-adherence judge and does not establish behavioral non-inferiority.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parents[1]
for root in (APP_ROOT, REPO_ROOT):
    if str(root) not in os.sys.path:
        os.sys.path.insert(0, str(root))

import existing_adapter_pair  # noqa: E402
import multi_adapter_matrix  # noqa: E402
import server  # noqa: E402


PROPOSAL_RE = re.compile(r"\[proposal:([a-z][a-z0-9_-]{0,63})\]", re.IGNORECASE)


class CompareError(RuntimeError):
    """A route, identity, or response violated the frozen comparison contract."""


def request_json(url: str, *, payload: dict[str, Any] | None = None, timeout: float = 240) -> Any:
    body = None if payload is None else server.canonical_json(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise CompareError(f"request failed for {url}: {exc}") from exc


def expected_selection(matrix: dict[str, Any], condition: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"id": int(adapter["adapter_id"]), "scale": float(condition["scales"][adapter["label"]])}
        for adapter in matrix["adapters"]
    ]


def validate_identity(
    identity: Any, matrix: dict[str, Any], condition: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(identity, dict):
        raise CompareError(f"identity for {condition['condition_id']} is not an object")
    expected = expected_selection(matrix, condition)
    if identity.get("matrix_id") != matrix["matrix_id"]:
        raise CompareError(f"identity matrix mismatch for {condition['condition_id']}")
    if identity.get("adapter_label") != condition["condition_id"]:
        raise CompareError(f"identity label mismatch for {condition['condition_id']}")
    if identity.get("model_alias") != condition["model_alias"]:
        raise CompareError(f"identity alias mismatch for {condition['condition_id']}")
    if identity.get("selection", {}).get("request_lora") != expected:
        raise CompareError(f"identity LoRA scales mismatch for {condition['condition_id']}")
    if not isinstance(identity.get("combination_sha256"), str) or len(identity["combination_sha256"]) != 64:
        raise CompareError(f"identity combination hash missing for {condition['condition_id']}")
    return identity


def extract_content(response: Any) -> str:
    try:
        return str(response["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise CompareError("chat response lacks choices[0].message.content") from exc


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompareError(f"cannot read JSON object from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CompareError(f"expected JSON object in {path}")
    return value


def finalize_resource_attestation(
    pointer_path: Path, resource_summary_path: Path, cleanup_path: Path
) -> dict[str, Any]:
    pointer = read_json_object(pointer_path)
    summary = read_json_object(resource_summary_path)
    cleanup = read_json_object(cleanup_path)
    allowed_schemas = {
        "pixie_multi_adapter_compare_pointer_v1",
        "pixie_multi_adapter_noninferiority_pointer_v1",
        "pixie_multi_adapter_noninferiority_companion_pointer_v1",
    }
    if pointer.get("schema_version") not in allowed_schemas:
        raise CompareError("cannot finalize an unknown pointer schema")
    pointer.setdefault("run_id", summary.get("run_id"))
    assertions = {
        "cap_verified": summary.get("cap_verified") is True,
        "cap_not_breached": summary.get("cap_breached") is False,
        "cleanup_passed": cleanup.get("cleanup_passed") is True,
        "no_lingering_owned_pids": cleanup.get("lingering_owned_pids") == [],
    }
    pointer["resource_attestation"] = {
        "assertions": assertions,
        "caps": summary.get("caps"),
        "peak_job_memory_bytes": summary.get("peak_job_memory_bytes"),
        "resource_summary": str(resource_summary_path),
        "resource_summary_sha256": existing_adapter_pair.sha256_file(resource_summary_path),
        "cleanup": str(cleanup_path),
        "cleanup_sha256": existing_adapter_pair.sha256_file(cleanup_path),
        "owned_pids": cleanup.get("owned_pids"),
        "gpu_compute_processes_after_cleanup": cleanup.get("gpu_compute_processes"),
    }
    if not all(assertions.values()):
        pointer["status"] = "FAIL"
    server.atomic_json(pointer_path, pointer)
    return pointer


def run_compare(
    base_url: str,
    matrix: dict[str, Any],
    output_dir: Path,
    *,
    launch_manifest: Path | None = None,
) -> dict[str, Any]:
    if output_dir.exists():
        raise CompareError(f"refusing to overwrite comparison output: {output_dir}")
    output_dir.mkdir(parents=True)
    raw_path = output_dir / "raw_generations.jsonl"
    models = request_json(base_url.rstrip("/") + "/v1/models")
    observed_aliases = {
        str(row.get("id")) for row in models.get("data", []) if isinstance(row, dict)
    }
    expected_aliases = {condition["model_alias"] for condition in matrix["conditions"]}
    if observed_aliases != expected_aliases:
        raise CompareError(
            f"model alias mismatch: expected {sorted(expected_aliases)}, observed {sorted(observed_aliases)}"
        )

    identities: dict[str, dict[str, Any]] = {}
    for condition in matrix["conditions"]:
        label = condition["condition_id"]
        identity = request_json(base_url.rstrip("/") + f"/pixie/identity/{label}")
        identities[label] = validate_identity(identity, matrix, condition)

    rows: list[dict[str, Any]] = []
    for prompt in matrix["prompts"]:
        legal = {str(item).casefold() for item in prompt["legal_proposals"]}
        required_for = set(prompt["proposal_required_for"])
        for condition in matrix["conditions"]:
            request_payload = {
                "model": condition["model_alias"],
                "messages": [
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"]},
                ],
                "temperature": 0,
                "max_tokens": prompt["max_tokens"],
            }
            response = request_json(
                base_url.rstrip("/") + "/v1/chat/completions", payload=request_payload
            )
            content = extract_content(response)
            proposals = [value.casefold() for value in PROPOSAL_RE.findall(content)]
            proposal_required = condition["condition_id"] in required_for
            proposal_valid = len(proposals) == 1 and proposals[0] in legal
            row = {
                "schema_version": "pixie_multi_adapter_generation_v1",
                "matrix_id": matrix["matrix_id"],
                "condition_id": condition["condition_id"],
                "model_alias": condition["model_alias"],
                "prompt_id": prompt["prompt_id"],
                "request_sha256": server.sha256_value(request_payload),
                "response_sha256": server.sha256_value(response),
                "content": content,
                "content_sha256": server.sha256_value(content),
                "proposal_markers": proposals,
                "proposal_required": proposal_required,
                "proposal_valid": proposal_valid,
                "nonempty": bool(content),
            }
            server.append_jsonl_fsync(raw_path, row)
            rows.append(row)

    by_prompt = {
        prompt["prompt_id"]: [row for row in rows if row["prompt_id"] == prompt["prompt_id"]]
        for prompt in matrix["prompts"]
    }
    required_rows = [row for row in rows if row["proposal_required"]]
    assertions = {
        "all_four_aliases_exposed": observed_aliases == expected_aliases,
        "all_four_identities_attested": len(identities) == 4,
        "all_outputs_nonempty": all(row["nonempty"] for row in rows),
        "complete_factorial_generations": len(rows) == len(matrix["conditions"]) * len(matrix["prompts"]),
        "registered_required_proposals_valid": bool(required_rows)
        and all(row["proposal_valid"] for row in required_rows),
    }
    behavior_signals = {
        "unique_outputs_per_prompt": {
            prompt_id: len({row["content"] for row in prompt_rows})
            for prompt_id, prompt_rows in by_prompt.items()
        },
        "stacked_differs_from_base": {
            prompt_id: next(row["content"] for row in prompt_rows if row["condition_id"] == "stacked")
            != next(row["content"] for row in prompt_rows if row["condition_id"] == "base")
            for prompt_id, prompt_rows in by_prompt.items()
        },
        "proposal_valid_by_condition": {
            condition["condition_id"]: {
                row["prompt_id"]: row["proposal_valid"] for row in rows if row["condition_id"] == condition["condition_id"]
            }
            for condition in matrix["conditions"]
        },
    }
    launch_snapshot = None
    if launch_manifest is not None and launch_manifest.is_file():
        launch_snapshot = output_dir / "launch_manifest.ready.json"
        server.atomic_json(launch_snapshot, server.read_json(launch_manifest))
    receipt = {
        "schema_version": "pixie_multi_adapter_compare_v1",
        "status": "PASS" if all(assertions.values()) else "FAIL",
        "evidence_class": "model_free_routing_and_lexical_composition_smoke",
        "matrix_id": matrix["matrix_id"],
        "matrix_sha256": multi_adapter_matrix.sha256_value(matrix),
        "base_url_redacted": True,
        "conditions": [condition["condition_id"] for condition in matrix["conditions"]],
        "prompt_ids": [prompt["prompt_id"] for prompt in matrix["prompts"]],
        "identities": identities,
        "assertions": assertions,
        "behavior_signals": behavior_signals,
        "raw_generations": str(raw_path),
        "raw_generations_sha256": existing_adapter_pair.sha256_file(raw_path),
        "source_launch_manifest": str(launch_manifest) if launch_manifest else None,
        "launch_manifest_ready_snapshot": str(launch_snapshot) if launch_snapshot else None,
        "launch_manifest_sha256": (
            existing_adapter_pair.sha256_file(launch_snapshot)
            if launch_snapshot is not None
            else None
        ),
        "limitation": (
            "Lexical routing smoke only; it does not establish persona adherence, semantic retention, "
            "or non-inferiority of the stacked adapter."
        ),
    }
    server.atomic_json(output_dir / "receipt.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--matrix", type=Path, default=APP_ROOT / "config" / "multi_adapter_matrix_v1.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--launch-manifest", type=Path)
    parser.add_argument("--pointer", type=Path)
    args = parser.parse_args(argv)
    matrix = multi_adapter_matrix.load_matrix(args.matrix.expanduser().resolve())
    receipt = run_compare(
        args.base_url,
        matrix,
        args.output_dir.expanduser().resolve(),
        launch_manifest=args.launch_manifest.expanduser().resolve() if args.launch_manifest else None,
    )
    if args.pointer:
        receipt_path = args.output_dir.expanduser().resolve() / "receipt.json"
        pointer = {
            "schema_version": "pixie_multi_adapter_compare_pointer_v1",
            "status": receipt["status"],
            "run_id": args.output_dir.expanduser().resolve().name,
            "matrix_id": receipt["matrix_id"],
            "receipt": str(receipt_path),
            "receipt_sha256": existing_adapter_pair.sha256_file(receipt_path),
            "assertions": receipt["assertions"],
            "behavior_signals": receipt["behavior_signals"],
            "limitation": receipt["limitation"],
        }
        server.atomic_json(args.pointer.expanduser().resolve(), pointer)
        print(json.dumps(pointer, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
