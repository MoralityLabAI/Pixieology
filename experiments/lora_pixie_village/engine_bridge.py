"""Replay-safe adapter from village proposals to the canonical Storyworld engine.

This module never reimplements world dynamics. It imports
``DiplomacyStoryworldEnv`` from the configured GPTStoryworld checkout, resets it,
and replays fsynced public action receipts before applying one new action.
"""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from storyworld_bridge import (
    canonical_json,
    private_source_values,
    read_object,
    sha256_file,
    sha256_value,
    validate_source_world,
)


ENGINE_SCHEMA = "pixie_village_engine_state_v1"
ENGINE_STEP_SCHEMA = "pixie_village_engine_step_v1"
FORBIDDEN_PUBLIC_KEYS = {"beliefs", "trust", "private_evidence", "hidden_state", "expected_payoff"}
MESSAGE_TYPE_BY_ACTION = {
    "propose": "proposal",
    "ally": "concession",
    "betray": "challenge",
    "wait": "update",
}


class EngineBridgeError(RuntimeError):
    """Canonical engine application or deterministic replay failed."""


def _contains_forbidden_key(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_PUBLIC_KEYS:
                return str(key)
            found = _contains_forbidden_key(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _contains_forbidden_key(child)
            if found:
                return found
    return None


def audit_public_engine_value(value: Any, forbidden_values: list[str]) -> dict[str, Any]:
    key = _contains_forbidden_key(value)
    if key:
        raise EngineBridgeError(f"private engine key leaked into public receipt: {key}")
    encoded = canonical_json(value)
    leaked = [item for item in forbidden_values if item and item in encoded]
    if leaked:
        raise EngineBridgeError(f"private engine value leaked into public receipt: {leaked}")
    return {
        "status": "PASS",
        "forbidden_key_count": len(FORBIDDEN_PUBLIC_KEYS),
        "forbidden_value_checks": len(forbidden_values),
        "public_sha256": sha256_value(value),
    }


@dataclass(frozen=True)
class WorldBinding:
    decision_id: str
    path: Path
    world: dict[str, Any]
    source_sha256: str
    validation: dict[str, Any]


class StoryworldEngineBridge:
    def __init__(self, engine_root: Path, source_world_root: Path, decision_catalog: Any):
        self.engine_root = engine_root.resolve()
        self.source_world_root = source_world_root.resolve()
        self.decision_catalog = decision_catalog
        self.validator_path = self.engine_root / "storyworld" / "validators" / "validate_storyworld.py"
        self.engine_path = self.engine_root / "storyworld" / "env" / "diplomacy_env.py"
        if not self.validator_path.is_file() or not self.engine_path.is_file():
            raise EngineBridgeError(f"canonical Storyworld engine is unavailable at {self.engine_root}")
        if not self.source_world_root.is_dir():
            raise EngineBridgeError(f"source world root is unavailable: {self.source_world_root}")
        self.engine_sha256 = sha256_file(self.engine_path)
        self._bindings: dict[str, WorldBinding] = {}
        self._env_type: Any | None = None

    def _load_env_type(self) -> Any:
        if self._env_type is not None:
            return self._env_type
        root_text = str(self.engine_root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
        module = importlib.import_module("storyworld.env.diplomacy_env")
        module_path = Path(module.__file__ or "").resolve()
        try:
            module_path.relative_to(self.engine_root)
        except ValueError as exc:
            raise EngineBridgeError(
                f"loaded Storyworld engine from {module_path}, expected configured root {self.engine_root}"
            ) from exc
        self._env_type = module.DiplomacyStoryworldEnv
        return self._env_type

    def _binding(self, decision_id: str) -> WorldBinding:
        if decision_id in self._bindings:
            return self._bindings[decision_id]
        packet = self.decision_catalog.get(decision_id)
        source = packet["source"]
        matches: list[Path] = []
        for path in self.source_world_root.rglob("*.json"):
            try:
                candidate = read_object(path)
            except Exception:
                continue
            if candidate.get("id") == source["storyworld_id"]:
                matches.append(path.resolve())
        if len(matches) != 1:
            raise EngineBridgeError(
                f"expected exactly one source world {source['storyworld_id']} beneath {self.source_world_root}; found {len(matches)}"
            )
        world_path = matches[0]
        actual_sha = sha256_file(world_path)
        if actual_sha != source["source_sha256"]:
            raise EngineBridgeError(
                f"source world hash mismatch for {decision_id}: expected {source['source_sha256']}, got {actual_sha}"
            )
        validation = validate_source_world(world_path, self.engine_root)
        binding = WorldBinding(
            decision_id=decision_id,
            path=world_path,
            world=read_object(world_path),
            source_sha256=actual_sha,
            validation=validation,
        )
        self._bindings[decision_id] = binding
        return binding

    @staticmethod
    def _node_label(world: dict[str, Any], node_id: str | None) -> str:
        for node in world.get("nodes", []):
            if isinstance(node, dict) and node.get("id") == node_id:
                return str(node.get("label") or node_id)
        return str(node_id or "Unknown")

    def _public_state(self, world: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        return {
            "engine_turn": int(state.get("turn", 0)),
            "active_node": state.get("active_node"),
            "location": self._node_label(world, state.get("active_node")),
            "done": bool(state.get("done")),
            "next_turn_owner": state.get("turn_owner"),
        }

    def _public_event(self, world: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        outcome = str(event.get("outcome") or "unknown")
        transition = world.get("rules", {}).get("outcomes", {}).get(outcome, {})
        metrics = event.get("metrics") if isinstance(event.get("metrics"), dict) else {}
        public = {
            "engine_turn": int(event.get("turn", 0)),
            "turn_owner": event.get("turn_owner"),
            "next_turn_owner": event.get("next_turn_owner"),
            "outcome": outcome,
            "outcome_notes": str(transition.get("notes") or ""),
            "active_node": event.get("active_node"),
            "location": self._node_label(world, event.get("active_node")),
            "done": bool(event.get("done")),
            "metrics": {
                "coalition_count": int(metrics.get("coalition_count", 0) or 0),
                "coalition_mean_stability": float(metrics.get("coalition_mean_stability", 0.0) or 0.0),
                "betrayal_surprise": metrics.get("betrayal_surprise"),
            },
        }
        audit_public_engine_value(public, private_source_values(world))
        return public

    def initialize(self, decision_id: str, seed: int, village_agent_ids: list[str]) -> dict[str, Any]:
        binding = self._binding(decision_id)
        world_turns = binding.world.get("turns")
        if not isinstance(world_turns, list) or len(world_turns) != len(village_agent_ids):
            raise EngineBridgeError("village residents and Storyworld turn seats do not match")
        Env = self._load_env_type()
        env = Env(binding.world, seed=seed, log_path=None)
        state = env.reset(seed=seed)
        agent_map = dict(zip(village_agent_ids, world_turns, strict=True))
        public_state = self._public_state(binding.world, state)
        descriptor = {
            "schema_version": ENGINE_SCHEMA,
            "status": "ready",
            "decision_id": decision_id,
            "source_sha256": binding.source_sha256,
            "engine_sha256": self.engine_sha256,
            "canonical_validation": binding.validation.get("stdout") == "VALID",
            "agent_map": agent_map,
            "history": [],
            "public_state": public_state,
        }
        audit_public_engine_value(descriptor, private_source_values(binding.world))
        return descriptor

    def apply(self, engine_state: dict[str, Any], speaker_id: str, action_id: str, public_message: str, seed: int) -> dict[str, Any]:
        if engine_state.get("schema_version") != ENGINE_SCHEMA or engine_state.get("status") != "ready":
            raise EngineBridgeError("session does not contain a ready canonical engine state")
        decision_id = str(engine_state.get("decision_id") or "")
        binding = self._binding(decision_id)
        if engine_state.get("source_sha256") != binding.source_sha256:
            raise EngineBridgeError("session source hash no longer matches the bound world")
        if engine_state.get("engine_sha256") != self.engine_sha256:
            raise EngineBridgeError("session engine hash no longer matches the configured engine")
        Env = self._load_env_type()
        env = Env(binding.world, seed=seed, log_path=None)
        state = env.reset(seed=seed)
        history = list(engine_state.get("history") or [])
        for index, receipt in enumerate(history):
            state, replayed, _ = env.step(receipt["actions"], receipt["messages"])
            replay_public = self._public_event(binding.world, replayed)
            if sha256_value(replay_public) != receipt.get("public_event_sha256"):
                raise EngineBridgeError(f"canonical replay mismatch at engine history index {index}")
        world_owner = engine_state.get("agent_map", {}).get(speaker_id)
        if not world_owner:
            raise EngineBridgeError(f"village agent is not mapped to a Storyworld seat: {speaker_id}")
        expected_owner = state.get("turn_owner")
        if world_owner != expected_owner:
            raise EngineBridgeError(
                f"turn-owner mismatch: village speaker {speaker_id} maps to {world_owner}, engine expects {expected_owner}"
            )
        legal = set(binding.world.get("rules", {}).get("action_types", []))
        if action_id not in legal:
            raise EngineBridgeError(f"illegal canonical engine action: {action_id}")
        turn_order = list(binding.world.get("turns", []))
        other_owner = next((owner for owner in turn_order if owner != world_owner), None)
        target = None if action_id == "wait" else other_owner
        action = {
            "type": action_id,
            "target": target,
            "public_justification": public_message,
            "decision_source": "pixie_village",
        }
        message = {
            "from": world_owner,
            "to": other_owner,
            "type": MESSAGE_TYPE_BY_ACTION.get(action_id, "update"),
            "content": public_message,
        }
        state, event, _ = env.step({world_owner: action}, [message])
        public_event = self._public_event(binding.world, event)
        receipt = {
            "schema_version": ENGINE_STEP_SCHEMA,
            "speaker_id": speaker_id,
            "world_owner": world_owner,
            "actions": {world_owner: action},
            "messages": [message],
            "public_event": public_event,
            "public_event_sha256": sha256_value(public_event),
            "replay_prefix_sha256": sha256_value(history),
        }
        audit_public_engine_value(receipt, private_source_values(binding.world))
        next_state = {
            **engine_state,
            "history": [*history, receipt],
            "public_state": self._public_state(binding.world, state),
        }
        audit_public_engine_value(next_state, private_source_values(binding.world))
        return next_state
