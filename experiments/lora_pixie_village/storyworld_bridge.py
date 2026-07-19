#!/usr/bin/env python3
"""Extract a leakage-safe public decision card from a validated Storyworld.

This module does not execute Storyworld dynamics. It creates the narrow public
input consumed by the phase-one two-agent conversation room. Only fields
explicitly declared visible by the source experiment are eligible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


DECISION_SCHEMA = "pixie_village_decision_v1"
MANIFEST_SCHEMA = "pixie_village_decision_manifest_v1"
ACTION_COPY = {
    "propose": ("Propose safeguards", "Offer a concrete joint protocol for the decision."),
    "ally": ("Form a coalition", "Commit to a shared course with the other resident."),
    "betray": ("Act unilaterally", "Break coordination and take the risky action alone."),
    "wait": ("Wait", "Delay commitment while asking for more public information."),
}
FORBIDDEN_SOURCE_KEYS = {
    "hidden_state",
    "private_evidence",
    "beliefs",
    "trust",
    "expected_payoff",
}


class DecisionBridgeError(RuntimeError):
    """A world cannot be safely projected into a public decision card."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DecisionBridgeError(f"cannot read JSON object from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DecisionBridgeError(f"expected JSON object: {path}")
    return payload


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def find_validator(storyworld_root: Path) -> Path:
    path = storyworld_root.resolve() / "storyworld" / "validators" / "validate_storyworld.py"
    if not path.is_file():
        raise DecisionBridgeError(f"canonical Storyworld validator not found: {path}")
    return path


def validate_source_world(world_path: Path, storyworld_root: Path) -> dict[str, Any]:
    validator = find_validator(storyworld_root)
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [sys.executable, str(validator), str(world_path.resolve()), "--strict"],
        cwd=storyworld_root.resolve(),
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        shell=False,
        timeout=60,
    )
    receipt = {
        "validator": str(validator),
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    if completed.returncode != 0:
        raise DecisionBridgeError(f"canonical Storyworld validation failed: {receipt}")
    return receipt


def _required_string(value: Any, label: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise DecisionBridgeError(f"{label} is required")
    return text


def validate_decision_packet(packet: dict[str, Any]) -> dict[str, Any]:
    if packet.get("schema_version") != DECISION_SCHEMA:
        raise DecisionBridgeError(f"decision schema must be {DECISION_SCHEMA}")
    normalized = {
        **packet,
        "decision_id": _required_string(packet.get("decision_id"), "decision_id"),
        "title": _required_string(packet.get("title"), "title"),
        "situation": _required_string(packet.get("situation"), "situation"),
        "location": _required_string(packet.get("location"), "location"),
    }
    source = packet.get("source")
    if not isinstance(source, dict):
        raise DecisionBridgeError("decision source must be an object")
    for field in ["storyworld_id", "world_revision", "source_sha256", "split"]:
        _required_string(source.get(field), f"source.{field}")
    facts = packet.get("visible_facts")
    if not isinstance(facts, list) or not facts:
        raise DecisionBridgeError("visible_facts must be a non-empty list")
    normalized["visible_facts"] = [_required_string(item, "visible_fact") for item in facts]
    constraints = packet.get("public_constraints", [])
    if not isinstance(constraints, list):
        raise DecisionBridgeError("public_constraints must be a list")
    normalized["public_constraints"] = [_required_string(item, "public_constraint") for item in constraints]
    options = packet.get("options")
    if not isinstance(options, list) or len(options) < 2:
        raise DecisionBridgeError("a decision requires at least two options")
    option_ids: set[str] = set()
    normalized_options = []
    for index, option in enumerate(options):
        if not isinstance(option, dict):
            raise DecisionBridgeError(f"options[{index}] must be an object")
        option_id = _required_string(option.get("id"), f"options[{index}].id")
        if option_id in option_ids:
            raise DecisionBridgeError(f"duplicate option id: {option_id}")
        if not option_id.replace("_", "").replace("-", "").isalnum():
            raise DecisionBridgeError(f"unsafe option id: {option_id}")
        option_ids.add(option_id)
        normalized_options.append(
            {
                "id": option_id,
                "label": _required_string(option.get("label"), f"options[{index}].label"),
                "description": _required_string(option.get("description"), f"options[{index}].description"),
            }
        )
    normalized["options"] = normalized_options
    encoded = canonical_json(normalized).lower()
    for forbidden in FORBIDDEN_SOURCE_KEYS:
        if f'"{forbidden.lower()}"' in encoded:
            raise DecisionBridgeError(f"forbidden private key leaked into decision packet: {forbidden}")
    return normalized


def private_source_values(world: dict[str, Any]) -> list[str]:
    values: list[str] = []
    hidden = world.get("hidden_state", [])
    if isinstance(hidden, list):
        values.extend(str(item.get("value")) for item in hidden if isinstance(item, dict))
    experiment = world.get("metadata", {}).get("experiment", {})
    private = experiment.get("private_evidence", {}) if isinstance(experiment, dict) else {}
    if isinstance(private, dict):
        values.extend(str(value) for value in private.values())
    return [value for value in values if value]


def extract_public_decision(world_path: Path) -> dict[str, Any]:
    world_path = world_path.resolve()
    world = read_object(world_path)
    experiment = world.get("metadata", {}).get("experiment", {})
    if not isinstance(experiment, dict):
        raise DecisionBridgeError("world metadata.experiment is required")
    visible_facts = experiment.get("visible_facts")
    if not isinstance(visible_facts, list) or not visible_facts:
        raise DecisionBridgeError("world must explicitly declare metadata.experiment.visible_facts")
    initial_state = world.get("initial_state")
    if not isinstance(initial_state, dict):
        raise DecisionBridgeError("world initial_state is required")
    active_node = str(initial_state.get("active_node") or "")
    nodes = world.get("nodes")
    if not isinstance(nodes, list):
        raise DecisionBridgeError("world nodes must be a list")
    node = next((item for item in nodes if isinstance(item, dict) and item.get("id") == active_node), None)
    if node is None:
        raise DecisionBridgeError(f"active node is not registered: {active_node}")
    action_types = world.get("rules", {}).get("action_types")
    if not isinstance(action_types, list) or len(action_types) < 2:
        raise DecisionBridgeError("world rules.action_types must declare at least two public actions")
    options = []
    for action in action_types:
        action_id = _required_string(action, "action_type")
        label, description = ACTION_COPY.get(
            action_id,
            (action_id.replace("_", " ").title(), f"Choose the public storyworld action '{action_id}'."),
        )
        options.append({"id": action_id, "label": label, "description": description})
    public_constraints = []
    for message in world.get("messages", []):
        if not isinstance(message, dict):
            continue
        if str(message.get("to") or "").lower() in {"all", "public", "*"}:
            public_constraints.append(_required_string(message.get("content"), "public message"))
    packet = {
        "schema_version": DECISION_SCHEMA,
        "decision_id": f"{world['id']}::{active_node}",
        "title": str(world.get("title") or world["id"]),
        "situation": str(world.get("description") or "A public decision is required."),
        "location": str(node.get("label") or active_node),
        "visible_facts": list(visible_facts),
        "public_constraints": public_constraints,
        "options": options,
        "source": {
            "storyworld_id": str(world["id"]),
            "world_revision": str(experiment.get("revision") or "unversioned"),
            "source_sha256": sha256_file(world_path),
            "split": str(experiment.get("split") or "unspecified"),
        },
    }
    normalized = validate_decision_packet(packet)
    audit_public_packet(normalized, private_source_values(world))
    return normalized


def audit_public_packet(packet: dict[str, Any], forbidden_values: Iterable[str] = ()) -> dict[str, Any]:
    normalized = validate_decision_packet(packet)
    encoded = canonical_json(normalized)
    checked_values = [value for value in forbidden_values if value]
    leaked = [value for value in checked_values if value in encoded]
    if leaked:
        raise DecisionBridgeError(f"private source value leaked into public decision packet: {leaked}")
    return {
        "status": "PASS",
        "decision_id": normalized["decision_id"],
        "packet_sha256": sha256_value(normalized),
        "visible_fact_count": len(normalized["visible_facts"]),
        "option_count": len(normalized["options"]),
        "forbidden_value_checks": len(checked_values),
    }


def build_packet(world: Path, output: Path, manifest: Path, storyworld_root: Path) -> dict[str, Any]:
    validation = validate_source_world(world, storyworld_root)
    packet = extract_public_decision(world)
    audit = audit_public_packet(packet, private_source_values(read_object(world.resolve())))
    atomic_json(output, packet)
    reread = validate_decision_packet(read_object(output))
    if sha256_value(reread) != audit["packet_sha256"]:
        raise DecisionBridgeError("written decision packet failed round-trip hashing")
    receipt = {
        "schema_version": MANIFEST_SCHEMA,
        "status": "PASS",
        "source_world": str(world.resolve()),
        "source_sha256": sha256_file(world.resolve()),
        "decision_packet": str(output.resolve()),
        "decision_packet_sha256": sha256_file(output.resolve()),
        "semantic_packet_sha256": audit["packet_sha256"],
        "canonical_validation": validation,
        "leakage_audit": audit,
    }
    atomic_json(manifest, receipt)
    return receipt


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--world", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True)
    command.add_argument("--manifest", type=Path, required=True)
    command.add_argument("--storyworld-root", type=Path, required=True)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    receipt = build_packet(args.world, args.out, args.manifest, args.storyworld_root)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
