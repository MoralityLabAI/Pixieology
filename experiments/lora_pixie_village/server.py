#!/usr/bin/env python3
"""Local two-agent conversation platform for independently served LoRA Pixies.

The browser never receives model endpoints, API-key names, private system
prompts, or adapter paths. Every session begins as an ordinary agent-to-agent
conversation. A validated public Storyworld decision may later be attached as
discussion context; it is an optional layer, not the owner of the dialogue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from storyworld_bridge import DecisionBridgeError, read_object as read_decision_object
from storyworld_bridge import validate_decision_packet
from engine_bridge import EngineBridgeError, StoryworldEngineBridge
from provider_preflight import ProviderPreflightError, atomic_json as write_preflight_json
from provider_preflight import preflight_providers


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parents[1]
SCHEMA = "pixie_village_agents_v1"
SESSION_SCHEMA = "pixie_village_session_v1"
EVENT_SCHEMA = "pixie_village_event_v1"
PROVIDER_TYPES = {"deterministic", "openai_compatible"}
THINK_BLOCK = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.IGNORECASE | re.DOTALL)
PROPOSAL_MARKER = re.compile(r"\[proposal:([a-zA-Z0-9_-]+)\]", re.IGNORECASE)


class VillageError(RuntimeError):
    """The room contract or a provider call failed."""


class ProviderError(VillageError):
    """A model provider failed without advancing the session."""


class WorldEngineError(VillageError):
    """The canonical Storyworld engine failed without advancing the session."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VillageError(f"cannot read JSON object from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise VillageError(f"expected a JSON object in {path}")
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


def append_jsonl_fsync(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(payload) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def validate_agent_config(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != SCHEMA:
        raise VillageError(f"agent config schema must be {SCHEMA}")
    room_id = str(payload.get("room_id") or "").strip()
    if not room_id:
        raise VillageError("room_id is required")
    agents = payload.get("agents")
    if not isinstance(agents, list) or len(agents) != 2:
        raise VillageError("phase 1 requires exactly two agents")
    ids: set[str] = set()
    normalized_agents: list[dict[str, Any]] = []
    for index, raw in enumerate(agents):
        if not isinstance(raw, dict):
            raise VillageError(f"agents[{index}] must be an object")
        agent_id = str(raw.get("id") or "").strip()
        display_name = str(raw.get("display_name") or "").strip()
        system_prompt = str(raw.get("private_system_prompt") or "").strip()
        adapter_label = str(raw.get("adapter_label") or "").strip()
        provider = raw.get("provider")
        if not agent_id or not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}", agent_id):
            raise VillageError(f"invalid agents[{index}].id")
        if agent_id in ids:
            raise VillageError(f"duplicate agent id: {agent_id}")
        if not display_name or not system_prompt or not adapter_label:
            raise VillageError(f"agent {agent_id} requires display_name, adapter_label, and private_system_prompt")
        if not isinstance(provider, dict) or provider.get("type") not in PROVIDER_TYPES:
            raise VillageError(f"agent {agent_id} has unsupported provider")
        if provider["type"] == "openai_compatible":
            base_url = str(provider.get("base_url") or "").strip().rstrip("/")
            model = str(provider.get("model") or "").strip()
            parsed = urlparse(base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or not model:
                raise VillageError(f"agent {agent_id} requires a valid base_url and model")
        ids.add(agent_id)
        normalized_agents.append(
            {
                **raw,
                "id": agent_id,
                "display_name": display_name,
                "adapter_label": adapter_label,
                "private_system_prompt": system_prompt,
                "color": str(raw.get("color") or "#d8c7ff"),
                "glyph": str(raw.get("glyph") or "✦")[:4],
                "provider": dict(provider),
            }
        )
    context_turns = int(payload.get("context_turns", 12))
    max_turns = int(payload.get("max_turns", 80))
    max_message_chars = int(payload.get("max_message_chars", 700))
    if not 1 <= context_turns <= 100:
        raise VillageError("context_turns must be between 1 and 100")
    if not 2 <= max_turns <= 1000:
        raise VillageError("max_turns must be between 2 and 1000")
    if not 80 <= max_message_chars <= 4000:
        raise VillageError("max_message_chars must be between 80 and 4000")
    normalized = {
        **{key: value for key, value in payload.items() if key != "config_hash"},
        "room_id": room_id,
        "context_turns": context_turns,
        "max_turns": max_turns,
        "max_message_chars": max_message_chars,
        "agents": normalized_agents,
    }
    normalized["config_hash"] = sha256_value(normalized)
    return normalized


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "room_id": config["room_id"],
        "context_turns": config["context_turns"],
        "max_turns": config["max_turns"],
        "agents": [
            {
                "id": agent["id"],
                "display_name": agent["display_name"],
                "color": agent["color"],
                "glyph": agent["glyph"],
                "adapter_label": agent["adapter_label"],
                "provider_type": agent["provider"]["type"],
            }
            for agent in config["agents"]
        ],
    }


class DecisionCatalog:
    """A server-owned whitelist of public decision packets."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self._packets: dict[str, dict[str, Any]] = {}
        if self.root.is_dir():
            for path in sorted(self.root.glob("*.decision.json")):
                try:
                    packet = validate_decision_packet(read_decision_object(path))
                except DecisionBridgeError as exc:
                    raise VillageError(f"invalid decision packet {path}: {exc}") from exc
                decision_id = packet["decision_id"]
                if decision_id in self._packets:
                    raise VillageError(f"duplicate decision id in catalog: {decision_id}")
                self._packets[decision_id] = packet

    def get(self, decision_id: str) -> dict[str, Any]:
        try:
            return json.loads(json.dumps(self._packets[decision_id]))
        except KeyError as exc:
            raise VillageError(f"unknown decision id: {decision_id}") from exc

    def public_index(self) -> list[dict[str, Any]]:
        return [
            {
                "decision_id": packet["decision_id"],
                "title": packet["title"],
                "location": packet["location"],
                "storyworld_id": packet["source"]["storyworld_id"],
                "option_count": len(packet["options"]),
            }
            for packet in self._packets.values()
        ]


def sanitize_topic(value: Any) -> str:
    topic = " ".join(str(value or "").split())
    if not topic:
        raise VillageError("topic is required")
    if len(topic) > 2000:
        raise VillageError("topic exceeds 2000 characters")
    return topic


def sanitize_public_message(value: Any, maximum: int) -> tuple[str, bool]:
    raw = str(value or "")
    filtered = THINK_BLOCK.sub("", raw)
    reasoning_removed = filtered != raw
    if re.search(r"<think\b", filtered, flags=re.IGNORECASE):
        raise ProviderError("provider returned an unterminated hidden-reasoning block")
    filtered = re.sub(r"```(?:json|text)?", "", filtered, flags=re.IGNORECASE).replace("```", "")
    message = " ".join(filtered.split()).strip()
    if not message:
        raise ProviderError("provider returned no public speech")
    if len(message) > maximum:
        message = message[: maximum - 1].rstrip() + "…"
    return message, reasoning_removed


def extract_proposal(value: Any, decision_packet: dict[str, Any] | None) -> tuple[str, str | None]:
    raw = str(value or "")
    matches = PROPOSAL_MARKER.findall(raw)
    without_markers = PROPOSAL_MARKER.sub("", raw)
    if decision_packet is None:
        return without_markers, None
    legal = {option["id"] for option in decision_packet["options"]}
    unique_matches = list(dict.fromkeys(matches))
    if not matches:
        raise ProviderError("decision responses require exactly one [proposal:ACTION_ID] marker")
    if len(unique_matches) != 1:
        raise ProviderError("decision response contains conflicting proposal markers")
    proposed = unique_matches[0]
    if proposed not in legal:
        raise ProviderError(f"provider proposed an illegal action: {proposed}")
    return without_markers, proposed


def render_marker_only_proposal(decision_packet: dict[str, Any], proposed_action_id: str) -> str:
    """Render a model-selected legal action when its response contains only the marker."""
    option = next(
        (entry for entry in decision_packet["options"] if entry["id"] == proposed_action_id),
        None,
    )
    if option is None:
        raise ProviderError(f"cannot render unknown proposed action: {proposed_action_id}")
    return f"I propose {option['label']}: {option['description']}"


def model_visible_decision(decision_packet: dict[str, Any] | None) -> dict[str, Any] | None:
    if decision_packet is None:
        return None
    return {
        "title": decision_packet["title"],
        "situation": decision_packet["situation"],
        "location": decision_packet["location"],
        "visible_facts": decision_packet["visible_facts"],
        "public_constraints": decision_packet["public_constraints"],
        "options": decision_packet["options"],
    }


def build_agent_messages(
    config: dict[str, Any], session: dict[str, Any], agent: dict[str, Any]
) -> list[dict[str, str]]:
    other = next(item for item in config["agents"] if item["id"] != agent["id"])
    bounded = session["transcript"][-config["context_turns"] :]
    decision_packet = session.get("decision_packet")
    engine_state = session.get("engine") if isinstance(session.get("engine"), dict) else None
    instruction = "Reply directly to the other resident with public speech only. Do not narrate hidden reasoning."
    if decision_packet is not None:
        legal = ", ".join(option["id"] for option in decision_packet["options"])
        instruction += (
            " Discuss the public decision and end with exactly one proposal marker in the form "
            f"[proposal:ACTION_ID]. Legal ACTION_ID values: {legal}."
        )
    public_context = {
        "room_id": session["room_id"],
        "topic": session["topic"],
        "turn_number": session["turn_index"] + 1,
        "you": {"id": agent["id"], "display_name": agent["display_name"]},
        "other_resident": {"id": other["id"], "display_name": other["display_name"]},
        "public_transcript": [
            {
                "turn": row["turn"],
                "speaker_id": row["speaker_id"],
                "speaker_name": row["speaker_name"],
                "message": row["message"],
            }
            for row in bounded
        ],
        "decision_packet": model_visible_decision(decision_packet),
        "current_world_state": engine_state.get("public_state") if engine_state else None,
        "public_world_history": [
            row["public_event"] for row in (engine_state.get("history", [])[-config["context_turns"] :] if engine_state else [])
        ],
        "instruction": instruction,
    }
    if bounded:
        turn_directive = (
            f"{other['display_name']} just said: {bounded[-1]['message']}\n"
            "Reply to that specific statement. Do not repeat it verbatim; add one new idea or question."
        )
    else:
        turn_directive = (
            f"Open the conversation with {other['display_name']} about the room topic. "
            "Offer one concrete idea or question."
        )
    return [
        {"role": "system", "content": agent["private_system_prompt"]},
        {
            "role": "user",
            "content": turn_directive + "\n\nPublic room state (JSON):\n" + canonical_json(public_context),
        },
    ]


def deterministic_message(agent: dict[str, Any], session: dict[str, Any]) -> str:
    topic = session["topic"]
    previous = session["transcript"][-1]["message"] if session["transcript"] else ""
    voice = str(agent["provider"].get("voice") or agent["id"])
    turn = session["turn_index"]
    decision = session.get("decision_packet")
    proposal = ""
    if decision is not None:
        options = decision["options"]
        offset = 0 if voice == "lantern" else 1
        chosen = options[(turn + offset) % len(options)]["id"]
        proposal = f" [proposal:{chosen}]"
    if voice == "lantern":
        openings = [
            "I keep seeing a bright edge to this:",
            "Let me turn that toward the light:",
            "A curious possibility just landed:",
            "I want to test one small spark:",
        ]
        questions = [
            "Which part would you try first?",
            "What would make that feel real rather than decorative?",
            "Can we name the smallest experiment?",
            "Where do you think the risk is hiding?",
        ]
        core = previous[:120] if previous else topic[:160]
        return f"{openings[turn % len(openings)]} {core} {questions[turn % len(questions)]}{proposal}"
    openings = [
        "I can give that idea some roots:",
        "Let us keep one foot on the path:",
        "There is a practical shape inside that:",
        "I hear the invitation; here is the sturdy part:",
    ]
    next_steps = [
        "We can hold the topic steady and make one reversible move.",
        "I would preserve the transcript, then compare what each of us actually changed.",
        "Let us keep the promise small enough to verify.",
        "If it fails, the failure should leave us a clean clue.",
    ]
    core = previous[:120] if previous else topic[:160]
    return f"{openings[turn % len(openings)]} {core} {next_steps[turn % len(next_steps)]}{proposal}"


def _chat_completion_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    if clean.endswith("/v1"):
        return clean + "/chat/completions"
    return clean + "/v1/chat/completions"


@dataclass(frozen=True)
class ProviderResult:
    public_message: str
    request_sha256: str
    response_sha256: str
    latency_ms: int
    reasoning_removed: bool
    proposed_action_id: str | None
    proposal_speech_synthesized: bool
    proposal_markers_deduplicated: bool


def invoke_provider(
    config: dict[str, Any], session: dict[str, Any], agent: dict[str, Any]
) -> ProviderResult:
    messages = build_agent_messages(config, session, agent)
    provider = agent["provider"]
    request_payload: dict[str, Any] = {
        "model": provider.get("model", "deterministic-demo"),
        "messages": messages,
        "temperature": 0,
        "max_tokens": int(provider.get("max_tokens", 220)),
    }
    request_hash = sha256_value(request_payload)
    started = time.perf_counter()
    if provider["type"] == "deterministic":
        raw_message = deterministic_message(agent, session)
    else:
        headers = {"Content-Type": "application/json"}
        key_name = str(provider.get("api_key_env") or "").strip()
        if key_name and os.environ.get(key_name):
            headers["Authorization"] = f"Bearer {os.environ[key_name]}"
        request = urllib.request.Request(
            _chat_completion_url(str(provider["base_url"])),
            data=canonical_json(request_payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        timeout = float(provider.get("timeout_seconds", 90))
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise ProviderError(f"{agent['display_name']} provider failed: {exc}") from exc
        try:
            raw_message = decoded["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{agent['display_name']} provider returned an invalid chat completion") from exc
    decision_packet = session.get("decision_packet")
    speech_only, proposed_action_id = extract_proposal(raw_message, decision_packet)
    proposal_markers_deduplicated = bool(
        decision_packet is not None and len(PROPOSAL_MARKER.findall(str(raw_message or ""))) > 1
    )
    proposal_speech_synthesized = False
    if decision_packet is not None and proposed_action_id is not None and not speech_only.strip():
        speech_only = render_marker_only_proposal(decision_packet, proposed_action_id)
        proposal_speech_synthesized = True
    public_message, reasoning_removed = sanitize_public_message(speech_only, config["max_message_chars"])
    latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    return ProviderResult(
        public_message=public_message,
        request_sha256=request_hash,
        response_sha256=hashlib.sha256(str(raw_message).encode("utf-8")).hexdigest(),
        latency_ms=latency_ms,
        reasoning_removed=reasoning_removed,
        proposed_action_id=proposed_action_id,
        proposal_speech_synthesized=proposal_speech_synthesized,
        proposal_markers_deduplicated=proposal_markers_deduplicated,
    )


class SessionStore:
    def __init__(self, root: Path, config_hash: str):
        self.root = root.resolve()
        self.config_hash = config_hash
        self.root.mkdir(parents=True, exist_ok=True)

    def session_dir(self, session_id: str) -> Path:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{6,80}", session_id):
            raise VillageError("invalid session id")
        return self.root / session_id

    def snapshot_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "session.json"

    def events_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "events.jsonl"

    def save(self, session: dict[str, Any]) -> None:
        atomic_json(self.snapshot_path(session["session_id"]), session)

    def append(self, session_id: str, event: dict[str, Any]) -> None:
        append_jsonl_fsync(self.events_path(session_id), event)

    def load(self, session_id: str) -> dict[str, Any]:
        path = self.snapshot_path(session_id)
        if not path.is_file():
            raise VillageError(f"unknown session: {session_id}")
        session = read_json(path)
        if session.get("config_hash") != self.config_hash:
            raise VillageError("session was created by a different agent configuration")
        # Reconcile a turn that was fsynced immediately before a crash but whose
        # atomic snapshot replacement did not complete.
        events = self.events_path(session_id)
        if events.is_file():
            rows = []
            for line in events.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
            committed = {
                int(row["turn"]["turn"]): row["turn"]
                for row in rows
                if row.get("event_type") == "turn_committed" and isinstance(row.get("turn"), dict)
            }
            attached_threads = [
                row
                for row in rows
                if row.get("event_type") == "storyworld_thread_attached"
                and isinstance(row.get("decision_packet"), dict)
            ]
            if session.get("decision_packet") is None and attached_threads:
                attached = attached_threads[-1]
                session["decision_id"] = attached["decision_id"]
                session["decision_packet"] = attached["decision_packet"]
                session["thread_attached_turn"] = int(attached["attached_at_turn"])
                session["engine_mode"] = "deliberation_only"
                session["engine"] = None
            while len(session["transcript"]) in committed:
                recovered_turn = committed[len(session["transcript"])]
                session["transcript"].append(recovered_turn)
                recovered_engine_step = recovered_turn.get("engine_step")
                if isinstance(recovered_engine_step, dict) and isinstance(session.get("engine"), dict):
                    engine_history = session["engine"].setdefault("history", [])
                    if len(engine_history) == recovered_turn["turn"]:
                        engine_history.append(recovered_engine_step)
                        public_event = recovered_engine_step.get("public_event", {})
                        session["engine"]["public_state"] = {
                            "engine_turn": public_event.get("engine_turn"),
                            "active_node": public_event.get("active_node"),
                            "location": public_event.get("location"),
                            "done": public_event.get("done"),
                            "next_turn_owner": public_event.get("next_turn_owner"),
                        }
                session["turn_index"] = len(session["transcript"])
            if len(session["transcript"]) != int(session.get("turn_index", -1)):
                raise VillageError("session transcript and turn index disagree")
        return session


class ConversationService:
    def __init__(
        self,
        config: dict[str, Any],
        runtime_root: Path,
        decision_catalog: DecisionCatalog | None = None,
        engine_bridge: StoryworldEngineBridge | None = None,
        provider_preflight: dict[str, Any] | None = None,
    ):
        self.config = validate_agent_config(config)
        self.agents = {agent["id"]: agent for agent in self.config["agents"]}
        self.store = SessionStore(runtime_root, self.config["config_hash"])
        self.decision_catalog = decision_catalog or DecisionCatalog(Path("__no_decisions__"))
        self.engine_bridge = engine_bridge
        self.provider_preflight = provider_preflight
        self._lock = threading.RLock()

    def public_configuration(self) -> dict[str, Any]:
        return {
            **public_config(self.config),
            "decisions": self.decision_catalog.public_index(),
            "storyworld_engine_ready": self.engine_bridge is not None,
            "provider_preflight_status": (self.provider_preflight or {}).get("status", "NOT_RUN"),
        }

    def create_session(
        self,
        topic: Any = None,
        *,
        decision_id: str | None = None,
        session_id: str | None = None,
        seed: int = 17,
    ) -> dict[str, Any]:
        decision_packet = self.decision_catalog.get(decision_id) if decision_id else None
        clean_topic = (
            f"{decision_packet['title']}: {decision_packet['situation']}"
            if decision_packet is not None
            else sanitize_topic(topic)
        )
        session_id = session_id or f"pv-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        with self._lock:
            if self.store.snapshot_path(session_id).exists():
                raise VillageError(f"session already exists: {session_id}")
            now = utc_now()
            engine_state = None
            if decision_packet is not None and self.engine_bridge is not None:
                try:
                    engine_state = self.engine_bridge.initialize(
                        decision_packet["decision_id"], int(seed), [agent["id"] for agent in self.config["agents"]]
                    )
                except EngineBridgeError as exc:
                    raise WorldEngineError(f"cannot initialize canonical Storyworld engine: {exc}") from exc
            session = {
                "schema_version": SESSION_SCHEMA,
                "session_id": session_id,
                "room_id": self.config["room_id"],
                "config_hash": self.config["config_hash"],
                "seed": int(seed),
                "topic": clean_topic,
                "mode": "storyworld_decision" if decision_packet is not None else "conversation",
                "decision_id": decision_packet["decision_id"] if decision_packet is not None else None,
                "decision_packet": decision_packet,
                "engine_mode": "canonical" if engine_state is not None else "deliberation_only",
                "engine": engine_state,
                "created_utc": now,
                "updated_utc": now,
                "turn_index": 0,
                "status": "open",
                "transcript": [],
            }
            event = {
                "schema_version": EVENT_SCHEMA,
                "event_type": "session_created",
                "utc": now,
                "session_id": session_id,
                "config_hash": self.config["config_hash"],
                "topic_sha256": hashlib.sha256(clean_topic.encode("utf-8")).hexdigest(),
                "decision_id": decision_packet["decision_id"] if decision_packet is not None else None,
            }
            self.store.append(session_id, event)
            self.store.save(session)
            return self.public_session(session)

    def public_session(self, session: dict[str, Any]) -> dict[str, Any]:
        next_id = None
        if session["status"] == "open" and session["turn_index"] < self.config["max_turns"]:
            next_id = self.config["agents"][session["turn_index"] % 2]["id"]
        return {
            **session,
            "next_speaker_id": next_id,
            "agents": public_config(self.config)["agents"],
        }

    def get_session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            return self.public_session(self.store.load(session_id))

    def attach_decision_thread(self, session_id: str, decision_id: str) -> dict[str, Any]:
        """Attach a public Storyworld decision to an existing conversation.

        Attachment is deliberately deliberation-only. It preserves the existing
        transcript and does not initialize or advance the canonical world engine.
        Canonical execution remains a separate, explicit experimental path.
        """
        with self._lock:
            session = self.store.load(session_id)
            if session["status"] != "open":
                raise VillageError("session is not open")
            if session.get("decision_packet") is not None:
                raise VillageError("session already has a Storyworld decision thread")
            decision_packet = self.decision_catalog.get(decision_id)
            now = utc_now()
            session["decision_id"] = decision_packet["decision_id"]
            session["decision_packet"] = decision_packet
            session["thread_attached_turn"] = session["turn_index"]
            session["engine_mode"] = "deliberation_only"
            session["engine"] = None
            session["updated_utc"] = now
            self.store.append(
                session_id,
                {
                    "schema_version": EVENT_SCHEMA,
                    "event_type": "storyworld_thread_attached",
                    "utc": now,
                    "session_id": session_id,
                    "config_hash": self.config["config_hash"],
                    "decision_id": decision_packet["decision_id"],
                    "decision_packet": decision_packet,
                    "attached_at_turn": session["turn_index"],
                    "execution_mode": "deliberation_only",
                },
            )
            self.store.save(session)
            return self.public_session(session)

    def step(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = self.store.load(session_id)
            if session["status"] != "open":
                raise VillageError("session is not open")
            if session["turn_index"] >= self.config["max_turns"]:
                session["status"] = "complete"
                session["updated_utc"] = utc_now()
                self.store.save(session)
                return self.public_session(session)
            agent = self.config["agents"][session["turn_index"] % 2]
            try:
                result = invoke_provider(self.config, session, agent)
            except ProviderError as exc:
                self.store.append(
                    session_id,
                    {
                        "schema_version": EVENT_SCHEMA,
                        "event_type": "provider_failed",
                        "utc": utc_now(),
                        "session_id": session_id,
                        "turn": session["turn_index"],
                        "speaker_id": agent["id"],
                        "error": str(exc),
                    },
                )
                raise
            next_engine_state = session.get("engine")
            engine_step = None
            if session.get("decision_packet") is not None and self.engine_bridge is not None:
                try:
                    next_engine_state = self.engine_bridge.apply(
                        session["engine"],
                        agent["id"],
                        str(result.proposed_action_id),
                        result.public_message,
                        int(session["seed"]),
                    )
                    engine_step = next_engine_state["history"][-1]
                except EngineBridgeError as exc:
                    self.store.append(
                        session_id,
                        {
                            "schema_version": EVENT_SCHEMA,
                            "event_type": "engine_failed",
                            "utc": utc_now(),
                            "session_id": session_id,
                            "turn": session["turn_index"],
                            "speaker_id": agent["id"],
                            "request_sha256": result.request_sha256,
                            "response_sha256": result.response_sha256,
                            "error": str(exc),
                        },
                    )
                    raise WorldEngineError(f"canonical Storyworld step failed: {exc}") from exc
            now = utc_now()
            turn = {
                "turn": session["turn_index"],
                "speaker_id": agent["id"],
                "speaker_name": agent["display_name"],
                "message": result.public_message,
                "utc": now,
                "provider_type": agent["provider"]["type"],
                "adapter_label": agent["adapter_label"],
                "request_sha256": result.request_sha256,
                "response_sha256": result.response_sha256,
                "latency_ms": result.latency_ms,
                "reasoning_removed": result.reasoning_removed,
                "proposed_action_id": result.proposed_action_id,
                "proposal_speech_synthesized": result.proposal_speech_synthesized,
                "proposal_markers_deduplicated": result.proposal_markers_deduplicated,
                "engine_step": engine_step,
                "world_consequence": engine_step.get("public_event") if engine_step else None,
            }
            self.store.append(
                session_id,
                {
                    "schema_version": EVENT_SCHEMA,
                    "event_type": "turn_committed",
                    "utc": now,
                    "session_id": session_id,
                    "config_hash": self.config["config_hash"],
                    "turn": turn,
                },
            )
            session["transcript"].append(turn)
            session["engine"] = next_engine_state
            session["turn_index"] += 1
            session["updated_utc"] = now
            if session["turn_index"] >= self.config["max_turns"]:
                session["status"] = "complete"
            if isinstance(next_engine_state, dict) and next_engine_state.get("public_state", {}).get("done"):
                session["status"] = "complete"
            self.store.save(session)
            return self.public_session(session)


class VillageHandler(SimpleHTTPRequestHandler):
    server_version = "PixieVillage/1.0"

    def __init__(self, *args: Any, service: ConversationService, directory: Path, **kwargs: Any):
        self.service = service
        super().__init__(*args, directory=str(directory), **kwargs)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise VillageError("invalid content length") from exc
        if length < 0 or length > 64 * 1024:
            raise VillageError("request body is too large")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VillageError("request body must be a JSON object") from exc
        if not isinstance(payload, dict):
            raise VillageError("request body must be a JSON object")
        return payload

    def _send_json(self, status: int, payload: Any) -> None:
        body = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _api_error(self, error: Exception) -> None:
        status = HTTPStatus.BAD_GATEWAY if isinstance(error, (ProviderError, WorldEngineError)) else HTTPStatus.BAD_REQUEST
        self._send_json(status, {"error": type(error).__name__, "message": str(error)})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            if path == "/api/health":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "status": "ok",
                        "room_id": self.service.config["room_id"],
                        "providers": [agent["provider"]["type"] for agent in self.service.config["agents"]],
                        "decision_count": len(self.service.decision_catalog.public_index()),
                        "storyworld_engine_ready": self.service.engine_bridge is not None,
                        "provider_preflight_status": (self.service.provider_preflight or {}).get("status", "NOT_RUN"),
                    },
                )
                return
            if path == "/api/config":
                self._send_json(HTTPStatus.OK, self.service.public_configuration())
                return
            match = re.fullmatch(r"/api/sessions/([a-zA-Z0-9_-]{6,80})(?:/export)?", path)
            if match:
                self._send_json(HTTPStatus.OK, self.service.get_session(match.group(1)))
                return
            if path.startswith("/api/"):
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "NotFound", "message": "unknown API route"})
                return
            super().do_GET()
        except VillageError as exc:
            self._api_error(exc)

    def do_POST(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        try:
            if path == "/api/sessions":
                body = self._json_body()
                self._send_json(
                    HTTPStatus.CREATED,
                    self.service.create_session(
                        body.get("topic"),
                        decision_id=str(body.get("decision_id") or "") or None,
                        seed=int(body.get("seed", 17)),
                    ),
                )
                return
            match = re.fullmatch(r"/api/sessions/([a-zA-Z0-9_-]{6,80})/step", path)
            if match:
                # Deliberately ignore any browser-supplied provider or agent routing.
                self._json_body()
                self._send_json(HTTPStatus.OK, self.service.step(match.group(1)))
                return
            match = re.fullmatch(r"/api/sessions/([a-zA-Z0-9_-]{6,80})/threads", path)
            if match:
                body = self._json_body()
                decision_id = str(body.get("decision_id") or "").strip()
                if not decision_id:
                    raise VillageError("decision_id is required")
                self._send_json(
                    HTTPStatus.OK,
                    self.service.attach_decision_thread(match.group(1), decision_id),
                )
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "NotFound", "message": "unknown API route"})
        except (VillageError, ValueError) as exc:
            self._api_error(exc if isinstance(exc, VillageError) else VillageError(str(exc)))

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{utc_now()}] {self.address_string()} {format % args}")


def configured_paths() -> tuple[Path, Path, Path, Path, Path]:
    try:
        import sys

        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from pixie_env import config_path

        return (
            config_path("lora_pixie_village_root"),
            config_path("lora_pixie_village_runtime"),
            config_path("lora_pixie_village_decisions"),
            config_path("jinn_beast_experiment_root"),
            Path(os.environ.get("PIXIE_STORYWORLD_ROOT") or config_path("storyworld_engine_root")),
        )
    except (ImportError, KeyError, TypeError, ValueError):
        return (
            APP_ROOT,
            APP_ROOT / "runtime",
            APP_ROOT / "decision_packets",
            APP_ROOT.parent / "jinn_beast_multiagent_storyworlds",
            Path(os.environ.get("PIXIE_STORYWORLD_ROOT") or APP_ROOT / "external" / "GPTStoryworld"),
        )


def make_server(
    service: ConversationService, host: str, port: int, static_root: Path
) -> ThreadingHTTPServer:
    def handler(*args: Any, **kwargs: Any) -> VillageHandler:
        return VillageHandler(*args, service=service, directory=static_root, **kwargs)

    return ThreadingHTTPServer((host, port), handler)


def build_parser() -> argparse.ArgumentParser:
    default_root, default_runtime, default_decisions, default_source_worlds, default_storyworld = configured_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", type=Path, default=default_root / "config" / "agents.example.json")
    parser.add_argument("--runtime-root", type=Path, default=default_runtime)
    parser.add_argument("--decision-root", type=Path, default=default_decisions)
    parser.add_argument("--source-world-root", type=Path, default=default_source_worlds)
    parser.add_argument("--storyworld-root", type=Path, default=default_storyworld)
    parser.add_argument("--require-adapter-attestation", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--preflight-report", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--open", action="store_true", help="open the local room in the default browser")
    parser.add_argument("--allow-network", action="store_true", help="allow a non-loopback bind explicitly")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost", "::1"} and not args.allow_network:
        raise SystemExit("refusing non-loopback bind without --allow-network")
    config = validate_agent_config(read_json(args.agents.expanduser().resolve()))
    runtime_root = args.runtime_root.expanduser().resolve()
    try:
        provider_report = preflight_providers(
            config, require_attestation=bool(args.require_adapter_attestation)
        )
    except ProviderPreflightError as exc:
        raise SystemExit(f"provider preflight failed: {exc}") from exc
    preflight_path = (
        args.preflight_report.expanduser().resolve()
        if args.preflight_report
        else runtime_root / "provider_preflight.json"
    )
    write_preflight_json(preflight_path, provider_report)
    print(f"Provider preflight: {provider_report['status']} ({preflight_path})")
    if args.preflight_only:
        print(json.dumps(provider_report, indent=2, ensure_ascii=False))
        return 0
    catalog = DecisionCatalog(args.decision_root.expanduser().resolve())
    engine_bridge = None
    try:
        engine_bridge = StoryworldEngineBridge(
            args.storyworld_root.expanduser().resolve(),
            args.source_world_root.expanduser().resolve(),
            catalog,
        )
    except EngineBridgeError as exc:
        print(f"Storyworld execution disabled: {exc}")
    service = ConversationService(
        config,
        runtime_root,
        catalog,
        engine_bridge,
        provider_preflight=provider_report,
    )
    server = make_server(service, args.host, args.port, APP_ROOT)
    url = f"http://{args.host}:{server.server_address[1]}"
    print(f"LoRA Pixie Village listening at {url}")
    print(f"Runtime sessions: {service.store.root}")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nStopping village server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
