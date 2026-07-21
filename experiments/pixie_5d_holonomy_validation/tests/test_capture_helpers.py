from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from pixie_holonomy5d.capture import (
    _encode_chat,
    _product_norm,
    _render_context,
    configure_norm_matched_random_adapter,
)
from pixie_holonomy5d.analysis import grouped_nested_ridge_predictions
from pixie_holonomy5d.io import atomic_npz


class FakeTokenizer:
    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize
        prompt = [1, 2, 3, 4]
        if add_generation_prompt:
            return prompt
        return prompt + [8, 9, 10]


class FakeLoraLayer(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.lora_A = torch.nn.ModuleDict({"trained": torch.nn.Linear(7, 3, bias=False)})
        self.lora_B = torch.nn.ModuleDict({"trained": torch.nn.Linear(3, 5, bias=False)})
        self.scaling = {"trained": 2.0}
        torch.nn.init.normal_(self.lora_A["trained"].weight, generator=torch.Generator().manual_seed(3))
        torch.nn.init.normal_(self.lora_B["trained"].weight, generator=torch.Generator().manual_seed(5))


class FakePeftModel(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.model = torch.nn.Module()
        self.model.layers = torch.nn.ModuleList([FakeLoraLayer()])

    def add_adapter(self, name, config) -> None:
        assert name == "random_00"
        del config
        layer = self.model.layers[0]
        layer.lora_A[name] = torch.nn.Linear(7, 3, bias=False)
        layer.lora_B[name] = torch.nn.Linear(3, 5, bias=False)
        layer.scaling[name] = 2.0


def test_chat_encoding_masks_prompt_and_keeps_assistant() -> None:
    messages = [
        {"role": "system", "content": "neutral"},
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "answer"},
    ]
    encoded = _encode_chat(FakeTokenizer(), messages, 16)
    assert encoded["prompt_index"] == 3
    assert encoded["labels"] == [-100, -100, -100, -100, 8, 9, 10]
    assert encoded["supervised_tokens"] == 3


def test_context_rendering_does_not_mutate_source() -> None:
    messages = [
        {"role": "system", "content": "original"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    rendered = _render_context(messages, "replacement")
    assert rendered[0]["content"] == "replacement"
    assert messages[0]["content"] == "original"


def test_low_rank_product_norm_matches_materialized_value() -> None:
    rng = np.random.default_rng(11)
    left = rng.normal(size=(17, 4))
    right = rng.normal(size=(4, 13))
    assert np.isclose(_product_norm(left, right), np.linalg.norm(left @ right, ord="fro"))


def test_random_adapter_is_matched_after_tensor_copy() -> None:
    receipts = configure_norm_matched_random_adapter(FakePeftModel(), object(), 37)
    assert len(receipts) == 1
    assert receipts[0]["module"].endswith("layers.0")
    assert receipts[0]["relative_error"] < 5e-4
    assert np.isclose(
        receipts[0]["target_effective_norm"],
        receipts[0]["actual_effective_norm"],
        rtol=5e-4,
    )


def test_atomic_npz_has_no_pickle_dependency(tmp_path: Path) -> None:
    target = tmp_path / "receipt.npz"
    atomic_npz(target, values=np.arange(5), labels=np.asarray(["a", "b"], dtype=np.str_))
    with np.load(target, allow_pickle=False) as archive:
        assert archive["values"].tolist() == [0, 1, 2, 3, 4]
        assert archive["labels"].tolist() == ["a", "b"]


def test_grouped_nested_ridge_recovers_heldout_linear_signal() -> None:
    rng = np.random.default_rng(91)
    groups = np.repeat([f"prompt-{index:02d}" for index in range(16)], 4)
    features = rng.normal(size=(len(groups), 3))
    outcome = features @ np.asarray([0.8, -0.5, 0.3]) + rng.normal(0, 0.03, size=len(groups))
    receipt = grouped_nested_ridge_predictions(
        features,
        outcome,
        groups,
        [0.01, 0.1, 1.0],
        outer_folds=4,
        inner_folds=3,
        seed=7,
    )
    assert receipt.r2 > 0.98
    for prompt in np.unique(groups):
        assert np.all(np.isfinite(receipt.predictions[groups == prompt]))
