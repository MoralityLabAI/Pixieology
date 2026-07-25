import json
from inspect import getsource

from pixie_etale_capture_v3.capture import (
    CaptureV3Error,
    _checkpoint_is_resumable,
    _model_load_kwargs,
    _process_private_bytes,
    _read_json_receipt,
    _select_continuation,
    capture_continuation,
)
from pixie_etale_capture_v3.protocol import sha256_file, tokenizer_template_smoke


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
    source = getsource(capture_continuation)
    assert source.index('"HF_DEACTIVATE_ASYNC_LOAD": "1"') < source.index(
        "from transformers import"
    )


def test_continuation_selection_requires_ordered_family_chunks_and_splits():
    families = ["style", "copy", "format", "fact", "math"]
    rows = [
        {
            "id": f"row-{index:03d}",
            "family": "canary" if index < 32 else families[(index - 32) // 32],
            "split": (
                "discovery"
                if index % 32 < 16
                else "confirmation"
                if index % 32 < 24
                else "transfer"
            ),
        }
        for index in range(192)
    ]
    job = {
        "row_start": 32,
        "row_count": 160,
        "families": families,
        "splits": {"discovery": 80, "confirmation": 40, "transfer": 40},
    }
    assert _select_continuation(rows, job, 32) == rows[32:]
    rows[96]["family"] = "wrong"
    try:
        _select_continuation(rows, job, 32)
    except CaptureV3Error as error:
        assert "mixes families" in str(error)
    else:
        raise AssertionError("mixed-family continuation was accepted")


def test_resume_marker_is_bound_to_artifact_rows_job_and_protocol(tmp_path):
    artifact = tmp_path / "rows_032_039.npz"
    artifact.write_bytes(b"checkpoint")
    marker = artifact.with_suffix(".complete.json")
    value = {
        "schema": "pixieology_etale_capture_checkpoint_v3",
        "capture_protocol_sha256": "a" * 64,
        "job_sha256": "b" * 64,
        "row_ids": [f"row-{index:03d}" for index in range(32, 40)],
        "artifact_sha256": sha256_file(artifact),
    }
    marker.write_text(json.dumps(value), encoding="utf-8")
    assert _checkpoint_is_resumable(
        marker,
        artifact,
        capture_protocol_sha256="a" * 64,
        job_sha256="b" * 64,
        row_ids=value["row_ids"],
    )
    assert not _checkpoint_is_resumable(
        marker,
        artifact,
        capture_protocol_sha256="a" * 64,
        job_sha256="c" * 64,
        row_ids=value["row_ids"],
    )
    artifact.write_bytes(b"tampered")
    assert not _checkpoint_is_resumable(
        marker,
        artifact,
        capture_protocol_sha256="a" * 64,
        job_sha256="b" * 64,
        row_ids=value["row_ids"],
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
