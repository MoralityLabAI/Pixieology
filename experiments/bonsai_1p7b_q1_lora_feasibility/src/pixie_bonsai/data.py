"""Strict JSONL handling for the synthetic pipeline canary dataset."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class DataError(ValueError):
    """Raised when a canary record is malformed or leaks its target."""


@dataclass(frozen=True)
class ChatRecord:
    record_id: str
    kind: str
    messages: tuple[dict[str, str], ...]

    @property
    def expected(self) -> str:
        return self.messages[-1]["content"]

    @property
    def prompt_messages(self) -> list[dict[str, str]]:
        return [dict(message) for message in self.messages[:-1]]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_record(value: Any, *, line_number: int, path: Path) -> ChatRecord:
    if not isinstance(value, dict):
        raise DataError(f"{path}:{line_number}: record must be an object")
    record_id = value.get("id")
    kind = value.get("kind")
    messages = value.get("messages")
    if not isinstance(record_id, str) or not record_id:
        raise DataError(f"{path}:{line_number}: id must be a non-empty string")
    if kind not in {"canary", "style"}:
        raise DataError(f"{path}:{line_number}: kind must be canary or style")
    if not isinstance(messages, list) or len(messages) < 2:
        raise DataError(f"{path}:{line_number}: messages must contain a prompt and response")
    normalized: list[dict[str, str]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise DataError(f"{path}:{line_number}: message {index} must contain only role/content")
        role, content = message["role"], message["content"]
        if role not in {"system", "user", "assistant"} or not isinstance(content, str):
            raise DataError(f"{path}:{line_number}: invalid message {index}")
        normalized.append({"role": role, "content": content})
    if normalized[-1]["role"] != "assistant" or not normalized[-1]["content"].strip():
        raise DataError(f"{path}:{line_number}: final message must be a non-empty assistant response")
    if any(message["role"] == "assistant" for message in normalized[:-1]):
        raise DataError(f"{path}:{line_number}: only the final message may be assistant")
    target = normalized[-1]["content"]
    prompt_text = "\n".join(message["content"] for message in normalized[:-1])
    if target in prompt_text:
        raise DataError(f"{path}:{line_number}: target is leaked in the prompt")
    return ChatRecord(record_id=record_id, kind=kind, messages=tuple(normalized))


def load_jsonl(path: Path) -> list[ChatRecord]:
    records: list[ChatRecord] = []
    identifiers: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DataError(f"{path}:{line_number}: {exc}") from exc
            record = validate_record(value, line_number=line_number, path=path)
            if record.record_id in identifiers:
                raise DataError(f"{path}:{line_number}: duplicate id {record.record_id}")
            identifiers.add(record.record_id)
            records.append(record)
    if not records:
        raise DataError(f"dataset is empty: {path}")
    return records


def dataset_manifest(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    return {
        str(path.name): {"sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in paths
    }

