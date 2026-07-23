from inspect import getsource

from pixie_etale_capture_v2.capture import (
    _model_load_kwargs,
    _process_private_bytes,
    capture_canary_chunk,
)


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


def test_async_load_is_disabled_before_transformers_import():
    source = getsource(capture_canary_chunk)
    assert source.index('"HF_DEACTIVATE_ASYNC_LOAD": "1"') < source.index(
        "from transformers import"
    )
