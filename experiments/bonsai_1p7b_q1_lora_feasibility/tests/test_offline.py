from __future__ import annotations

import json
from types import SimpleNamespace

from pixie_bonsai import eval_gguf, eval_hf


def test_offline_execution_is_separate_from_behavioral_gate(monkeypatch, tmp_path) -> None:
    """A weak adapter is not evidence that cached/offline execution failed."""
    monkeypatch.setattr(eval_hf, "require_resource_cap", lambda: None)
    monkeypatch.setattr(eval_hf, "layout", lambda _config: SimpleNamespace(runs=tmp_path))
    monkeypatch.setattr(
        eval_hf,
        "evaluate_hf",
        lambda _config, _run_name: {"status": "FAIL", "offline": True, "modes": {}},
    )
    monkeypatch.setattr(
        eval_gguf,
        "evaluate_q1",
        lambda _config, _run_name: {
            "status": "FAIL",
            "modes": {
                "C_q1_base": {"rows": [{"id": "base"}]},
                "D_q1_adapter": {
                    "rows": [{"id": "adapter"}],
                    "adapter_load_confirmed": True,
                },
            },
        },
    )

    result = eval_hf.offline_evaluation(object(), "test-run")

    assert result["status"] == "PASS"
    assert result["offline_access_confirmed"] is True
    assert result["behavioral_gate_status"] == "FAIL"
    receipt = json.loads((tmp_path / "test-run" / "offline_evaluation.json").read_text(encoding="utf-8"))
    assert receipt["offline_access_confirmed"] is True
