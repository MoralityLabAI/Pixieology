from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import multi_adapter_compare as compare  # noqa: E402
import multi_adapter_matrix  # noqa: E402


MATRIX_PATH = APP_ROOT / "config" / "multi_adapter_matrix_v1.json"


def identities(matrix: dict) -> dict[str, dict]:
    routes = multi_adapter_matrix.build_routes(
        matrix, [Path("companion.gguf"), Path("storyworld.gguf")], ["a" * 64, "b" * 64]
    )
    return {
        route["label"]: {
            "matrix_id": matrix["matrix_id"],
            "adapter_label": route["label"],
            "model_alias": route["model_alias"],
            "adapter_sha256": route["adapter_sha256"],
            "combination_sha256": route["combination_sha256"],
            "selection": {"request_lora": route["lora_scales"]},
        }
        for route in routes.values()
    }


def test_compare_runs_complete_matrix_and_fsyncs_raw_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    matrix = multi_adapter_matrix.load_matrix(MATRIX_PATH)
    identity_by_label = identities(matrix)

    def fake_request(url: str, *, payload=None, timeout=240):
        if url.endswith("/v1/models"):
            return {"data": [{"id": row["model_alias"]} for row in matrix["conditions"]]}
        if "/pixie/identity/" in url:
            return identity_by_label[url.rsplit("/", 1)[-1]]
        model = payload["model"]
        prompt = payload["messages"][-1]["content"]
        suffix = " [proposal:propose]" if "marker" in prompt else ""
        return {"choices": [{"message": {"content": f"{model} answer{suffix}"}}]}

    monkeypatch.setattr(compare, "request_json", fake_request)
    output = tmp_path / "compare"
    receipt = compare.run_compare("http://127.0.0.1:1", matrix, output)
    assert receipt["status"] == "PASS"
    assert all(receipt["assertions"].values())
    rows = (output / "raw_generations.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 8
    assert receipt["behavior_signals"]["stacked_differs_from_base"] == {
        "neutral_introduction": True,
        "public_decision": True,
    }


def test_identity_rejects_scale_mismatch() -> None:
    matrix = multi_adapter_matrix.load_matrix(MATRIX_PATH)
    condition = matrix["conditions"][-1]
    identity = identities(matrix)["stacked"]
    identity["selection"]["request_lora"][0]["scale"] = 0.0
    with pytest.raises(compare.CompareError, match="scales mismatch"):
        compare.validate_identity(identity, matrix, condition)


def test_resource_finalizer_fails_closed_and_hashes_receipts(tmp_path: Path) -> None:
    pointer_path = tmp_path / "pointer.json"
    summary_path = tmp_path / "summary.json"
    cleanup_path = tmp_path / "cleanup.json"
    pointer_path.write_text(
        json.dumps({"schema_version": "pixie_multi_adapter_compare_pointer_v1", "status": "PASS"}),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps({"cap_verified": True, "cap_breached": False, "caps": {}, "peak_job_memory_bytes": 10}),
        encoding="utf-8-sig",
    )
    cleanup_path.write_text(
        json.dumps({"cleanup_passed": True, "lingering_owned_pids": [], "owned_pids": [7]}),
        encoding="utf-8",
    )
    finalized = compare.finalize_resource_attestation(pointer_path, summary_path, cleanup_path)
    assert finalized["status"] == "PASS"
    assert all(finalized["resource_attestation"]["assertions"].values())
    cleanup_path.write_text(
        json.dumps({"cleanup_passed": False, "lingering_owned_pids": [7]}), encoding="utf-8"
    )
    failed = compare.finalize_resource_attestation(pointer_path, summary_path, cleanup_path)
    assert failed["status"] == "FAIL"
