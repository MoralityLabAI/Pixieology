from inspect import getsource
from pathlib import Path

from pixie_bnb_canary_v3.canary import (
    _process_private_bytes,
    _read_json_receipt,
    run_canary,
)


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]


def test_canary_source_has_no_model_or_adapter_loader():
    source = getsource(run_canary)
    assert "from_pretrained" not in source
    assert "transformers" not in source
    assert "peft" not in source


def test_canary_checkpoints_each_projection_operation():
    source = getsource(run_canary)
    assert "for layer_index" in source
    assert "for projection" in source
    resident = source.index("resident.append(parameter)")
    assert resident < source.index("_checkpoint(", resident)


def test_wrapper_uses_registered_hard_caps():
    source = (EXPERIMENT_ROOT / "scripts" / "run_capped_canary_v3.ps1").read_text(
        encoding="utf-8"
    )
    assert "-MemoryMB 2048" in source
    assert "-CpuPercent 50" in source
    assert "-IoMBPerSecond 50" in source
    assert "-TimeoutSeconds 600" in source
    assert "maximum_existing_memory_mib" in source


def test_receipt_reader_accepts_windows_bom(tmp_path):
    receipt = tmp_path / "resource_summary.json"
    receipt.write_text('{"status":"aborted"}', encoding="utf-8-sig")
    assert _read_json_receipt(receipt) == {"status": "aborted"}


def test_process_private_receipt_is_optional_or_positive():
    value = _process_private_bytes()
    assert value is None or value > 0
