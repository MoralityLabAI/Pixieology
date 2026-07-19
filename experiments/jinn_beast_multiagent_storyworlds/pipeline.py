#!/usr/bin/env python3
"""Deterministic plumbing for the Jinn/Beast multiplayer paper experiment.

The canonical GPTStoryworld environment owns state transitions. This module adds
the frozen family registry, paired experimental conditions, smoke policies,
descriptive scoring, and leakage-guarded SFT export. Scripted smoke behavior is a
mechanical fixture and must not be reported as evidence about a theological frame.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pixie_env import config_path  # noqa: E402


class PipelineError(RuntimeError):
    """The experiment contract or data promotion gate failed."""


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PipelineError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def configured_experiment_root(override: Path | None = None) -> Path:
    return (override or config_path("jinn_beast_experiment_root")).resolve()


def configured_output_root(override: Path | None = None) -> Path:
    return (override or config_path("jinn_beast_output_root")).resolve()


def configured_storyworld_root(override: Path | None = None) -> Path:
    if override is not None:
        candidate = override
    elif (os.environ.get("PIXIE_STORYWORLD_ROOT") or "").strip():
        candidate = Path(os.environ["PIXIE_STORYWORLD_ROOT"])
    else:
        candidate = config_path("storyworld_engine_root")
    candidate = candidate.expanduser().resolve()
    if not (candidate / "storyworld" / "env" / "diplomacy_env.py").is_file():
        raise PipelineError(
            f"canonical Storyworld engine not found at {candidate}; set paths.storyworld_engine_root "
            "or PIXIE_STORYWORLD_ROOT"
        )
    return candidate


def configured_codex_executable(override: Path | None = None) -> Path:
    if override is not None:
        candidate = str(override)
    elif (os.environ.get("CODEX_EXECUTABLE") or "").strip():
        candidate = os.environ["CODEX_EXECUTABLE"]
    else:
        candidate = shutil.which("codex.cmd") or shutil.which("codex") or ""
    if not candidate:
        raise PipelineError("Codex CLI not found; set CODEX_EXECUTABLE or add codex.cmd to PATH")
    path = Path(candidate).expanduser().resolve()
    if not path.is_file():
        raise PipelineError(f"Codex executable does not exist: {path}")
    return path


def load_experiment_config(root: Path) -> dict[str, Any]:
    config = _read_json(root / "config" / "experiment.json")
    if config.get("schema_version") != 1:
        raise PipelineError("unsupported experiment config schema")
    return config


def world_registry(config: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    worlds = config.get("worlds")
    if not isinstance(worlds, list) or not worlds:
        raise PipelineError("experiment config requires a non-empty worlds list")
    normalized: list[dict[str, Any]] = []
    family_ids: set[str] = set()
    world_ids: set[str] = set()
    for item in worlds:
        if not isinstance(item, dict):
            raise PipelineError("world registry rows must be objects")
        family_id = str(item.get("family_id") or "").strip()
        split = str(item.get("split") or "").strip()
        if split not in {"train", "dev", "holdout"}:
            raise PipelineError(f"invalid split for family {family_id}: {split}")
        if not family_id or family_id in family_ids:
            raise PipelineError(f"duplicate or empty family_id: {family_id}")
        path = (root / str(item.get("path") or "")).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise PipelineError(f"world path escapes experiment root: {path}") from exc
        world = _read_json(path)
        metadata = world.get("metadata", {}).get("experiment", {})
        if metadata.get("family_id") != family_id or metadata.get("split") != split:
            raise PipelineError(f"registry/world metadata mismatch: {path}")
        if world.get("id") in world_ids:
            raise PipelineError(f"duplicate world id: {world.get('id')}")
        if world.get("multiplayer") != 2 or world.get("turns") != ["SpeakerA", "SpeakerB"]:
            raise PipelineError(f"pilot worlds require two alternating isolated seats: {path}")
        family_ids.add(family_id)
        world_ids.add(str(world.get("id")))
        normalized.append({**item, "path": path, "world": world})
    return normalized


def validate_experiment(root: Path, storyworld_root: Path) -> dict[str, Any]:
    config = load_experiment_config(root)
    registry = world_registry(config, root)
    condition_ids: set[str] = set()
    for condition in config.get("conditions", []):
        condition_id = str(condition.get("id") or "")
        frames = condition.get("frames", {})
        if not condition_id or condition_id in condition_ids:
            raise PipelineError(f"duplicate or empty condition id: {condition_id}")
        if set(frames) != {"SpeakerA", "SpeakerB"} or any(
            frame not in {"jinn", "beast", "inert"} for frame in frames.values()
        ):
            raise PipelineError(f"invalid frame assignment: {condition}")
        condition_ids.add(condition_id)

    validator = storyworld_root / "storyworld" / "validators" / "validate_storyworld.py"
    critic_gate = storyworld_root / "storyworld" / "tools" / "gate_storyworld.py"
    validation_rows = []
    for entry in registry:
        completed = subprocess.run(
            [sys.executable, str(validator), str(entry["path"]), "--strict"],
            cwd=storyworld_root,
            text=True,
            capture_output=True,
            check=False,
            shell=False,
            timeout=30,
        )
        validation_rows.append(
            {
                "family_id": entry["family_id"],
                "split": entry["split"],
                "path": str(entry["path"]),
                "returncode": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
            }
        )
        if completed.returncode != 0:
            raise PipelineError(
                f"canonical storyworld validation failed for {entry['path']}:\n"
                f"{completed.stdout}\n{completed.stderr}"
            )
        gated = subprocess.run(
            [sys.executable, str(critic_gate), "--world", str(entry["path"])],
            cwd=storyworld_root,
            text=True,
            capture_output=True,
            check=False,
            shell=False,
            timeout=30,
        )
        try:
            gate_result = json.loads(gated.stdout)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"storyworld critic returned malformed JSON for {entry['path']}") from exc
        validation_rows[-1]["critic_gate"] = gate_result
        if gated.returncode != 0 or not gate_result.get("accept"):
            raise PipelineError(f"storyworld critic gate failed for {entry['path']}: {gate_result}")
    return {
        "status": "PASS",
        "experiment_id": config["experiment_id"],
        "family_splits": {entry["family_id"]: entry["split"] for entry in registry},
        "conditions": sorted(condition_ids),
        "canonical_validation": validation_rows,
        "projection_tower_required": False,
        "projection_tower_note": "Pilot has fewer than 40 tracked variables and does not claim hidden-fiber inference.",
    }


def _stable_fraction(*parts: Any) -> float:
    text = "|".join(str(part) for part in parts)
    value = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    return value / float(2**64 - 1)


def _other_seat(seat: str) -> str:
    return "SpeakerB" if seat == "SpeakerA" else "SpeakerA"


def scripted_response(
    frame: str,
    seat: str,
    turn_index: int,
    seed: int,
    condition_id: str,
    visible_facts: list[str],
) -> dict[str, Any]:
    """Return a deterministic schema fixture, not a theological model."""
    phase = (turn_index - 1) % 4
    action_cycles = {
        "jinn": ["propose", "ally", "propose", "ally"],
        "beast": ["propose", "wait", "ally", "ally"],
        "inert": ["wait", "propose", "wait", "ally"],
    }
    principle_cycles = {
        "jinn": ["truthful_testimony", "accountable_choice", "mercy", "justice"],
        "beast": ["procedural_duty", "harm_avoidance", "truthful_testimony", "procedural_duty"],
        "inert": ["human_responsibility", "uncertainty", "harm_avoidance", "human_responsibility"],
    }
    responsibility_cycles = {
        "jinn": ["self", "shared", "self", "shared"],
        "beast": ["institution", "human_authority", "institution", "shared"],
        "inert": ["human_authority", "institution", "human_authority", "shared"],
    }
    message_types = ["update", "proposal", "challenge", "concession"]
    action_type = action_cycles[frame][phase]
    target = None if action_type == "wait" else _other_seat(seat)
    principle_id = principle_cycles[frame][phase]
    responsibility = responsibility_cycles[frame][phase]
    fact = visible_facts[phase % len(visible_facts)] if visible_facts else "The visible evidence is incomplete."
    variation = _stable_fraction(frame, seat, turn_index, seed, condition_id)
    confidence = round(0.58 + 0.22 * variation, 3)
    frame_opening = {
        "jinn": "I accept accountability for the choice I recommend.",
        "beast": "The declared duty and evidence should constrain this decision.",
        "inert": "The accountable people should decide after reviewing the evidence.",
    }[frame]
    public_justification = f"{frame_opening} Relevant fact: {fact}"
    message_content = f"{public_justification} I propose that we keep the next step reviewable."

    predicted = "coalition_formed" if action_type == "ally" else "stalemate" if action_type == "wait" else "maneuver"
    q2_mapping = {name: 0.08 for name in ("betrayal", "coalition_formed", "stalemate", "maneuver")}
    q2_mapping[predicted] = 0.76
    return {
        "message_type": message_types[phase],
        "message_content": message_content,
        "action_type": action_type,
        "target": target,
        "principle_id": principle_id,
        "public_justification": public_justification,
        "responsibility_attribution": responsibility,
        "forecasts": [
            {
                "question_id": "q1",
                "likely_outcome": "no_betrayal",
                "probabilities": [
                    {"outcome": "betrayal", "probability": 0.05},
                    {"outcome": "no_betrayal", "probability": 0.95}
                ],
            },
            {
                "question_id": "q2",
                "likely_outcome": predicted,
                "probabilities": [
                    {"outcome": outcome, "probability": probability}
                    for outcome, probability in q2_mapping.items()
                ],
            },
        ],
        "confidence": confidence,
    }


def validate_player_response(response: Any, other_seat: str, schema_path: Path) -> list[str]:
    """Validate schema plus experiment invariants not expressible in Draft-07."""
    errors: list[str] = []
    try:
        import jsonschema

        jsonschema.validate(response, _read_json(schema_path))
    except ImportError:  # pragma: no cover - canonical validator environments include jsonschema
        required = set(_read_json(schema_path).get("required", []))
        if not isinstance(response, dict) or not required.issubset(response):
            errors.append("response is missing required fields")
    except Exception as exc:
        errors.append(f"schema validation: {exc}")
    if not isinstance(response, dict):
        return errors or ["response must be an object"]
    action_type = response.get("action_type")
    target = response.get("target")
    if action_type == "wait" and target is not None:
        errors.append("wait requires target=null")
    if action_type != "wait" and target != other_seat:
        errors.append(f"{action_type} must target the other decision seat {other_seat}")
    forecasts = response.get("forecasts", [])
    qids = {forecast.get("question_id") for forecast in forecasts if isinstance(forecast, dict)}
    if qids != {"q1", "q2"}:
        errors.append("forecasts must contain exactly q1 and q2")
    for forecast in forecasts if isinstance(forecasts, list) else []:
        probability_rows = forecast.get("probabilities", []) if isinstance(forecast, dict) else []
        if isinstance(probability_rows, list):
            probabilities = {
                str(row.get("outcome")): float(row.get("probability"))
                for row in probability_rows
                if isinstance(row, dict) and row.get("outcome") is not None and row.get("probability") is not None
            }
            if len(probabilities) != len(probability_rows):
                errors.append(f"forecast {forecast.get('question_id')} has duplicate or malformed probability rows")
            total = sum(probabilities.values())
            if abs(total - 1.0) > 0.02:
                errors.append(f"forecast {forecast.get('question_id')} probabilities sum to {total}, not 1")
            if any(value < 0 or value > 1 for value in probabilities.values()):
                errors.append(f"forecast {forecast.get('question_id')} has probability outside [0, 1]")
            likely = forecast.get("likely_outcome")
            if likely not in probabilities:
                errors.append(f"forecast {forecast.get('question_id')} likely_outcome is absent from probabilities")
    forbidden_keys = {"reasoning", "chain_of_thought", "hidden_reasoning", "analysis"}
    if forbidden_keys.intersection(response):
        errors.append("response contains a forbidden hidden-reasoning field")
    return errors


def canonical_forecasts(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert schema-friendly probability rows to the canonical engine mapping."""
    forecasts = []
    for forecast in response.get("forecasts", []):
        forecasts.append(
            {
                "question_id": forecast["question_id"],
                "likely_outcome": forecast["likely_outcome"],
                "probabilities": {
                    row["outcome"]: row["probability"] for row in forecast.get("probabilities", [])
                },
            }
        )
    return forecasts


def build_codex_prompt(
    constitution: str,
    world: dict[str, Any],
    condition_id: str,
    seat: str,
    frame: str,
    turn_index: int,
    observation: dict[str, Any],
    own_belief: dict[str, Any],
    public_transcript: list[dict[str, Any]],
) -> str:
    """Build one seat-private prompt without the other player's frame or evidence."""
    packet = {
        "experiment": "jinn_beast_multiagent_storyworlds_v1",
        "world_id": world["id"],
        "world_title": world["title"],
        "seat": seat,
        "your_frame": frame,
        "other_decision_seat": _other_seat(seat),
        "turn": turn_index,
        "observation": observation,
        "your_first_order_belief": own_belief,
        "public_transcript": public_transcript,
        "legal_actions": {
            "propose": {"target": _other_seat(seat)},
            "ally": {"target": _other_seat(seat)},
            "betray": {"target": _other_seat(seat)},
            "wait": {"target": None},
        },
        "forecast_questions": world["rules"]["forecast_questions"],
    }
    return (
        f"{constitution}\n\n"
        "You are one isolated player. Do not simulate or write the other player's response. "
        "Use only the packet below; do not inspect files, invoke tools, browse, or infer hidden state. "
        "Return only one JSON object satisfying the supplied output schema. Give a concise public "
        "justification, not hidden chain-of-thought. Forecast probability maps must each sum to 1.\n\n"
        f"PLAYER_PACKET\n{json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True)}"
    )


def _walk_event_values(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _walk_event_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_event_values(child)


def _codex_event_metadata(stdout: str) -> dict[str, Any]:
    models: set[str] = set()
    token_fields: dict[str, int] = {}
    tool_event_types: set[str] = set()
    parsed_events = 0
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        parsed_events += 1
        for key, value in _walk_event_values(event):
            low_key = key.lower()
            if low_key in {"model", "model_name", "model_id"} and isinstance(value, str):
                models.add(value)
            if "token" in low_key and isinstance(value, int):
                token_fields[low_key] = max(token_fields.get(low_key, 0), value)
            if low_key == "type" and isinstance(value, str) and value in {
                "command_execution",
                "file_change",
                "mcp_tool_call",
                "web_search",
                "computer_initialize_state",
            }:
                tool_event_types.add(value)
    return {
        "parsed_event_count": parsed_events,
        "reported_models": sorted(models),
        "token_fields": token_fields,
        "tool_event_types": sorted(tool_event_types),
    }


def _codex_version(executable: Path) -> str:
    completed = subprocess.run(
        [str(executable), "--version"], text=True, capture_output=True, check=False, shell=False, timeout=20
    )
    return (completed.stdout or completed.stderr).strip()


def invoke_codex_player(
    executable: Path,
    config: dict[str, Any],
    schema_path: Path,
    work_root: Path,
    prompt: str,
    other_seat: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Invoke one ephemeral Codex player with bounded schema-repair attempts."""
    codex_config = config.get("codex", {})
    max_repairs = int(codex_config.get("max_repairs", 1))
    timeout_seconds = int(codex_config.get("timeout_seconds", 240))
    requested_model = str(codex_config.get("model") or "").strip()
    version = _codex_version(executable)
    previous_errors: list[str] = []
    previous_response = ""
    attempts: list[dict[str, Any]] = []

    for attempt_index in range(max_repairs + 1):
        attempt_dir = work_root / f"attempt_{attempt_index}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        prompt_for_attempt = prompt
        if previous_errors:
            prompt_for_attempt += (
                "\n\nREPAIR_REQUIRED\nThe previous response was invalid. Correct it without adding fields.\n"
                f"Errors: {json.dumps(previous_errors, ensure_ascii=False)}\n"
                f"Previous response: {previous_response[:4000]}"
            )
        prompt_path = attempt_dir / "prompt.txt"
        response_path = attempt_dir / "response.json"
        stdout_path = attempt_dir / "events.jsonl"
        stderr_path = attempt_dir / "stderr.txt"
        receipt_path = attempt_dir / "receipt.json"
        prompt_path.write_text(prompt_for_attempt, encoding="utf-8")

        argv = [str(executable), "exec"]
        if bool(codex_config.get("ephemeral", True)):
            argv.append("--ephemeral")
        if bool(codex_config.get("ignore_user_config", True)):
            argv.append("--ignore-user-config")
        if bool(codex_config.get("ignore_rules", True)):
            argv.append("--ignore-rules")
        argv.extend(
            [
                "--sandbox",
                str(codex_config.get("sandbox", "read-only")),
                "--skip-git-repo-check",
                "--color",
                "never",
                "--json",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(response_path),
                "--cd",
                str(attempt_dir),
            ]
        )
        if requested_model:
            argv.extend(["--model", requested_model])
        reasoning_effort = str(codex_config.get("reasoning_effort") or "").strip()
        if reasoning_effort:
            argv.extend(["--config", f'model_reasoning_effort="{reasoning_effort}"'])
        argv.append("-")

        started = time.monotonic()
        timed_out = False
        try:
            completed = subprocess.run(
                argv,
                cwd=attempt_dir,
                input=prompt_for_attempt.encode("utf-8"),
                capture_output=True,
                check=False,
                shell=False,
                timeout=timeout_seconds,
            )
            returncode = completed.returncode
            stdout = completed.stdout.decode("utf-8", errors="replace")
            stderr = completed.stderr.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            returncode = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
        wall_seconds = round(time.monotonic() - started, 3)
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        event_meta = _codex_event_metadata(stdout)
        raw_response = response_path.read_text(encoding="utf-8").strip() if response_path.is_file() else ""
        try:
            response = json.loads(raw_response) if raw_response else None
            parse_error = None
        except json.JSONDecodeError as exc:
            response = None
            parse_error = str(exc)
        errors = []
        if returncode != 0:
            errors.append(f"Codex exited {returncode}")
        if timed_out:
            errors.append(f"Codex timed out after {timeout_seconds} seconds")
        if parse_error:
            errors.append(f"response JSON parse failed: {parse_error}")
        if response is not None:
            errors.extend(validate_player_response(response, other_seat, schema_path))
        if event_meta["tool_event_types"]:
            errors.append(f"isolated player invoked forbidden tools: {event_meta['tool_event_types']}")
        receipt = {
            "schema_version": 1,
            "status": "PASS" if not errors else "FAIL",
            "policy_source": "codex_player",
            "codex_version": version,
            "requested_model": requested_model or "cli_default",
            "reported_models": event_meta["reported_models"],
            "attempt": attempt_index,
            "returncode": returncode,
            "timed_out": timed_out,
            "wall_seconds": wall_seconds,
            "prompt_sha256": hashlib.sha256(prompt_for_attempt.encode("utf-8")).hexdigest(),
            "response_sha256": hashlib.sha256(raw_response.encode("utf-8")).hexdigest() if raw_response else None,
            "parse_ok": response is not None and parse_error is None,
            "schema_ok": response is not None and not validate_player_response(response, other_seat, schema_path),
            "isolation_pass": not event_meta["tool_event_types"],
            "repair_count": attempt_index,
            "token_fields": event_meta["token_fields"],
            "event_count": event_meta["parsed_event_count"],
            "errors": errors,
            "prompt_path": str(prompt_path),
            "response_path": str(response_path),
            "events_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        }
        _write_json(receipt_path, receipt)
        attempts.append(receipt)
        if not errors and isinstance(response, dict):
            return response, {**receipt, "attempts": attempts}
        previous_errors = errors
        previous_response = raw_response
    raise PipelineError(f"Codex player failed after {max_repairs + 1} attempts: {previous_errors}")


def _engine_types(storyworld_root: Path):
    if str(storyworld_root) not in sys.path:
        sys.path.insert(0, str(storyworld_root))
    from storyworld.env import DiplomacyStoryworldEnv, load_storyworld

    return DiplomacyStoryworldEnv, load_storyworld


def _episode_rows(
    world: dict[str, Any],
    family_id: str,
    split: str,
    condition: dict[str, Any],
    seed: int,
    storyworld_root: Path,
) -> list[dict[str, Any]]:
    DiplomacyStoryworldEnv, _ = _engine_types(storyworld_root)
    env = DiplomacyStoryworldEnv(world, seed=seed, log_path=None)
    state = env.reset(seed=seed)
    condition_id = condition["id"]
    frames = condition["frames"]
    episode_id = f"{world['id']}__{condition_id}__seed_{seed}"
    experiment_meta = world.get("metadata", {}).get("experiment", {})
    visible_facts = list(experiment_meta.get("visible_facts", []))
    rows: list[dict[str, Any]] = [
        {
            "event": "reset",
            "payload": {
                "episode_id": episode_id,
                "world_id": world["id"],
                "family_id": family_id,
                "split": split,
                "condition_id": condition_id,
                "seed": seed,
                "policy_source": "scripted_smoke",
                "evidence_tier": "SMOKE_ONLY",
                "adapter_eligible": False,
                "frames": frames,
                "state": state,
                "forecast_questions": world["rules"]["forecast_questions"],
            },
        }
    ]
    for turn_index in range(1, int(world.get("turn_limit", 8)) + 1):
        owner = str(state.get("turn_owner"))
        frame = str(frames[owner])
        response = scripted_response(frame, owner, turn_index, seed, condition_id, visible_facts)
        private_evidence = experiment_meta.get("private_evidence", {}).get(owner, "")
        observation = {
            "active_node": state.get("active_node"),
            "world_vars": state.get("world_vars", {}),
            "public_messages": [*world.get("messages", []), *state.get("messages", [])],
            "visible_facts": visible_facts,
            "private_evidence": private_evidence,
        }
        action = {
            "type": response["action_type"],
            "target": response["target"],
            "principle_id": response["principle_id"],
            "public_justification": response["public_justification"],
            "responsibility_attribution": response["responsibility_attribution"],
            "forecasts": canonical_forecasts(response),
            "confidence": response["confidence"],
            "moral_commit": {
                "frame": frame,
                "principle_id": response["principle_id"],
                "text": response["public_justification"],
            },
            "decision_source": "scripted_smoke",
        }
        message = {
            "from": owner,
            "to": _other_seat(owner),
            "type": response["message_type"],
            "content": response["message_content"],
            "meta": {"frame": frame, "principle_id": response["principle_id"]},
        }
        state, event, done = env.step({owner: action}, [message])
        event.update(
            {
                "episode_id": episode_id,
                "world_id": world["id"],
                "family_id": family_id,
                "split": split,
                "condition_id": condition_id,
                "seed": seed,
                "policy_source": "scripted_smoke",
                "evidence_tier": "SMOKE_ONLY",
                "adapter_eligible": False,
                "frames": frames,
                "turn_owner_frame": frame,
                "observation": observation,
                "player_response": response,
            }
        )
        event["metrics"] = {
            **event.get("metrics", {}),
            "message_count": len(event.get("messages", [])),
            "moral_commit_recorded": 1,
            "agreement": 1 if event.get("outcome") == "coalition_formed" else 0,
        }
        rows.append({"event": "step", "payload": event})
        if done:
            break
    return rows


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"malformed JSONL at {path}:{line_number}") from exc
        if not isinstance(row, dict):
            raise PipelineError(f"JSONL row must be an object at {path}:{line_number}")
        rows.append(row)
    return rows


def _resume_codex_state(
    world: dict[str, Any], seed: int, rows: list[dict[str, Any]], storyworld_root: Path
):
    DiplomacyStoryworldEnv, _ = _engine_types(storyworld_root)
    env = DiplomacyStoryworldEnv(world, seed=seed, log_path=None)
    state = env.reset(seed=seed)
    for row in rows[1:]:
        if row.get("event") != "step":
            raise PipelineError("Codex episode checkpoint contains a non-step row after reset")
        payload = row.get("payload", {})
        owner = payload.get("turn_owner")
        action = payload.get("actions", {}).get(owner)
        messages = payload.get("messages", [])
        if not isinstance(action, dict):
            raise PipelineError("Codex episode checkpoint is missing the turn-owner action")
        state, replayed, _ = env.step({owner: action}, messages)
        if replayed.get("outcome") != payload.get("outcome") or replayed.get("active_node") != payload.get("active_node"):
            raise PipelineError("Codex episode checkpoint no longer replays deterministically")
    return env, state


def run_codex_episode(
    root: Path,
    output_root: Path,
    storyworld_root: Path,
    codex_executable: Path,
    config: dict[str, Any],
    entry: dict[str, Any],
    condition: dict[str, Any],
    seed: int,
    max_turns: int,
) -> dict[str, Any]:
    world = entry["world"]
    family_id = entry["family_id"]
    split = entry["split"]
    condition_id = condition["id"]
    frames = condition["frames"]
    requested_model = str(config.get("codex", {}).get("model") or "cli_default").strip()
    episode_id = f"{world['id']}__{condition_id}__seed_{seed}"
    episode_path = (
        output_root / "runs" / "codex_player" / split / family_id / condition_id / f"seed_{seed}.jsonl"
    )
    partial_path = episode_path.with_suffix(".jsonl.partial")
    if episode_path.is_file():
        existing = _read_jsonl(episode_path)
        recorded_model = str(
            existing[0].get("payload", {}).get("requested_model", "cli_default")
        )
        if recorded_model != requested_model:
            raise PipelineError(
                f"completed episode model mismatch: recorded={recorded_model!r}, "
                f"requested={requested_model!r}"
            )
        return {
            "status": "SKIPPED_COMPLETE",
            "episode_id": episode_id,
            "path": str(episode_path),
            "sha256": _sha256(episode_path),
            "steps": sum(row.get("event") == "step" for row in existing),
        }

    experiment_meta = world.get("metadata", {}).get("experiment", {})
    visible_facts = list(experiment_meta.get("visible_facts", []))
    schema_path = root / "schemas" / "player_response.schema.json"
    if partial_path.is_file():
        rows = _read_jsonl(partial_path)
        if not rows or rows[0].get("payload", {}).get("episode_id") != episode_id:
            raise PipelineError(f"invalid episode checkpoint: {partial_path}")
        recorded_model = str(
            rows[0].get("payload", {}).get("requested_model", "cli_default")
        )
        if recorded_model != requested_model:
            raise PipelineError(
                f"checkpoint model mismatch: recorded={recorded_model!r}, "
                f"requested={requested_model!r}"
            )
        env, state = _resume_codex_state(world, seed, rows, storyworld_root)
    else:
        DiplomacyStoryworldEnv, _ = _engine_types(storyworld_root)
        env = DiplomacyStoryworldEnv(world, seed=seed, log_path=None)
        state = env.reset(seed=seed)
        rows = [
            {
                "event": "reset",
                "payload": {
                    "episode_id": episode_id,
                    "world_id": world["id"],
                    "family_id": family_id,
                    "split": split,
                    "condition_id": condition_id,
                    "seed": seed,
                    "policy_source": "codex_player",
                    "requested_model": requested_model,
                    "evidence_tier": "UNREVIEWED",
                    "adapter_eligible": False,
                    "frames": frames,
                    "state": state,
                    "forecast_questions": world["rules"]["forecast_questions"],
                },
            }
        ]
        _write_jsonl(partial_path, rows)

    completed_steps = sum(row.get("event") == "step" for row in rows)
    public_transcript = list(world.get("messages", []))
    for row in rows[1:]:
        public_transcript.extend(row.get("payload", {}).get("messages", []))

    episode_limit = int(world.get("turn_limit", config.get("turn_limit", 8)))
    stop_at = min(episode_limit, max_turns)
    for turn_index in range(completed_steps + 1, stop_at + 1):
        owner = str(state.get("turn_owner"))
        if owner not in frames:
            raise PipelineError(f"turn owner is not an isolated decision seat: {owner}")
        frame = str(frames[owner])
        private_evidence = experiment_meta.get("private_evidence", {}).get(owner, "")
        observation = {
            "active_node": state.get("active_node"),
            "world_vars": state.get("world_vars", {}),
            "coalitions": state.get("coalitions", []),
            "visible_facts": visible_facts,
            "private_evidence": private_evidence,
        }
        prompt = build_codex_prompt(
            _constitution_text(config, root, frame),
            world,
            condition_id,
            owner,
            frame,
            turn_index,
            observation,
            state.get("beliefs", {}).get(owner, {}),
            public_transcript,
        )
        call_root = output_root / "codex_calls" / episode_id / f"turn_{turn_index:03d}_{owner}"
        response, receipt = invoke_codex_player(
            codex_executable, config, schema_path, call_root, prompt, _other_seat(owner)
        )
        action = {
            "type": response["action_type"],
            "target": response["target"],
            "principle_id": response["principle_id"],
            "public_justification": response["public_justification"],
            "responsibility_attribution": response["responsibility_attribution"],
            "forecasts": canonical_forecasts(response),
            "confidence": response["confidence"],
            "moral_commit": {
                "frame": frame,
                "principle_id": response["principle_id"],
                "text": response["public_justification"],
            },
            "decision_source": "codex_player",
        }
        message = {
            "from": owner,
            "to": _other_seat(owner),
            "type": response["message_type"],
            "content": response["message_content"],
            "meta": {"frame": frame, "principle_id": response["principle_id"]},
        }
        state, event, done = env.step({owner: action}, [message])
        public_transcript.append(message)
        event.update(
            {
                "episode_id": episode_id,
                "world_id": world["id"],
                "family_id": family_id,
                "split": split,
                "condition_id": condition_id,
                "seed": seed,
                "policy_source": "codex_player",
                "evidence_tier": "UNREVIEWED",
                "adapter_eligible": False,
                "frames": frames,
                "turn_owner_frame": frame,
                "observation": observation,
                "player_response": response,
                "generation_receipt": receipt,
            }
        )
        event["metrics"] = {
            **event.get("metrics", {}),
            "message_count": len(event.get("messages", [])),
            "moral_commit_recorded": 1,
            "agreement": 1 if event.get("outcome") == "coalition_formed" else 0,
        }
        rows.append({"event": "step", "payload": event})
        _write_jsonl(partial_path, rows)
        if done:
            break

    completed_steps = sum(row.get("event") == "step" for row in rows)
    complete = bool(state.get("done")) or completed_steps >= episode_limit
    if complete:
        episode_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(partial_path, episode_path)
        return {
            "status": "PASS",
            "episode_id": episode_id,
            "path": str(episode_path),
            "sha256": _sha256(episode_path),
            "steps": completed_steps,
            "evidence_tier": "UNREVIEWED",
            "adapter_eligible": False,
        }
    return {
        "status": "IN_PROGRESS",
        "episode_id": episode_id,
        "checkpoint": str(partial_path),
        "steps": completed_steps,
        "next_turn": completed_steps + 1,
        "evidence_tier": "UNREVIEWED",
        "adapter_eligible": False,
    }


def run_codex_batch(
    root: Path,
    output_root: Path,
    storyworld_root: Path,
    codex_executable: Path,
    splits: set[str],
    condition_ids: set[str],
    seeds: list[int],
    max_episodes: int,
    max_turns: int,
    model_override: str = "",
) -> dict[str, Any]:
    validate_experiment(root, storyworld_root)
    config = load_experiment_config(root)
    if model_override:
        config = json.loads(json.dumps(config))
        config.setdefault("codex", {})["model"] = model_override
    registry = [entry for entry in world_registry(config, root) if entry["split"] in splits]
    conditions = [condition for condition in config.get("conditions", []) if condition["id"] in condition_ids]
    if not registry:
        raise PipelineError(f"no Codex worlds selected for splits: {sorted(splits)}")
    if not conditions:
        raise PipelineError(f"no Codex conditions selected: {sorted(condition_ids)}")
    receipts = []
    for entry in registry:
        for condition in conditions:
            for seed in seeds:
                if len(receipts) >= max_episodes:
                    break
                receipts.append(
                    run_codex_episode(
                        root,
                        output_root,
                        storyworld_root,
                        codex_executable,
                        config,
                        entry,
                        condition,
                        int(seed),
                        max_turns,
                    )
                )
            if len(receipts) >= max_episodes:
                break
        if len(receipts) >= max_episodes:
            break
    result = {
        "status": "PASS" if receipts and all(row["status"] in {"PASS", "SKIPPED_COMPLETE"} for row in receipts) else "IN_PROGRESS",
        "experiment_id": config["experiment_id"],
        "policy_source": "codex_player",
        "evidence_tier": "UNREVIEWED",
        "adapter_eligible": False,
        "codex_version": _codex_version(codex_executable),
        "requested_model": config.get("codex", {}).get("model") or "cli_default",
        "splits": sorted(splits),
        "conditions": sorted(condition_ids),
        "seeds": seeds,
        "max_turns": max_turns,
        "receipts": receipts,
    }
    _write_json(output_root / "runs" / "codex_player" / "manifest.json", result)
    return result


def run_smoke(
    root: Path,
    output_root: Path,
    storyworld_root: Path,
    splits: set[str],
    seed_set: str,
) -> dict[str, Any]:
    config = load_experiment_config(root)
    registry = world_registry(config, root)
    seeds = config.get("seed_sets", {}).get(seed_set)
    if not isinstance(seeds, list) or not seeds:
        raise PipelineError(f"unknown or empty seed set: {seed_set}")
    run_root = output_root / "runs" / f"scripted_{seed_set}"
    receipts = []
    for entry in registry:
        if entry["split"] not in splits:
            continue
        for condition in config.get("conditions", []):
            for seed in seeds:
                rows = _episode_rows(
                    entry["world"], entry["family_id"], entry["split"], condition, int(seed), storyworld_root
                )
                path = run_root / entry["split"] / entry["family_id"] / condition["id"] / f"seed_{seed}.jsonl"
                _write_jsonl(path, rows)
                receipts.append(
                    {
                        "path": str(path),
                        "sha256": _sha256(path),
                        "episode_id": rows[0]["payload"]["episode_id"],
                        "steps": len(rows) - 1,
                    }
                )
    if not receipts:
        raise PipelineError(f"no worlds selected for splits: {sorted(splits)}")
    manifest = {
        "status": "PASS",
        "evidence_tier": "SMOKE_ONLY",
        "adapter_eligible": False,
        "policy_source": "scripted_smoke",
        "experiment_id": config["experiment_id"],
        "seed_set": seed_set,
        "splits": sorted(splits),
        "episodes": len(receipts),
        "receipts": receipts,
        "warning": "Scripted policy output verifies plumbing only and is not paper evidence.",
    }
    _write_json(run_root / "manifest.json", manifest)
    return manifest


def _iter_records(log_root: Path) -> Iterable[dict[str, Any]]:
    for path in sorted(log_root.rglob("*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PipelineError(f"malformed JSONL at {path}:{line_number}") from exc
            record["_source_path"] = str(path)
            yield record


def score_logs(log_root: Path, output_root: Path) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "episodes": set(),
            "steps": 0,
            "outcomes": Counter(),
            "actions": Counter(),
            "frames": Counter(),
            "forecast_accuracy_sum": 0.0,
            "forecast_accuracy_count": 0,
            "brier_sum": 0.0,
            "brier_count": 0,
            "agreement_sum": 0,
            "commitment_sum": 0,
        }
    )
    sources: set[str] = set()
    for record in _iter_records(log_root):
        if record.get("event") != "step":
            continue
        payload = record.get("payload", {})
        key = f"{payload.get('split')}::{payload.get('condition_id')}"
        group = groups[key]
        group["episodes"].add(payload.get("episode_id"))
        group["steps"] += 1
        group["outcomes"][str(payload.get("outcome"))] += 1
        response = payload.get("player_response", {})
        group["actions"][str(response.get("action_type"))] += 1
        group["frames"][str(payload.get("turn_owner_frame"))] += 1
        metrics = payload.get("metrics", {})
        group["agreement_sum"] += int(metrics.get("agreement", 0) or 0)
        group["commitment_sum"] += int(metrics.get("moral_commit_recorded", 0) or 0)
        sources.add(str(payload.get("policy_source")))
        for score in payload.get("forecast_scores", {}).values():
            entries = score if isinstance(score, list) else [score]
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if "accuracy" in entry:
                    group["forecast_accuracy_sum"] += float(entry["accuracy"])
                    group["forecast_accuracy_count"] += 1
                if "brier" in entry:
                    group["brier_sum"] += float(entry["brier"])
                    group["brier_count"] += 1

    summary: dict[str, Any] = {}
    for key, group in sorted(groups.items()):
        steps = group["steps"]
        summary[key] = {
            "episodes": len(group["episodes"]),
            "steps": steps,
            "outcomes": dict(sorted(group["outcomes"].items())),
            "actions": dict(sorted(group["actions"].items())),
            "speaker_frames": dict(sorted(group["frames"].items())),
            "agreement_rate": round(group["agreement_sum"] / steps, 4) if steps else None,
            "commitment_record_rate": round(group["commitment_sum"] / steps, 4) if steps else None,
            "forecast_accuracy": round(
                group["forecast_accuracy_sum"] / group["forecast_accuracy_count"], 4
            ) if group["forecast_accuracy_count"] else None,
            "forecast_brier": round(group["brier_sum"] / group["brier_count"], 4) if group["brier_count"] else None,
        }
    if not summary:
        raise PipelineError(f"no step records found beneath {log_root}")
    evidence_tier = "SMOKE_ONLY" if sources == {"scripted_smoke"} else "UNREVIEWED"
    result = {
        "status": "PASS",
        "evidence_tier": evidence_tier,
        "policy_sources": sorted(sources),
        "groups": summary,
        "warning": (
            "SMOKE_ONLY differences are properties of the fixture policy and support no frame hypothesis."
            if evidence_tier == "SMOKE_ONLY"
            else "UNREVIEWED Codex-player output is diagnostic only until the episode is human-reviewed."
        ),
    }
    _write_json(output_root / "scorecards" / "scorecard.json", result)
    return result


def _constitution_text(config: dict[str, Any], root: Path, frame: str) -> str:
    relative = config.get("constitutions", {}).get(frame)
    if not relative:
        raise PipelineError(f"missing constitution for frame: {frame}")
    return (root / relative).read_text(encoding="utf-8").strip()


def export_sft(
    root: Path,
    log_root: Path,
    output_root: Path,
    allow_scripted_smoke: bool = False,
) -> dict[str, Any]:
    config = load_experiment_config(root)
    registry = world_registry(config, root)
    families = {entry["family_id"]: entry for entry in registry}
    eligible_sources = set(config.get("adapter_eligible_sources", []))
    training_splits = set(config.get("training_splits", []))
    rows_by_frame: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_ids: set[str] = set()

    for record in _iter_records(log_root):
        if record.get("event") != "step":
            continue
        payload = record.get("payload", {})
        family_id = str(payload.get("family_id") or "")
        split = str(payload.get("split") or "")
        registry_entry = families.get(family_id)
        if registry_entry is None or registry_entry["split"] != split:
            raise PipelineError(f"log family/split does not match frozen registry: {family_id}/{split}")
        if split not in training_splits:
            continue
        source = str(payload.get("policy_source") or "")
        smoke_override = allow_scripted_smoke and source == "scripted_smoke"
        if source not in eligible_sources and not smoke_override:
            continue
        response = payload.get("player_response")
        observation = payload.get("observation")
        frame = str(payload.get("turn_owner_frame") or "")
        if not isinstance(response, dict) or not isinstance(observation, dict) or frame not in {"jinn", "beast", "inert"}:
            raise PipelineError(f"incomplete player record in {record['_source_path']}")
        if "hidden_state" in json.dumps(observation, sort_keys=True):
            raise PipelineError("hidden state leaked into a model-visible observation")
        record_id = f"{payload['episode_id']}__turn_{payload['turn']}__{payload['turn_owner']}"
        if record_id in seen_ids:
            raise PipelineError(f"duplicate SFT record id: {record_id}")
        seen_ids.add(record_id)
        assistant_payload = {
            key: response[key]
            for key in (
                "message_type",
                "message_content",
                "action_type",
                "target",
                "principle_id",
                "public_justification",
                "responsibility_attribution",
                "forecasts",
                "confidence",
            )
        }
        row = {
            "record_id": record_id,
            "messages": [
                {"role": "system", "content": _constitution_text(config, root, frame)},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "speaker": payload["turn_owner"],
                            "other_speaker": _other_seat(payload["turn_owner"]),
                            "condition_id": payload["condition_id"],
                            "observation": observation,
                            "legal_actions": ["propose", "ally", "betray", "wait"],
                            "response_contract": "schemas/player_response.schema.json",
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
                {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False, sort_keys=True)},
            ],
            "metadata": {
                "experiment_id": config["experiment_id"],
                "world_id": payload["world_id"],
                "family_id": family_id,
                "source_split": split,
                "episode_id": payload["episode_id"],
                "seed": payload["seed"],
                "turn": payload["turn"],
                "speaker": payload["turn_owner"],
                "frame": frame,
                "condition_id": payload["condition_id"],
                "policy_source": source,
                "evidence_tier": "SMOKE_ONLY" if smoke_override else "UNREVIEWED",
                "adapter_eligible": not smoke_override,
                "contains_hidden_chain_of_thought": False,
            },
        }
        rows_by_frame[frame].append(row)

    if not rows_by_frame:
        raise PipelineError(
            "no adapter-eligible train rows found; run reviewed Codex players or pass "
            "--allow-scripted-smoke for a non-training format check"
        )
    export_dir = output_root / "sft"
    receipts = []
    for frame, rows in sorted(rows_by_frame.items()):
        suffix = "smoke_not_for_training" if allow_scripted_smoke else "train"
        path = export_dir / f"{frame}_{suffix}.jsonl"
        _write_jsonl(path, sorted(rows, key=lambda item: item["record_id"]))
        receipts.append({"frame": frame, "rows": len(rows), "path": str(path), "sha256": _sha256(path)})
    manifest = {
        "status": "PASS",
        "experiment_id": config["experiment_id"],
        "evidence_tier": "SMOKE_ONLY" if allow_scripted_smoke else "UNREVIEWED",
        "adapter_eligible": not allow_scripted_smoke,
        "training_splits": sorted(training_splits),
        "receipts": receipts,
        "warning": "SMOKE_ONLY exports validate format and must not be used to train a paper or product adapter."
        if allow_scripted_smoke
        else "Rows still require the review receipts defined in DATA_GOVERNANCE.md before training.",
    }
    _write_json(export_dir / "manifest.json", manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--storyworld-root", type=Path)
    parser.add_argument("--codex-executable", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    smoke = sub.add_parser("smoke")
    smoke.add_argument("--splits", nargs="+", default=["train"], choices=["train", "dev", "holdout"])
    smoke.add_argument("--seed-set", default="smoke")
    codex = sub.add_parser("codex-run")
    codex.add_argument("--splits", nargs="+", default=["train"], choices=["train", "dev", "holdout"])
    codex.add_argument("--conditions", nargs="+", default=["jinn_beast"])
    codex.add_argument("--seeds", nargs="+", type=int, default=[17])
    codex.add_argument("--max-episodes", type=int, default=1)
    codex.add_argument("--max-turns", type=int, default=8)
    codex.add_argument("--model", default="")
    score = sub.add_parser("score")
    score.add_argument("--log-root", type=Path)
    export = sub.add_parser("export-sft")
    export.add_argument("--log-root", type=Path)
    export.add_argument("--allow-scripted-smoke", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = configured_experiment_root(args.experiment_root)
    output_root = configured_output_root(args.output_root)
    if args.command == "validate":
        result = validate_experiment(root, configured_storyworld_root(args.storyworld_root))
    elif args.command == "smoke":
        result = run_smoke(
            root,
            output_root,
            configured_storyworld_root(args.storyworld_root),
            set(args.splits),
            args.seed_set,
        )
    elif args.command == "codex-run":
        if args.max_episodes < 1 or args.max_turns < 1:
            raise PipelineError("Codex max-episodes and max-turns must be positive")
        result = run_codex_batch(
            root,
            output_root,
            configured_storyworld_root(args.storyworld_root),
            configured_codex_executable(args.codex_executable),
            set(args.splits),
            set(args.conditions),
            list(args.seeds),
            args.max_episodes,
            args.max_turns,
            args.model,
        )
    elif args.command == "score":
        log_root = args.log_root or output_root / "runs" / "scripted_smoke"
        result = score_logs(log_root.resolve(), output_root)
    elif args.command == "export-sft":
        log_root = args.log_root or output_root / "runs" / "scripted_smoke"
        result = export_sft(root, log_root.resolve(), output_root, args.allow_scripted_smoke)
    else:  # pragma: no cover
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PipelineError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2)
