from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import streaming_qwen3_convert as streaming  # noqa: E402


class QType(Enum):
    F32 = 0
    BF16 = 1
    F16 = 2


FAKE_GGUF = SimpleNamespace(GGMLQuantizationType=QType)


def test_raw_bf16_bytes_preserve_bits_without_copy() -> None:
    values = torch.tensor([[1.0, -2.5], [0.125, 9.0]], dtype=torch.bfloat16)
    raw = streaming.raw_bf16_bytes(values)
    expected = values.view(torch.uint8).numpy()
    assert raw.dtype == np.uint8
    assert raw.shape == (2, 4)
    assert raw.tobytes() == expected.tobytes()
    assert raw.__array_interface__["data"][0] == values.data_ptr()


def test_raw_bf16_bytes_reject_non_bf16() -> None:
    with pytest.raises(streaming.StreamingConversionError, match="expected BF16"):
        streaming.raw_bf16_bytes(torch.ones((2, 2), dtype=torch.float16))


@pytest.mark.parametrize(
    ("n_dims", "name", "forced", "expected"),
    [
        (1, "blk.0.attn_norm.weight", False, QType.F32),
        (2, "blk.0.attn_norm.weight", False, QType.F32),
        (2, "blk.0.attn_q.weight", False, QType.BF16),
        (2, "blk.0.attn_q.weight", True, QType.BF16),
        (2, "blk.0.attn_q.weight", QType.F16, QType.F16),
    ],
)
def test_output_qtype_is_narrow_and_deterministic(
    n_dims: int, name: str, forced: object, expected: QType
) -> None:
    assert streaming.output_qtype(n_dims=n_dims, new_name=name, forced=forced, gguf=FAKE_GGUF) == expected
