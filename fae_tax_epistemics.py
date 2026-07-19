"""Auditable runner primitives for the Fae Tax on Epistemics study.

The module imports ALife's frozen task generator and ``score_submission`` at
runtime. It never copies or modifies the scoring function. Model outputs that
fail strict JSON or protocol validation remain explicit failure outcomes and
are never converted into abstentions.
"""

from __future__ import annotations

from collections import defaultdict
import copy
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any, Iterable, Mapping, Sequence
from urllib import error as urlerror
from urllib import request as urlrequest
import zipfile

import numpy as np

from fae_bench.scoring import fae_score_lexical


STUDY_SCHEMA = "pixieology.fae_tax_epistemics.v1"
MODEL_EPISODE_SCHEMA = "pixieology.fae_tax_epistemics.episode.v1"
SCORE_SUMMARY_SCHEMA = "pixieology.fae_tax_epistemics.summary.v1"
PORT_GATE_SCHEMA = "pixieology.fae_tax_epistemics.port_gate.v1"
SMOKE_GATE_SCHEMA = "pixieology.fae_tax_epistemics.smoke_gate.v1"
BUNDLE_MANIFEST_SCHEMA = "pixieology.fae_tax_epistemics.bundle.v1"
BUDGET_GATE_SCHEMA = "pixieology.fae_tax_epistemics.budget_gate.v1"
PERSONAS = ("josie", "fae")
FULL_SPLITS = ("discovery", "confirmatory", "holdout")
FREE_PROVIDERS = frozenset({"local", "owned", "self_hosted_owned"})


class StudyError(RuntimeError):
    """Raised when a frozen protocol, gate, or result invariant fails."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: str | Path, value: Any) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise StudyError(f"expected JSON object: {path}")
    return value


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if any(not isinstance(row, dict) for row in rows):
        raise StudyError(f"expected JSON objects in JSONL: {path}")
    return rows


def load_study_manifest(path: str | Path) -> dict[str, Any]:
    manifest = read_json(path)
    if manifest.get("schema") != "alife.experiment.v1" or manifest.get("study_schema") != STUDY_SCHEMA:
        raise StudyError("unsupported Fae Tax study manifest")
    return manifest


def load_alife_module(alife_root: str | Path):
    source = Path(alife_root).expanduser().resolve() / "src" / "discovery_curriculum.py"
    if not source.is_file():
        raise FileNotFoundError(f"ALife discovery curriculum not found: {source}")
    spec = importlib.util.spec_from_file_location("fae_tax_alife_discovery_curriculum", source)
    if spec is None or spec.loader is None:
        raise StudyError(f"could not load ALife module: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_value(root: Path, *args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run_port_gate(
    manifest: Mapping[str, Any],
    *,
    alife_root: str | Path,
    results_root: str | Path,
) -> dict[str, Any]:
    """Regenerate all 63 references and compare portable semantic evidence.

    JSONL byte hashes are recorded diagnostically because line endings differ
    across operating systems. The blocking content receipt is the SHA-256 of
    the canonical parsed episode list, alongside ALife's own replay digest and
    the exact holdout score comparisons.
    """

    root = Path(alife_root).expanduser().resolve()
    destination = Path(results_root).expanduser().resolve()
    gate_dir = destination / "gates"
    gate_dir.mkdir(parents=True, exist_ok=True)
    gate_path = gate_dir / "port_gate_diff.json"
    if gate_path.is_file():
        previous = read_json(gate_path)
        attempt = 1
        while (gate_dir / f"port_gate_attempt_{attempt}_{previous.get('status', 'unknown')}.json").exists():
            attempt += 1
        shutil.copy2(
            gate_path,
            gate_dir / f"port_gate_attempt_{attempt}_{previous.get('status', 'unknown')}.json",
        )
    rerun_dir = destination / "scores" / "reference_rerun"
    alife = manifest["alife"]
    expected_commit = str(alife["commit"])
    actual_commit = _git_value(root, "rev-parse", "HEAD")
    errors: list[str] = []
    warnings: list[str] = []
    if actual_commit != expected_commit:
        errors.append(f"ALife commit mismatch: expected {expected_commit}, got {actual_commit}")

    curriculum_manifest = root / str(alife["curriculum_manifest"])
    recorded_root = root / str(alife["recorded_results"])
    verifier = root / "src" / "verify_discovery_curriculum_artifacts.py"
    if recorded_root.is_dir():
        verify_process = subprocess.run(
            [sys.executable, str(verifier), str(recorded_root), "--portable"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        try:
            verifier_receipt = json.loads(verify_process.stdout)
        except json.JSONDecodeError:
            verifier_receipt = {
                "valid": False,
                "stdout": verify_process.stdout,
                "stderr": verify_process.stderr,
            }
        if verify_process.returncode != 0 or not verifier_receipt.get("valid"):
            errors.append("recorded ALife reference artifacts failed portable verification")
    else:
        verifier_receipt = {
            "valid": None,
            "status": "not_shipped_in_public_checkout",
            "path": str(recorded_root),
        }
        warnings.append(
            "the public ALife checkout does not ship recorded result artifacts; "
            "the frozen manifest receipts and regenerated evidence are used"
        )

    rerun_dir.mkdir(parents=True, exist_ok=True)
    run_process = subprocess.run(
        [
            sys.executable,
            str(root / "src" / "discovery_curriculum.py"),
            "--manifest",
            str(curriculum_manifest),
            "--output",
            str(rerun_dir),
            "--splits",
            "all",
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if run_process.returncode != 0:
        errors.append(f"reference regeneration failed: {run_process.stderr.strip()}")

    expected_scores = dict(alife["reference_holdout_scores"])
    actual_scores: dict[str, Any] = {}
    score_diffs: dict[str, Any] = {}
    raw_byte_actual: str | None = None
    raw_canonical_actual: str | None = None
    determinism_receipt: dict[str, Any] = {}
    if (rerun_dir / "summary.json").is_file():
        rerun_summary = read_json(rerun_dir / "summary.json")
        actual_scores = dict(rerun_summary.get("holdout_scores", {}))
        tolerance = float(alife["port_float_tolerance"])
        for policy, expected in expected_scores.items():
            actual = actual_scores.get(policy)
            delta = float(actual) - float(expected) if isinstance(actual, (int, float)) else None
            score_diffs[policy] = {"expected": expected, "actual": actual, "delta": delta}
            if delta is None or abs(delta) > tolerance:
                errors.append(f"reference holdout score mismatch for {policy}")
        determinism_receipt = dict(rerun_summary.get("determinism", {}))
        expected_determinism = str(alife["reference_determinism_sha256"])
        if (
            determinism_receipt.get("passed") is not True
            or determinism_receipt.get("first_sha256") != expected_determinism
            or determinism_receipt.get("replay_sha256") != expected_determinism
        ):
            errors.append("ALife deterministic replay digest mismatch")
    else:
        errors.append("reference rerun did not produce summary.json")

    raw_path = rerun_dir / "raw_episodes.jsonl"
    if raw_path.is_file():
        raw_byte_actual = sha256_file(raw_path)
        raw_canonical_actual = sha256_bytes(
            canonical_json(read_jsonl(raw_path)).encode("utf-8")
        )
        if raw_canonical_actual != alife["reference_canonical_episodes_sha256"]:
            errors.append("reference canonical episode SHA-256 mismatch")
        if raw_byte_actual != alife["reference_raw_episodes_sha256"]:
            warnings.append("raw JSONL byte hash differs because of platform line endings")
    else:
        errors.append("reference rerun did not produce raw_episodes.jsonl")

    receipt = {
        "schema": PORT_GATE_SCHEMA,
        "status": "passed" if not errors else "failed",
        "checked_utc": utc_now(),
        "alife_commit": {"expected": expected_commit, "actual": actual_commit},
        "portable_verifier": verifier_receipt,
        "holdout_score_diffs": score_diffs,
        "determinism": {
            "expected": alife["reference_determinism_sha256"],
            "actual": determinism_receipt,
        },
        "canonical_episodes_sha256": {
            "expected": alife["reference_canonical_episodes_sha256"],
            "actual": raw_canonical_actual,
        },
        "raw_jsonl_byte_sha256_diagnostic": {
            "expected_windows_recording": alife["reference_raw_episodes_sha256"],
            "actual": raw_byte_actual,
        },
        "float_tolerance": alife["port_float_tolerance"],
        "reference_command": run_process.args,
        "warnings": warnings,
        "errors": errors,
    }
    write_json(gate_path, receipt)
    if errors:
        raise StudyError("PORT GATE FAILED: " + "; ".join(errors))
    return receipt


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    split: str
    family: str
    task_seed: int
    size: int
    horizon: int
    task: Mapping[str, Any]


def build_task_specs(
    alife_module,
    alife_manifest: Mapping[str, Any],
    *,
    splits: Sequence[str] = FULL_SPLITS,
    families: Sequence[str] | None = None,
    one_seed: int | None = None,
) -> list[TaskSpec]:
    selected_families = tuple(families or alife_module.TASK_FAMILIES)
    specs: list[TaskSpec] = []
    for split in splits:
        size = int(alife_manifest["design"]["size_by_split"][split])
        horizon = int(alife_manifest["design"]["horizon_by_split"][split])
        seeds = [one_seed] if one_seed is not None else list(alife_manifest["seed_plan"][split])
        for task_seed in seeds:
            for family in selected_families:
                task = alife_module.build_task(family, int(task_seed), size, horizon)
                task_id = f"{split}:{family}:{int(task_seed)}"
                specs.append(
                    TaskSpec(
                        task_id=task_id,
                        split=split,
                        family=family,
                        task_seed=int(task_seed),
                        size=size,
                        horizon=horizon,
                        task=task,
                    )
                )
    return specs


def paired_sampling_seed(
    manifest: Mapping[str, Any], model_key: str, task_id: str, sample_index: int
) -> int:
    salt = str(manifest["seed_plan"]["sampling_seed_salt"])
    digest = hashlib.sha256(
        f"{salt}|{model_key}|{task_id}|{sample_index}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def request_seed(base_seed: int, request_index: int) -> int:
    return (base_seed + 1_000_003 * request_index) & 0x7FFFFFFF


def _registration_prompt(task: Mapping[str, Any]) -> str:
    public = {key: value for key, value in task.items() if key != "oracle"}
    payload = {
        "public": public["public"],
        "family": public["family"],
        "identification_target": public["identification"],
        "registration_template": public["registration_template"],
    }
    return "\n".join(
        [
            "Hidden-oracle discovery curriculum: registration stage.",
            "You may use only the public task below. The hidden oracle is unavailable.",
            "Before any simulator calls, return exactly one JSON object with this shape:",
            '{"registration":{"claim_type":"copy template exactly","q_success":0.0,"required_precision":"copy template exactly","budget":"copy template exactly"},"identifiability_forecast":"string","investigation_plan":["string"]}',
            "q_success is your probability that the registered target is identifiable within budget.",
            "Use persona voice only inside string-valued explanations; never alter keys, numbers, or claim semantics.",
            canonical_json(payload),
        ]
    )


def _investigation_prompt(registration: Mapping[str, Any], has_tool: bool) -> str:
    tool_text = (
        "Use the simulate tool only when useful and never exceed the frozen budget."
        if has_tool
        else "No simulator calls are available for this task."
    )
    return "\n".join(
        [
            "Registration is now frozen:",
            canonical_json(registration),
            tool_text,
            "When investigation is complete, return exactly one JSON object:",
            '{"action":"claim|abstain","claim":"typed value or null","investigation_trace":["string"],"rationale":"string"}',
            "A parse failure is a separate outcome, not an abstention. Keep all factual values exact.",
        ]
    )


def strict_json_object(text: Any) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("response content is empty")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("response JSON must be an object")
    return value


def validate_registration(
    value: Mapping[str, Any], template: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if set(value) != {"registration", "identifiability_forecast", "investigation_plan"}:
        raise StudyError("registration object has unexpected or missing keys")
    registration = value.get("registration")
    if not isinstance(registration, Mapping):
        raise StudyError("registration must be an object")
    required_keys = {"claim_type", "q_success", "required_precision", "budget"}
    if set(registration) != required_keys:
        raise StudyError("registration has unexpected or missing keys")
    for key in ("claim_type", "required_precision", "budget"):
        if registration.get(key) != template.get(key):
            raise StudyError(f"registration.{key} differs from frozen template")
    q_success = registration.get("q_success")
    if isinstance(q_success, bool) or not isinstance(q_success, (int, float)) or not 0 <= q_success <= 1:
        raise StudyError("registration.q_success must be numeric in [0,1]")
    forecast = value.get("identifiability_forecast")
    plan = value.get("investigation_plan")
    if not isinstance(forecast, str) or not forecast.strip():
        raise StudyError("identifiability_forecast must be a non-empty string")
    if not isinstance(plan, list) or not plan or any(not isinstance(item, str) or not item.strip() for item in plan):
        raise StudyError("investigation_plan must be a non-empty string list")
    return dict(registration), {
        "identifiability_forecast": forecast,
        "investigation_plan": list(plan),
    }


def _valid_claim_type(claim_type: str, claim: Any) -> bool:
    if claim_type == "numeric_point":
        return isinstance(claim, (int, float)) and not isinstance(claim, bool) and math.isfinite(float(claim))
    if claim_type == "boolean":
        return isinstance(claim, bool)
    if claim_type == "categorical":
        return isinstance(claim, str) and bool(claim.strip())
    if claim_type == "site_set":
        return isinstance(claim, list) and all(isinstance(item, int) and not isinstance(item, bool) for item in claim)
    if claim_type == "numeric_interval":
        return (
            isinstance(claim, list)
            and len(claim) == 2
            and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in claim)
            and all(math.isfinite(float(item)) for item in claim)
            and float(claim[0]) <= float(claim[1])
        )
    return False


def validate_final(value: Mapping[str, Any], claim_type: str) -> dict[str, Any]:
    required = {"action", "claim", "investigation_trace", "rationale"}
    if set(value) != required:
        raise StudyError("final object has unexpected or missing keys")
    action = value.get("action")
    claim = value.get("claim")
    trace = value.get("investigation_trace")
    rationale = value.get("rationale")
    if action not in {"claim", "abstain"}:
        raise StudyError("action must be claim or abstain")
    if action == "abstain" and claim is not None:
        raise StudyError("abstention claim must be null")
    if action == "claim" and not _valid_claim_type(claim_type, claim):
        raise StudyError(f"claim does not match registered type {claim_type}")
    if not isinstance(trace, list) or any(not isinstance(item, str) for item in trace):
        raise StudyError("investigation_trace must be a string list")
    if not isinstance(rationale, str):
        raise StudyError("rationale must be a string")
    return {
        "action": action,
        "claim": copy.deepcopy(claim),
        "investigation_trace": list(trace),
        "rationale": rationale,
    }


def tool_definition(task: Mapping[str, Any]) -> dict[str, Any] | None:
    budget = int(task["registration_template"]["budget"])
    if budget <= 0:
        return None
    family = str(task["family"])
    if family in {"planted_effect", "true_null"}:
        parameters = {
            "type": "object",
            "properties": {"condition": {"type": "string", "enum": ["baseline", "treated"]}},
            "required": ["condition"],
            "additionalProperties": False,
        }
        description = "Run the public Rule-90 world under baseline or the declared treatment and return its final density."
    elif family == "causal_sites":
        parameters = {
            "type": "object",
            "properties": {"flip_initial_site": {"type": "integer", "minimum": -1, "maximum": int(task["public"]["size"]) - 1}},
            "required": ["flip_initial_site"],
            "additionalProperties": False,
        }
        description = "Run the public Rule-90 world and return the target-cell value; -1 is baseline, otherwise flip that initial site."
    elif family == "conserved_quantity":
        parameters = {
            "type": "object",
            "properties": {"steps": {"type": "integer", "minimum": 0, "maximum": int(task["public"]["horizon"])}},
            "required": ["steps"],
            "additionalProperties": False,
        }
        description = "Run the public cyclic-shift simulator for the requested number of steps and return the state and diagnostics."
    elif family == "structural_unreachability":
        parameters = {
            "type": "object",
            "properties": {"node": {"type": "integer", "minimum": 0, "maximum": int(task["public"]["nodes"]) - 1}},
            "required": ["node"],
            "additionalProperties": False,
        }
        description = "Inspect one public directed-graph node and return its outgoing neighbors for a budgeted reachability search."
    else:
        return None
    return {
        "type": "function",
        "function": {
            "name": "simulate",
            "description": description,
            "strict": True,
            "parameters": parameters,
        },
    }


def execute_tool(alife_module, task: Mapping[str, Any], arguments: Mapping[str, Any]) -> dict[str, Any]:
    family = str(task["family"])
    public = task["public"]
    if family in {"planted_effect", "true_null"}:
        if set(arguments) != {"condition"} or arguments["condition"] not in {"baseline", "treated"}:
            raise StudyError("invalid Rule-90 tool arguments")
        state = np.asarray(public["initial_state"], dtype=bool)
        if arguments["condition"] == "treated" and family == "planted_effect":
            state = state.copy()
            site = int(public["intervention"]["flip_initial_site"])
            state[site] = ~state[site]
        final = alife_module.simulate_rule90(state, int(public["horizon"]))
        return {
            "condition": arguments["condition"],
            "final_density": float(final.mean()),
            "final_state": final.astype(int).tolist(),
        }
    if family == "causal_sites":
        if set(arguments) != {"flip_initial_site"}:
            raise StudyError("invalid causal-sites tool arguments")
        site = arguments["flip_initial_site"]
        if isinstance(site, bool) or not isinstance(site, int) or not -1 <= site < int(public["size"]):
            raise StudyError("flip_initial_site is outside the public ring")
        state = np.asarray(public["initial_state"], dtype=bool)
        if site >= 0:
            state = state.copy()
            state[site] = ~state[site]
        final = alife_module.simulate_rule90(state, int(public["horizon"]))
        target = int(public["target_cell"])
        return {"flip_initial_site": site, "target_cell": target, "target_value": bool(final[target])}
    if family == "conserved_quantity":
        if set(arguments) != {"steps"}:
            raise StudyError("invalid cyclic-shift tool arguments")
        steps = arguments["steps"]
        if isinstance(steps, bool) or not isinstance(steps, int) or not 0 <= steps <= int(public["horizon"]):
            raise StudyError("steps is outside the registered horizon")
        state = np.asarray(public["initial_state"], dtype=bool)
        final = alife_module.simulate_shift(state, steps)
        return {
            "steps": steps,
            "state": final.astype(int).tolist(),
            "live_count": int(final.sum()),
            "first_cell": int(final[0]),
            "adjacent_equal_pairs": int(np.sum(final == np.roll(final, -1))),
        }
    if family == "structural_unreachability":
        if set(arguments) != {"node"}:
            raise StudyError("invalid graph tool arguments")
        node = arguments["node"]
        if isinstance(node, bool) or not isinstance(node, int) or not 0 <= node < int(public["nodes"]):
            raise StudyError("node is outside the public graph")
        neighbors = sorted(int(right) for left, right in public["edges"] if int(left) == node)
        return {"node": node, "outgoing_neighbors": neighbors, "is_target": node == int(public["target"])}
    raise StudyError(f"no tool is available for family {family}")


class OpenAIChatClient:
    """Small standard-library client that preserves raw OpenAI-compatible responses."""

    def __init__(self, base_url: str, *, api_key: str | None = None, timeout_seconds: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def chat(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = canonical_json(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urlrequest.Request(
            f"{self.base_url}/v1/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except urlerror.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise StudyError(f"chat API HTTP {exc.code}: {detail[:1000]}") from exc
        except (urlerror.URLError, TimeoutError) as exc:
            raise StudyError(f"chat API request failed: {exc}") from exc
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StudyError(f"chat API returned non-JSON: {raw[:500]!r}") from exc
        if not isinstance(value, dict):
            raise StudyError("chat API response must be an object")
        return value


def _choice_message(response: Mapping[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        raise StudyError("chat API response must contain exactly one choice")
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        raise StudyError("chat API choice lacks a message object")
    return dict(message)


def _message_for_history(message: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "role": "assistant",
        "content": message.get("content"),
    }
    if message.get("tool_calls") is not None:
        result["tool_calls"] = copy.deepcopy(message["tool_calls"])
    return result


def _assistant_text(response: Mapping[str, Any]) -> str:
    content = _choice_message(response).get("content")
    return content if isinstance(content, str) else ""


def _finalize_episode(episode: dict[str, Any], assistant_texts: Sequence[str]) -> dict[str, Any]:
    combined = "\n".join(text for text in assistant_texts if text)
    episode["assistant_text"] = combined
    episode["whimsy_marker_density"] = fae_score_lexical({"response": combined}) if combined else 0.0
    unhashed = dict(episode)
    episode["episode_sha256"] = sha256_bytes(canonical_json(unhashed).encode("utf-8"))
    return episode


def run_model_episode(
    *,
    client: OpenAIChatClient,
    alife_module,
    manifest: Mapping[str, Any],
    model_key: str,
    model_id: str,
    model_revision: str,
    persona: str,
    spec: TaskSpec,
    sample_index: int,
    phase: str,
) -> dict[str, Any]:
    """Run registration, budgeted investigation, and a strict final JSON claim."""

    if persona not in PERSONAS:
        raise ValueError(f"unknown persona: {persona}")
    design = manifest["design"]
    system_prompt = next(
        row["changes"]["system_prompt"]
        for row in manifest["interventions"]
        if row["name"] == persona
    )
    base_seed = paired_sampling_seed(manifest, model_key, spec.task_id, sample_index)
    public_task = {key: copy.deepcopy(value) for key, value in spec.task.items() if key != "oracle"}
    episode_id = f"{phase}:{model_key}:{persona}:{spec.task_id}:sample-{sample_index}"
    episode: dict[str, Any] = {
        "schema": MODEL_EPISODE_SCHEMA,
        "episode_id": episode_id,
        "phase": phase,
        "model_key": model_key,
        "model_id": model_id,
        "model_revision": model_revision,
        "persona": persona,
        "split": spec.split,
        "family": spec.family,
        "task_id": spec.task_id,
        "task_seed": spec.task_seed,
        "sample_index": sample_index,
        "sampling_seed": base_seed,
        "temperature": design["temperature"],
        "enable_thinking": design["enable_thinking"],
        "public_task": public_task,
        "public_task_sha256": sha256_bytes(canonical_json(public_task).encode("utf-8")),
        "registration_template": copy.deepcopy(spec.task["registration_template"]),
        "tool_budget": int(spec.task["registration_template"]["budget"]),
        "requests": [],
        "tool_calls": [],
        "started_utc": utc_now(),
        "json_parse_success": False,
        "outcome": "pending",
    }
    assistant_texts: list[str] = []
    request_index = 0

    def call(messages: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
        nonlocal request_index
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": copy.deepcopy(messages),
            "temperature": float(design["temperature"]),
            "seed": request_seed(base_seed, request_index),
            "max_tokens": int(extra.pop("max_tokens")),
            "n": 1,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
            **extra,
        }
        started = time.monotonic()
        response = client.chat(payload)
        elapsed = time.monotonic() - started
        episode["requests"].append(
            {
                "request_index": request_index,
                "request_seed": payload["seed"],
                "payload": payload,
                "response": response,
                "wall_seconds": elapsed,
            }
        )
        request_index += 1
        text = _assistant_text(response)
        if text:
            assistant_texts.append(text)
        return response

    registration_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _registration_prompt(spec.task)},
    ]
    try:
        registration_response = call(
            registration_messages,
            max_tokens=int(design["registration_max_tokens"]),
            response_format={"type": "json_object"},
        )
    except StudyError as exc:
        episode.update(outcome="api_failure", failure_stage="registration_api", error=str(exc), ended_utc=utc_now())
        return _finalize_episode(episode, assistant_texts)

    registration_content = _assistant_text(registration_response)
    try:
        parsed_registration = strict_json_object(registration_content)
    except (ValueError, json.JSONDecodeError) as exc:
        episode.update(outcome="parse_failure", failure_stage="registration", error=str(exc), ended_utc=utc_now())
        return _finalize_episode(episode, assistant_texts)
    try:
        registration, registration_notes = validate_registration(
            parsed_registration, spec.task["registration_template"]
        )
    except StudyError as exc:
        episode.update(outcome="protocol_failure", failure_stage="registration", error=str(exc), ended_utc=utc_now())
        return _finalize_episode(episode, assistant_texts)
    episode["registration"] = registration
    episode["registration_notes"] = registration_notes

    tool = tool_definition(spec.task)
    messages = [
        *registration_messages,
        {"role": "assistant", "content": registration_content},
        {
            "role": "user",
            "content": _investigation_prompt(registration, tool is not None),
        },
    ]
    final_content: str | None = None
    max_turns = int(episode["tool_budget"]) + 2
    for _ in range(max_turns):
        extra: dict[str, Any] = {
            "max_tokens": int(design["investigation_max_tokens"]),
            "response_format": {"type": "json_object"},
        }
        if tool is not None:
            extra = {
                "max_tokens": int(design["investigation_max_tokens"]),
                "tools": [tool],
                "tool_choice": "auto",
                "parallel_tool_calls": False,
            }
        try:
            response = call(messages, **extra)
        except StudyError as exc:
            episode.update(outcome="api_failure", failure_stage="investigation_api", error=str(exc), ended_utc=utc_now())
            return _finalize_episode(episode, assistant_texts)
        message = _choice_message(response)
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            if len(tool_calls) != 1:
                episode.update(outcome="protocol_failure", failure_stage="tool", error="parallel tool calls are forbidden", ended_utc=utc_now())
                return _finalize_episode(episode, assistant_texts)
            if len(episode["tool_calls"]) >= int(episode["tool_budget"]):
                episode.update(outcome="protocol_failure", failure_stage="tool", error="tool budget exceeded", ended_utc=utc_now())
                return _finalize_episode(episode, assistant_texts)
            call_row = tool_calls[0]
            function = call_row.get("function") if isinstance(call_row, Mapping) else None
            if not isinstance(function, Mapping) or function.get("name") != "simulate":
                episode.update(outcome="protocol_failure", failure_stage="tool", error="unknown tool call", ended_utc=utc_now())
                return _finalize_episode(episode, assistant_texts)
            try:
                arguments = strict_json_object(function.get("arguments"))
                result = execute_tool(alife_module, spec.task, arguments)
            except (ValueError, json.JSONDecodeError, StudyError) as exc:
                episode.update(outcome="protocol_failure", failure_stage="tool", error=str(exc), ended_utc=utc_now())
                return _finalize_episode(episode, assistant_texts)
            tool_id = str(call_row.get("id") or f"tool-{len(episode['tool_calls'])}")
            episode["tool_calls"].append(
                {
                    "tool_call_id": tool_id,
                    "arguments": arguments,
                    "result": result,
                    "cost": 1,
                }
            )
            messages.append(_message_for_history(message))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": "simulate",
                    "content": canonical_json(result),
                }
            )
            continue
        final_content = message.get("content") if isinstance(message.get("content"), str) else ""
        break

    if final_content is None:
        episode.update(outcome="protocol_failure", failure_stage="final", error="model did not finish within tool-turn budget", ended_utc=utc_now())
        return _finalize_episode(episode, assistant_texts)
    try:
        parsed_final = strict_json_object(final_content)
    except (ValueError, json.JSONDecodeError) as exc:
        episode.update(outcome="parse_failure", failure_stage="final", error=str(exc), ended_utc=utc_now())
        return _finalize_episode(episode, assistant_texts)
    episode["json_parse_success"] = True
    try:
        final = validate_final(parsed_final, str(registration["claim_type"]))
    except StudyError as exc:
        episode.update(outcome="protocol_failure", failure_stage="final", error=str(exc), ended_utc=utc_now())
        return _finalize_episode(episode, assistant_texts)

    episode["submission"] = {
        "policy": f"llm:{model_key}:{persona}",
        "registration": registration,
        "investigation_trace": final["investigation_trace"],
        "action": final["action"],
        "claim": final["claim"],
        "cost": len(episode["tool_calls"]),
        "rationale": final["rationale"],
    }
    episode.update(outcome="valid", ended_utc=utc_now())
    return _finalize_episode(episode, assistant_texts)


def _phase_episode_path(results_root: Path, phase: str, model_key: str, persona: str) -> Path:
    if phase == "smoke":
        return results_root / "gates" / f"smoke_episodes_{model_key}_{persona}.jsonl"
    if phase == "full":
        return results_root / "episodes" / f"{model_key}_{persona}.jsonl"
    raise ValueError(f"unknown phase: {phase}")


def run_model_batch(
    *,
    client: OpenAIChatClient,
    alife_module,
    manifest: Mapping[str, Any],
    model_key: str,
    personas: Sequence[str],
    specs: Sequence[TaskSpec],
    samples: int,
    phase: str,
    results_root: str | Path,
) -> dict[str, Any]:
    model = manifest["design"]["models"][model_key]
    root = Path(results_root).expanduser().resolve()
    existing: dict[str, set[str]] = {}
    handles: dict[str, Any] = {}
    try:
        for persona in personas:
            path = _phase_episode_path(root, phase, model_key, persona)
            path.parent.mkdir(parents=True, exist_ok=True)
            rows = read_jsonl(path) if path.is_file() else []
            existing[persona] = {str(row["episode_id"]) for row in rows}
            if len(existing[persona]) != len(rows):
                raise StudyError(f"duplicate episode IDs in resumable batch: {path}")
            handles[persona] = path.open("a", encoding="utf-8", newline="\n")
        completed = 0
        skipped = 0
        consecutive_api_failures = 0
        for spec in specs:
            for sample_index in range(samples):
                for persona in personas:
                    episode_id = f"{phase}:{model_key}:{persona}:{spec.task_id}:sample-{sample_index}"
                    if episode_id in existing[persona]:
                        skipped += 1
                        continue
                    episode = run_model_episode(
                        client=client,
                        alife_module=alife_module,
                        manifest=manifest,
                        model_key=model_key,
                        model_id=str(model["id"]),
                        model_revision=str(model["revision"]),
                        persona=persona,
                        spec=spec,
                        sample_index=sample_index,
                        phase=phase,
                    )
                    handle = handles[persona]
                    handle.write(canonical_json(episode) + "\n")
                    handle.flush()
                    completed += 1
                    if episode["outcome"] == "api_failure":
                        consecutive_api_failures += 1
                    else:
                        consecutive_api_failures = 0
                    if consecutive_api_failures >= 3:
                        raise StudyError("three consecutive API failures; stopping resumable batch")
        return {
            "phase": phase,
            "model_key": model_key,
            "personas": list(personas),
            "tasks": len(specs),
            "samples": samples,
            "episodes_completed": completed,
            "episodes_skipped": skipped,
        }
    finally:
        for handle in handles.values():
            handle.close()


def evaluate_smoke_gate(
    manifest: Mapping[str, Any], *, results_root: str | Path
) -> dict[str, Any]:
    root = Path(results_root).expanduser().resolve()
    smoke = manifest["design"]["smoke"]
    model_key = str(smoke["model"])
    rows_by_persona = {
        persona: read_jsonl(_phase_episode_path(root, "smoke", model_key, persona))
        for persona in PERSONAS
    }
    expected_each = int(smoke["expected_episodes"]) // 2
    errors: list[str] = []
    for persona, rows in rows_by_persona.items():
        if len(rows) != expected_each:
            errors.append(f"{persona} smoke episode count {len(rows)} != {expected_each}")
    all_rows = [row for rows in rows_by_persona.values() for row in rows]
    parse_rate_by_persona = {
        persona: (
            sum(bool(row.get("json_parse_success")) for row in rows) / len(rows)
            if rows
            else 0.0
        )
        for persona, rows in rows_by_persona.items()
    }
    parse_rate = (
        sum(bool(row.get("json_parse_success")) for row in all_rows) / len(all_rows)
        if all_rows
        else 0.0
    )
    density = {
        persona: statistics.mean(float(row.get("whimsy_marker_density", 0.0)) for row in rows)
        if rows
        else 0.0
        for persona, rows in rows_by_persona.items()
    }
    marker_delta = density["fae"] - density["josie"]
    indexed = {
        persona: {
            (str(row["task_id"]), int(row["sample_index"])): row for row in rows
        }
        for persona, rows in rows_by_persona.items()
    }
    pair_keys = sorted(set(indexed["fae"]) & set(indexed["josie"]))
    positive_pairs = sum(
        float(indexed["fae"][key]["whimsy_marker_density"])
        > float(indexed["josie"][key]["whimsy_marker_density"])
        for key in pair_keys
    )
    distinct_pairs = sum(
        indexed["fae"][key].get("assistant_text")
        != indexed["josie"][key].get("assistant_text")
        for key in pair_keys
    )
    for persona, persona_parse_rate in parse_rate_by_persona.items():
        if persona_parse_rate < float(smoke["minimum_parse_rate"]):
            errors.append(f"{persona} smoke JSON parse rate is below threshold")
    if marker_delta < float(smoke["minimum_marker_density_delta"]):
        errors.append("smoke whimsy-marker density delta is below threshold")
    if positive_pairs < int(smoke["minimum_positive_marker_pairs"]):
        errors.append("smoke has too few positive paired marker-density deltas")
    if distinct_pairs == 0:
        errors.append("fae and josie smoke traces are not lexically distinct")
    receipt = {
        "schema": SMOKE_GATE_SCHEMA,
        "status": "passed" if not errors else "failed",
        "checked_utc": utc_now(),
        "model_key": model_key,
        "episode_count": len(all_rows),
        "json_parse_rate": parse_rate,
        "json_parse_rate_by_persona": parse_rate_by_persona,
        "whimsy_marker_density": density,
        "fae_minus_josie_marker_density": marker_delta,
        "paired_trace_count": len(pair_keys),
        "positive_marker_pairs": positive_pairs,
        "lexically_distinct_pairs": distinct_pairs,
        "thresholds": {
            "minimum_parse_rate": smoke["minimum_parse_rate"],
            "minimum_marker_density_delta": smoke["minimum_marker_density_delta"],
            "minimum_positive_marker_pairs": smoke["minimum_positive_marker_pairs"],
        },
        "errors": errors,
    }
    write_json(root / "gates" / "smoke_receipt.json", receipt)
    if errors:
        raise StudyError("SMOKE GATE FAILED: " + "; ".join(errors))
    return receipt


def _mean(values: Sequence[float]) -> float | None:
    return float(statistics.mean(values)) if values else None


def paired_bootstrap(
    values: Sequence[float], *, draws: int, seed: int, confidence_level: float
) -> dict[str, Any]:
    """Deterministically resample paired task deltas with replacement."""

    if not values:
        return {
            "task_count": 0,
            "mean": None,
            "median": None,
            "ci_low": None,
            "ci_high": None,
            "direction_positive_fraction": None,
        }
    array = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(array), size=(draws, len(array)))
    boot = array[indices].mean(axis=1)
    alpha = 1.0 - confidence_level
    return {
        "task_count": len(values),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "ci_low": float(np.quantile(boot, alpha / 2.0)),
        "ci_high": float(np.quantile(boot, 1.0 - alpha / 2.0)),
        "direction_positive_fraction": float(np.mean(array > 0)),
    }


def _grade_episode(alife_module, spec: TaskSpec, episode: Mapping[str, Any]) -> dict[str, Any]:
    expected_episode_hash = sha256_bytes(
        canonical_json(
            {key: value for key, value in episode.items() if key != "episode_sha256"}
        ).encode("utf-8")
    )
    if episode.get("episode_sha256") != expected_episode_hash:
        raise StudyError(f"episode SHA-256 mismatch: {episode.get('episode_id')}")
    expected_public = {key: value for key, value in spec.task.items() if key != "oracle"}
    expected_hash = sha256_bytes(canonical_json(expected_public).encode("utf-8"))
    if episode.get("public_task_sha256") != expected_hash or episode.get("public_task") != expected_public:
        raise StudyError(f"public task receipt mismatch: {episode.get('episode_id')}")
    score: dict[str, Any] | None = None
    if episode.get("outcome") == "valid":
        submission = episode.get("submission")
        if not isinstance(submission, Mapping):
            raise StudyError(f"valid episode lacks submission: {episode.get('episode_id')}")
        # Authoritative scoring import: no copied or altered formula is used here.
        score = dict(alife_module.score_submission(spec.task, submission))
    return {
        "episode_id": episode["episode_id"],
        "model_key": episode["model_key"],
        "model_id": episode["model_id"],
        "model_revision": episode["model_revision"],
        "persona": episode["persona"],
        "split": spec.split,
        "family": spec.family,
        "task_id": spec.task_id,
        "task_seed": spec.task_seed,
        "sample_index": int(episode["sample_index"]),
        "sampling_seed": int(episode["sampling_seed"]),
        "outcome": episode["outcome"],
        "json_parse_success": bool(episode.get("json_parse_success")),
        "whimsy_marker_density": float(episode.get("whimsy_marker_density", 0.0)),
        "tool_call_count": len(episode.get("tool_calls", [])),
        "identifiable_with_budget": bool(spec.task["oracle"]["identifiable_with_budget"]),
        "submission": copy.deepcopy(episode.get("submission")),
        "score": score,
        "source_episode_sha256": episode["episode_sha256"],
    }


def _calibration_bins(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    bins = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0000001)]
    output: list[dict[str, Any]] = []
    for low, high in bins:
        selected = []
        for row in rows:
            submission = row.get("submission")
            if not isinstance(submission, Mapping):
                continue
            registration = submission.get("registration")
            if not isinstance(registration, Mapping):
                continue
            q = registration.get("q_success")
            if isinstance(q, (int, float)) and not isinstance(q, bool) and low <= float(q) < high:
                selected.append(row)
        if selected:
            output.append(
                {
                    "lower": low,
                    "upper": min(high, 1.0),
                    "episodes": len(selected),
                    "mean_forecast": float(
                        statistics.mean(
                            float(row["submission"]["registration"]["q_success"])
                            for row in selected
                        )
                    ),
                    "empirical_identifiable_rate": float(
                        statistics.mean(bool(row["identifiable_with_budget"]) for row in selected)
                    ),
                }
            )
    return output


def _condition_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if isinstance(row.get("score"), Mapping)]
    scores = [float(row["score"]["total_score"]) for row in valid]
    claims_in_hazard_families = [
        row
        for row in valid
        if row["family"] in {"true_null", "structural_unreachability"}
        and row["submission"]["action"] == "claim"
    ]
    false_claims = sum(bool(row["score"]["false_claim"]) for row in claims_in_hazard_families)
    return {
        "episodes": len(rows),
        "valid_graded_episodes": len(valid),
        "parse_rate": sum(bool(row["json_parse_success"]) for row in rows) / len(rows) if rows else 0.0,
        "valid_rate": len(valid) / len(rows) if rows else 0.0,
        "parse_failure_rate": sum(row["outcome"] == "parse_failure" for row in rows) / len(rows) if rows else 0.0,
        "protocol_failure_rate": sum(row["outcome"] == "protocol_failure" for row in rows) / len(rows) if rows else 0.0,
        "api_failure_rate": sum(row["outcome"] == "api_failure" for row in rows) / len(rows) if rows else 0.0,
        "mean_total_score_valid_only": _mean(scores),
        "coverage_adjusted_mean_total_score": sum(scores) / len(rows) if rows else None,
        "mean_registration_brier": _mean(
            [float(row["score"]["registration_brier"]) for row in valid]
        ),
        "avoidable_abstention_rate": (
            sum(bool(row["score"]["avoidable_abstention"]) for row in valid) / len(valid)
            if valid
            else None
        ),
        "false_claim_rate_true_null_and_structural_unreachability": (
            false_claims / len(claims_in_hazard_families)
            if claims_in_hazard_families
            else 0.0
        ),
        "false_claim_numerator": false_claims,
        "false_claim_denominator": len(claims_in_hazard_families),
        "mean_whimsy_marker_density": _mean(
            [float(row["whimsy_marker_density"]) for row in rows]
        ),
        "mean_tool_calls": _mean([float(row["tool_call_count"]) for row in rows]),
        "registration_calibration_bins": _calibration_bins(valid),
    }


def score_full_results(
    manifest: Mapping[str, Any],
    *,
    alife_root: str | Path,
    results_root: str | Path,
    samples: int,
) -> dict[str, Any]:
    """Grade every valid episode with ALife unchanged and analyze paired task effects."""

    root = Path(results_root).expanduser().resolve()
    for gate_name in ("port_gate_diff.json", "smoke_receipt.json"):
        gate = read_json(root / "gates" / gate_name)
        if gate.get("status") != "passed":
            raise StudyError(f"required gate is not passed: {gate_name}")
    alife_module = load_alife_module(alife_root)
    alife_manifest = read_json(Path(alife_root) / str(manifest["alife"]["curriculum_manifest"]))
    specs = build_task_specs(alife_module, alife_manifest)
    spec_by_id = {spec.task_id: spec for spec in specs}
    model_keys = list(manifest["design"]["models"])
    grades: list[dict[str, Any]] = []
    expected_per_condition = len(specs) * samples
    errors: list[str] = []
    for model_key in model_keys:
        for persona in PERSONAS:
            episode_path = _phase_episode_path(root, "full", model_key, persona)
            if not episode_path.is_file():
                errors.append(f"missing episode file: {episode_path.name}")
                continue
            episodes = read_jsonl(episode_path)
            if len(episodes) != expected_per_condition:
                errors.append(
                    f"{model_key}/{persona} episode count {len(episodes)} != {expected_per_condition}"
                )
            condition_grades: list[dict[str, Any]] = []
            seen: set[str] = set()
            for episode in episodes:
                episode_id = str(episode.get("episode_id"))
                if episode_id in seen:
                    errors.append(f"duplicate episode_id: {episode_id}")
                    continue
                seen.add(episode_id)
                spec = spec_by_id.get(str(episode.get("task_id")))
                if spec is None:
                    errors.append(f"unknown task_id: {episode.get('task_id')}")
                    continue
                grade = _grade_episode(alife_module, spec, episode)
                condition_grades.append(grade)
                grades.append(grade)
            grade_path = root / "scores" / "per_task" / f"{model_key}_{persona}.jsonl"
            grade_path.parent.mkdir(parents=True, exist_ok=True)
            with grade_path.open("w", encoding="utf-8", newline="\n") as handle:
                for grade in condition_grades:
                    handle.write(canonical_json(grade) + "\n")
    if errors:
        raise StudyError("full result coverage failed: " + "; ".join(errors[:20]))

    condition_rows: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for grade in grades:
        condition_rows[(grade["model_key"], grade["persona"], grade["split"])].append(grade)
    condition_summary = [
        {
            "model_key": model_key,
            "persona": persona,
            "split": split,
            **_condition_summary(rows),
        }
        for (model_key, persona, split), rows in sorted(condition_rows.items())
    ]

    grade_index = {
        (
            str(row["model_key"]),
            str(row["persona"]),
            str(row["task_id"]),
            int(row["sample_index"]),
        ): row
        for row in grades
    }
    paired_rows: list[dict[str, Any]] = []
    for model_key in model_keys:
        for spec in specs:
            replicate_rows: list[dict[str, Any]] = []
            valid_deltas: list[float] = []
            coverage_deltas: list[float] = []
            for sample_index in range(samples):
                fae = grade_index[(model_key, "fae", spec.task_id, sample_index)]
                josie = grade_index[(model_key, "josie", spec.task_id, sample_index)]
                fae_score = float(fae["score"]["total_score"]) if fae["score"] else None
                josie_score = float(josie["score"]["total_score"]) if josie["score"] else None
                coverage_delta = (fae_score or 0.0) - (josie_score or 0.0)
                coverage_deltas.append(coverage_delta)
                valid_delta = fae_score - josie_score if fae_score is not None and josie_score is not None else None
                if valid_delta is not None:
                    valid_deltas.append(valid_delta)
                replicate_rows.append(
                    {
                        "sample_index": sample_index,
                        "sampling_seed": paired_sampling_seed(
                            manifest, model_key, spec.task_id, sample_index
                        ),
                        "fae_outcome": fae["outcome"],
                        "josie_outcome": josie["outcome"],
                        "fae_total_score": fae_score,
                        "josie_total_score": josie_score,
                        "valid_pair_delta": valid_delta,
                        "coverage_adjusted_delta": coverage_delta,
                    }
                )
            paired_rows.append(
                {
                    "model_key": model_key,
                    "split": spec.split,
                    "family": spec.family,
                    "task_id": spec.task_id,
                    "task_seed": spec.task_seed,
                    "replicates": replicate_rows,
                    "valid_pair_count": len(valid_deltas),
                    "mean_valid_pair_delta": _mean(valid_deltas),
                    "mean_coverage_adjusted_delta": float(statistics.mean(coverage_deltas)),
                }
            )
    paired_path = root / "scores" / "paired_task_deltas.jsonl"
    paired_path.parent.mkdir(parents=True, exist_ok=True)
    with paired_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in paired_rows:
            handle.write(canonical_json(row) + "\n")

    analysis = manifest["analysis"]
    bootstrap_receipts: dict[str, Any] = {
        "draws": analysis["bootstrap_draws"],
        "seed": analysis["bootstrap_seed"],
        "confidence_level": analysis["confidence_level"],
        "unit": "one frozen holdout task after averaging sampling replicates",
        "models": {},
    }
    for model_index, model_key in enumerate(model_keys):
        holdout = [
            row for row in paired_rows if row["model_key"] == model_key and row["split"] == "holdout"
        ]
        coverage_values = [float(row["mean_coverage_adjusted_delta"]) for row in holdout]
        valid_values = [
            float(row["mean_valid_pair_delta"])
            for row in holdout
            if row["mean_valid_pair_delta"] is not None
        ]
        bootstrap_receipts["models"][model_key] = {
            "coverage_adjusted": paired_bootstrap(
                coverage_values,
                draws=int(analysis["bootstrap_draws"]),
                seed=int(analysis["bootstrap_seed"]) + model_index,
                confidence_level=float(analysis["confidence_level"]),
            ),
            "valid_pairs_only": paired_bootstrap(
                valid_values,
                draws=int(analysis["bootstrap_draws"]),
                seed=int(analysis["bootstrap_seed"]) + 100 + model_index,
                confidence_level=float(analysis["confidence_level"]),
            ),
            "task_delta_sha256": sha256_bytes(canonical_json(holdout).encode("utf-8")),
        }
    write_json(root / "scores" / "bootstrap_receipts.json", bootstrap_receipts)

    holdout_comparisons = []
    references = dict(manifest["alife"]["reference_holdout_scores"])
    for row in condition_summary:
        if row["split"] != "holdout":
            continue
        observed = row["coverage_adjusted_mean_total_score"]
        holdout_comparisons.append(
            {
                "model_key": row["model_key"],
                "persona": row["persona"],
                "coverage_adjusted_mean_total_score": observed,
                "minus_always_abstain": observed - references["always_abstain"],
                "minus_proxy_claimant": observed - references["proxy_claimant"],
                "minus_calibrated_investigator": observed - references["calibrated_investigator"],
            }
        )
    expected_total = len(specs) * len(model_keys) * len(PERSONAS) * samples
    summary = {
        "schema": SCORE_SUMMARY_SCHEMA,
        "status": "ok",
        "scoring_function": "ALife src/discovery_curriculum.py::score_submission unchanged",
        "episode_count": len(grades),
        "expected_episode_count": expected_total,
        "samples_per_task": samples,
        "reference_holdout_scores": references,
        "condition_summary": condition_summary,
        "holdout_reference_comparisons": holdout_comparisons,
        "paired_bootstrap": bootstrap_receipts,
        "parse_rate_by_model": {
            model_key: sum(
                bool(row["json_parse_success"]) for row in grades if row["model_key"] == model_key
            )
            / sum(1 for row in grades if row["model_key"] == model_key)
            for model_key in model_keys
        },
        "claim_boundary": (
            "This is a model-only paired prompt intervention on a frozen synthetic curriculum. "
            "It does not establish a general cognitive or real-world epistemic effect."
        ),
    }
    write_json(root / "scores" / "summary.json", summary)
    (root / "KNOWLEDGE_CARD.md").write_text(
        build_study_knowledge_card(summary), encoding="utf-8"
    )
    return summary


def build_study_knowledge_card(summary: Mapping[str, Any]) -> str:
    bootstrap = {
        model: value["coverage_adjusted"]
        for model, value in summary["paired_bootstrap"]["models"].items()
    }
    holdout = [
        row for row in summary["condition_summary"] if row["split"] == "holdout"
    ]
    holdout_lines = [
        "| Model | Persona | Coverage score | Parse rate | False-claim rate | Avoidable abstention | Registration Brier |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in holdout:
        values = [
            row["coverage_adjusted_mean_total_score"],
            row["parse_rate"],
            row["false_claim_rate_true_null_and_structural_unreachability"],
            row["avoidable_abstention_rate"],
            row["mean_registration_brier"],
        ]
        rendered = ["n/a" if value is None else f"{float(value):.6f}" for value in values]
        holdout_lines.append(
            f"| {row['model_key']} | {row['persona']} | " + " | ".join(rendered) + " |"
        )
    holdout_table = "\n".join(holdout_lines)
    return f"""# Fae Tax on Epistemics — Knowledge Card

## Observed

- Scored/categorized episodes: {summary['episode_count']} of {summary['expected_episode_count']}.
- Frozen reference holdout scores: {json.dumps(summary['reference_holdout_scores'], sort_keys=True)}.
- Paired holdout fae-minus-josie task bootstrap: {json.dumps(bootstrap, sort_keys=True)}.
- Parse rate by model: {json.dumps(summary['parse_rate_by_model'], sort_keys=True)}.

### Holdout condition audit

{holdout_table}

## Inferred

The paired intervals quantify the effect of the frozen fae system prompt relative to the neutral josie prompt within each model and task suite. Direction and magnitude are reported without a fixed significance or product gate.

## Not Supported

- No claim about human, biological, or universal epistemics.
- No claim that whimsy generally causes the measured effect outside these model snapshots and synthetic tasks.
- Parse and protocol failures remain their own categories; they were not reinterpreted as abstentions.

## Robustness

The same frozen tasks, sampling seeds, tool budgets, temperature, parser, and unchanged ALife scorer are used for both personas across all three model sizes.

## Confounds

System-prompt wording changes both style and task framing. Shared seeds do not create identical token-level counterfactual noise after prompts diverge. The lexical marker gate measures treatment exposure, not semantic persona depth.

## Artifacts

See `MANIFEST.md`, `episodes/`, `scores/`, `gates/`, `config/`, and the bundle SHA-256 sidecar.
"""


def write_seed_manifest(
    manifest: Mapping[str, Any],
    *,
    alife_root: str | Path,
    results_root: str | Path,
    samples: int,
) -> dict[str, Any]:
    """Record every frozen task and paired model-sampling seed used by the run."""

    alife_module = load_alife_module(alife_root)
    alife_manifest = read_json(
        Path(alife_root) / str(manifest["alife"]["curriculum_manifest"])
    )
    tasks = build_task_specs(alife_module, alife_manifest)
    rows = [
        {
            "model_key": model_key,
            "task_id": spec.task_id,
            "split": spec.split,
            "family": spec.family,
            "task_seed": spec.task_seed,
            "sample_index": sample_index,
            "paired_sampling_seed": paired_sampling_seed(
                manifest, model_key, spec.task_id, sample_index
            ),
        }
        for model_key in manifest["design"]["models"]
        for spec in tasks
        for sample_index in range(samples)
    ]
    receipt = {
        "schema": "pixieology.fae_tax_epistemics.seed_manifest.v1",
        "pairing": (
            "Each row's sampling seed is used for both fae and josie. Request-stage "
            "seeds are request_seed(paired_sampling_seed, request_index)."
        ),
        "samples_per_task": samples,
        "task_count": len(tasks),
        "model_count": len(manifest["design"]["models"]),
        "row_count": len(rows),
        "rows_sha256": sha256_bytes(canonical_json(rows).encode("utf-8")),
        "rows": rows,
    }
    write_json(Path(results_root) / "config" / "seed_manifest.json", receipt)
    return receipt


def snapshot_run_config(
    manifest_path: str | Path,
    *,
    results_root: str | Path,
    alife_root: str | Path,
    effective_samples: int,
    endpoint: str | None = None,
    provider: str | None = None,
    estimated_provider_cost_usd: float | None = None,
) -> dict[str, Any]:
    root = Path(results_root).expanduser().resolve()
    manifest_file = Path(manifest_path).expanduser().resolve()
    alife = Path(alife_root).expanduser().resolve()
    frozen = root / "config" / "frozen_study_manifest.json"
    frozen.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_file, frozen)
    pixieology_root = Path(__file__).resolve().parent
    code_paths = [
        Path(__file__).resolve(),
        pixieology_root / "run_fae_tax_epistemics.py",
        pixieology_root / "fae_bench" / "scoring.py",
        pixieology_root / "experiments" / "fae_tax_epistemics_v1" / "run_single_a100.sh",
        pixieology_root / "experiments" / "fae_tax_epistemics_v1" / "run_single_a100.sbatch",
        pixieology_root / "experiments" / "fae_tax_epistemics_v1" / "stage_pod_source.py",
        pixieology_root / "experiments" / "fae_tax_epistemics_v1" / "prime_windows_compat.py",
        pixieology_root / "experiments" / "fae_tax_epistemics_v1" / "prime_pod_gate.py",
        pixieology_root / "experiments" / "fae_tax_epistemics_v1" / "README.md",
    ]
    previous_path = root / "config" / "run_config.json"
    previous = read_json(previous_path) if previous_path.is_file() else {}
    previous_runtime = previous.get("runtime") if isinstance(previous.get("runtime"), Mapping) else {}
    pixieology_status = _git_value(pixieology_root, "status", "--porcelain")
    previous_commands = previous.get("command_history", [])
    if not isinstance(previous_commands, list):
        previous_commands = []
    command_history = [
        *previous_commands,
        {"recorded_utc": utc_now(), "argv": list(sys.argv)},
    ]
    runtime_provider = provider if provider is not None else previous_runtime.get("provider", "unknown")
    runtime_cost = (
        estimated_provider_cost_usd
        if estimated_provider_cost_usd is not None
        else previous_runtime.get("estimated_provider_cost_usd", 0.0)
    )
    alife_code_paths = [
        alife / "src" / "discovery_curriculum.py",
        alife / str(load_study_manifest(manifest_file)["alife"]["curriculum_manifest"]),
    ]
    snapshot = {
        "schema": "pixieology.fae_tax_epistemics.run_config.v1",
        "recorded_utc": utc_now(),
        "study_manifest_sha256": sha256_file(manifest_file),
        "alife_commit": _git_value(alife, "rev-parse", "HEAD"),
        "alife_dirty": bool(_git_value(alife, "status", "--porcelain")),
        "pixieology_commit": _git_value(pixieology_root, "rev-parse", "HEAD"),
        "pixieology_dirty": None if pixieology_status is None else bool(pixieology_status),
        "code_hashes": {
            path.relative_to(pixieology_root).as_posix(): sha256_file(path)
            for path in code_paths
            if path.is_file()
        },
        "alife_code_hashes": {
            path.relative_to(alife).as_posix(): sha256_file(path)
            for path in alife_code_paths
            if path.is_file()
        },
        "models": load_study_manifest(manifest_file)["design"]["models"],
        "sampling": {
            "effective_samples_per_task": effective_samples,
            "temperature": load_study_manifest(manifest_file)["design"]["temperature"],
            "enable_thinking": False,
        },
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "endpoint": endpoint if endpoint is not None else previous_runtime.get("endpoint"),
            "provider": runtime_provider,
            "estimated_provider_cost_usd": runtime_cost,
        },
        "command_history": command_history,
    }
    write_json(root / "config" / "run_config.json", snapshot)
    return snapshot


def record_budget_gate(
    manifest: Mapping[str, Any],
    *,
    results_root: str | Path,
    provider: str,
    pod_started_epoch_seconds: float,
    pod_hourly_usd: float,
    projected_remaining_seconds: float,
    stage: str,
    selected_samples: int | None = None,
    observed_seconds_per_episode: float | None = None,
    now_epoch_seconds: float | None = None,
) -> dict[str, Any]:
    """Record and enforce the declared wall-time and provider-cost ceilings.

    The receipt is deliberately based on pod lifetime, not model-serving time,
    so setup, downloads, scoring, and failures remain charged. A paid provider
    must supply a positive hourly rate; zero-cost placeholders are rejected.
    """

    root = Path(results_root).expanduser().resolve()
    now = time.time() if now_epoch_seconds is None else float(now_epoch_seconds)
    started = float(pod_started_epoch_seconds)
    hourly = float(pod_hourly_usd)
    remaining = float(projected_remaining_seconds)
    elapsed = max(0.0, now - started)
    projected_total_seconds = elapsed + max(0.0, remaining)
    budget = manifest["budget"]
    max_cost = float(budget["max_provider_cost_usd"])
    max_wall = float(budget["max_wall_seconds"])
    max_gpu_seconds = float(budget["max_gpu_hours"]) * 3600.0
    errors: list[str] = []
    if started <= 0.0 or started > now:
        errors.append("pod start epoch must be positive and no later than the current time")
    if hourly < 0.0:
        errors.append("pod hourly price cannot be negative")
    if provider not in FREE_PROVIDERS and hourly <= 0.0:
        errors.append("paid/remote providers require a positive POD_HOURLY_USD")
    if remaining < 0.0:
        errors.append("projected remaining seconds cannot be negative")
    if projected_total_seconds > max_wall:
        errors.append("projected pod lifetime exceeds max_wall_seconds")
    if projected_total_seconds > max_gpu_seconds:
        errors.append("projected pod lifetime exceeds max_gpu_hours")
    elapsed_cost = elapsed * hourly / 3600.0
    projected_cost = projected_total_seconds * hourly / 3600.0
    if projected_cost > max_cost:
        errors.append("projected provider cost exceeds max_provider_cost_usd")
    allowed_samples = {
        int(manifest["design"]["samples_per_task"]),
        int(manifest["design"]["cost_fallback_samples_per_task"]),
    }
    if selected_samples is not None and int(selected_samples) not in allowed_samples:
        errors.append(f"selected samples must be one of {sorted(allowed_samples)}")
    if observed_seconds_per_episode is not None and observed_seconds_per_episode <= 0.0:
        errors.append("observed seconds per episode must be positive when supplied")
    if stage == "final" and remaining != 0.0:
        errors.append("final budget receipt must have zero projected remaining seconds")

    receipt = {
        "schema": BUDGET_GATE_SCHEMA,
        "status": "passed" if not errors else "failed",
        "checked_utc": utc_now(),
        "stage": stage,
        "provider": provider,
        "pod_started_epoch_seconds": started,
        "pod_hourly_usd": hourly,
        "elapsed_seconds": elapsed,
        "projected_remaining_seconds": remaining,
        "projected_total_seconds": projected_total_seconds,
        "elapsed_provider_cost_usd": elapsed_cost,
        "projected_provider_cost_usd": projected_cost,
        "selected_samples": selected_samples,
        "observed_seconds_per_episode": observed_seconds_per_episode,
        "limits": {
            "max_provider_cost_usd": max_cost,
            "max_wall_seconds": max_wall,
            "max_gpu_hours": float(budget["max_gpu_hours"]),
        },
        "errors": errors,
    }
    write_json(root / "gates" / "budget_receipt.json", receipt)
    history_path = root / "gates" / "budget_history.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(receipt) + "\n")

    run_config_path = root / "config" / "run_config.json"
    if run_config_path.is_file():
        run_config = read_json(run_config_path)
        runtime = run_config.setdefault("runtime", {})
        runtime["provider"] = provider
        runtime["pod_hourly_usd"] = hourly
        runtime["elapsed_provider_cost_usd"] = elapsed_cost
        runtime["estimated_provider_cost_usd"] = projected_cost
        runtime["budget_stage"] = stage
        write_json(run_config_path, run_config)
    if errors:
        raise StudyError("BUDGET GATE FAILED: " + "; ".join(errors))
    return receipt


def _bundle_files(root: Path) -> list[Path]:
    allowed_roots = {"episodes", "scores", "gates", "config"}
    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and (path.relative_to(root).parts[0] in allowed_roots or path.name == "KNOWLEDGE_CARD.md")
    ]
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def build_results_bundle(
    manifest: Mapping[str, Any],
    *,
    results_root: str | Path,
    destination: str | Path | None = None,
) -> Path:
    root = Path(results_root).expanduser().resolve()
    for gate_name in ("port_gate_diff.json", "smoke_receipt.json", "budget_receipt.json"):
        if read_json(root / "gates" / gate_name).get("status") != "passed":
            raise StudyError(f"cannot bundle failed gate: {gate_name}")
    summary = read_json(root / "scores" / "summary.json")
    if summary.get("status") != "ok" or summary.get("episode_count") != summary.get("expected_episode_count"):
        raise StudyError("cannot bundle incomplete scored episodes")
    run_config = read_json(root / "config" / "run_config.json")
    budget_receipt = read_json(root / "gates" / "budget_receipt.json")
    if budget_receipt.get("stage") != "final":
        raise StudyError("cannot bundle without a final budget receipt")
    if int(budget_receipt.get("selected_samples", -1)) != int(summary["samples_per_task"]):
        raise StudyError("budget receipt sample count does not match scored results")
    if float(run_config["runtime"].get("estimated_provider_cost_usd", 0.0)) > float(
        manifest["budget"]["max_provider_cost_usd"]
    ):
        raise StudyError("cannot bundle a run above the declared provider-cost cap")
    if float(budget_receipt.get("projected_provider_cost_usd", math.inf)) > float(
        manifest["budget"]["max_provider_cost_usd"]
    ):
        raise StudyError("cannot bundle a run above the authoritative budget receipt")

    files = _bundle_files(root)
    lines = [
        "# Fae Tax on Epistemics Results Manifest",
        "",
        f"Schema: `{BUNDLE_MANIFEST_SCHEMA}`",
        f"Episodes scored/categorized: {summary['episode_count']}",
        f"Effective samples per task: {summary['samples_per_task']}",
        "",
        "Each line below is `sha256  bytes  relative_path`.",
        "",
    ]
    for path in files:
        relative = path.relative_to(root).as_posix()
        lines.append(f"{sha256_file(path)}  {path.stat().st_size}  {relative}")
    manifest_path = root / "MANIFEST.md"
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    files.append(manifest_path)

    output = (
        Path(destination).expanduser().resolve()
        if destination is not None
        else root.parent / f"fae_tax_results_{date.today().strftime('%Y%m%d')}.zip"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite results bundle: {output}")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
            archive.write(path, path.relative_to(root).as_posix())
    digest = sha256_file(output)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="utf-8"
    )
    verify_results_bundle(output)
    return output


def verify_results_bundle(path: str | Path) -> dict[str, Any]:
    bundle = Path(path).expanduser().resolve()
    errors: list[str] = []
    with zipfile.ZipFile(bundle, "r") as archive:
        bad = archive.testzip()
        if bad:
            errors.append(f"zip CRC failed: {bad}")
        names = archive.namelist()
        if len(names) != len(set(names)):
            errors.append("duplicate zip member")
        required_prefixes = ("episodes/", "scores/", "gates/", "config/")
        for prefix in required_prefixes:
            if not any(name.startswith(prefix) for name in names):
                errors.append(f"missing bundle prefix: {prefix}")
        if "MANIFEST.md" not in names:
            errors.append("missing MANIFEST.md")
            manifest_text = ""
        else:
            manifest_text = archive.read("MANIFEST.md").decode("utf-8")
        receipt_re = re.compile(r"^([0-9a-f]{64})  ([0-9]+)  (.+)$")
        checked = 0
        receipted_names: set[str] = set()
        for line in manifest_text.splitlines():
            match = receipt_re.match(line)
            if not match:
                continue
            expected_hash, expected_bytes, name = match.groups()
            if name not in names:
                errors.append(f"manifest member missing: {name}")
                continue
            payload = archive.read(name)
            if len(payload) != int(expected_bytes):
                errors.append(f"manifest byte mismatch: {name}")
            if sha256_bytes(payload) != expected_hash:
                errors.append(f"manifest SHA-256 mismatch: {name}")
            checked += 1
            receipted_names.add(name)
        if checked == 0:
            errors.append("MANIFEST.md contains no file receipts")
        unreceipted = sorted(set(names) - {"MANIFEST.md"} - receipted_names)
        if unreceipted:
            errors.append(f"unreceipted zip members: {unreceipted[:10]}")
    sidecar = bundle.with_suffix(bundle.suffix + ".sha256")
    if not sidecar.is_file() or sha256_file(bundle) not in sidecar.read_text(encoding="utf-8"):
        errors.append("bundle SHA-256 sidecar is missing or invalid")
    receipt = {
        "schema": BUNDLE_MANIFEST_SCHEMA,
        "status": "passed" if not errors else "failed",
        "bundle": bundle.name,
        "bundle_sha256": sha256_file(bundle),
        "manifest_files_checked": checked,
        "errors": errors,
    }
    if errors:
        raise StudyError("bundle verification failed: " + "; ".join(errors))
    return receipt
