"""Assistant-only loss masking without tokenizer or chat-template mutation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Sequence

import torch


class MaskingError(ValueError):
    """Raised when an example has no usable supervised response tokens."""


def _ids(value: Any) -> list[int]:
    if isinstance(value, Mapping):
        if "input_ids" not in value:
            raise MaskingError("tokenizer mapping did not contain input_ids")
        value = value["input_ids"]
    if isinstance(value, torch.Tensor):
        return [int(item) for item in value.reshape(-1).tolist()]
    if value and isinstance(value[0], (list, tuple)):
        if len(value) != 1:
            raise MaskingError("expected one encoded chat example")
        value = value[0]
    return [int(item) for item in value]


def encode_assistant_example(
    tokenizer: Any,
    messages: Sequence[dict[str, str]],
    max_length: int,
) -> dict[str, list[int]]:
    """Encode one final-assistant chat and mask every prompt token with -100.

    When truncation is needed the left side of the prompt is discarded so the
    supervised assistant suffix is retained. The tokenizer and its chat template
    are only read; this function never adds tokens or changes tokenizer state.
    """
    if max_length < 8:
        raise MaskingError("max_length must be at least 8")
    if not messages or messages[-1].get("role") != "assistant":
        raise MaskingError("the final message must be assistant")
    prefix = _ids(tokenizer.apply_chat_template(
        list(messages[:-1]), tokenize=True, add_generation_prompt=True
    ))
    full = _ids(tokenizer.apply_chat_template(
        list(messages), tokenize=True, add_generation_prompt=False
    ))
    common = 0
    for left, right in zip(prefix, full):
        if left != right:
            break
        common += 1
    if common == len(full):
        raise MaskingError("chat template produced no assistant response tokens")
    labels = [-100] * common + full[common:]
    if len(full) > max_length:
        full = full[-max_length:]
        labels = labels[-max_length:]
    if all(label == -100 for label in labels):
        raise MaskingError("truncation removed every supervised assistant token")
    return {"input_ids": full, "attention_mask": [1] * len(full), "labels": labels}


class AssistantOnlyCollator:
    def __init__(self, pad_token_id: int):
        self.pad_token_id = int(pad_token_id)

    def __call__(self, examples: Sequence[dict[str, list[int]]]) -> dict[str, torch.Tensor]:
        width = max(len(example["input_ids"]) for example in examples)
        input_ids, masks, labels = [], [], []
        for example in examples:
            padding = width - len(example["input_ids"])
            input_ids.append(example["input_ids"] + [self.pad_token_id] * padding)
            masks.append(example["attention_mask"] + [0] * padding)
            labels.append(example["labels"] + [-100] * padding)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(masks, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }
