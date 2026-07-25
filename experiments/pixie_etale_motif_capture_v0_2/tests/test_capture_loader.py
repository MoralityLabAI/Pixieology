from inspect import getsource

from pixie_etale_capture_v2.capture import (
    _model_load_kwargs,
    _process_private_bytes,
    _read_json_receipt,
    capture_canary_chunk,
)
from pixie_etale_capture_v2.protocol import tokenizer_template_smoke


class DummyTorch:
    float16 = "float16"


def test_model_loader_uses_verified_safetensors_and_single_gpu():
    values = _model_load_kwargs(DummyTorch, "quantization")
    assert values["use_safetensors"] is True
    assert values["device_map"] == {"": 0}
    assert values["quantization_config"] == "quantization"
    assert "offload_state_dict" not in values
    assert "low_cpu_mem_usage" not in values


def test_process_private_memory_receipt_is_available_on_windows():
    value = _process_private_bytes()
    assert value is None or value > 0


def test_receipt_reader_accepts_windows_powershell_utf8_bom(tmp_path):
    receipt = tmp_path / "resource_summary.json"
    receipt.write_text('{"status":"aborted"}', encoding="utf-8-sig")
    assert _read_json_receipt(receipt) == {"status": "aborted"}


def test_async_load_is_disabled_before_transformers_import():
    source = getsource(capture_canary_chunk)
    assert source.index('"HF_DEACTIVATE_ASYNC_LOAD": "1"') < source.index(
        "from transformers import"
    )


def test_tokenizer_template_smoke_accepts_batch_encoding_shape(monkeypatch, tmp_path):
    class DummyTokenizer:
        def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
            assert messages[0]["role"] == "user"
            assert tokenize is True
            assert add_generation_prompt is True
            return {"input_ids": [[101, 102, 103]]}

    monkeypatch.setattr(
        "transformers.AutoTokenizer.from_pretrained",
        lambda *args, **kwargs: DummyTokenizer(),
    )
    assert tokenizer_template_smoke(tmp_path) is True
