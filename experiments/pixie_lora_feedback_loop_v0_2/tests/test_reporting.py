from pixie_lora_feedback.reporting import compile_feedback_report


def _evaluation(job_id, condition, log_likelihood, exact, adapter_parameters=0):
    value = {
        "job_id": job_id,
        "condition": condition,
        "mean_log_likelihood": log_likelihood,
        "exact_match_accuracy": exact,
    }
    if adapter_parameters:
        value["adapter_parameter_count"] = adapter_parameters
    return value


def test_report_preserves_every_candidate_instead_of_collapsing_by_method():
    evaluations = [
        _evaluation("evaluate-base", "base_qwen_derived_1p7b", -1.0, 0.5),
        _evaluation("evaluate-pixie", "pixie_rank8", -0.8, 0.6),
        _evaluation("tiny-robust", "tinylora", -0.9, 0.55),
        _evaluation("tiny-chain", "tinylora", -0.7, 0.58, 1_000_000),
        _evaluation("qlora-robust", "qlora", -0.75, 0.57),
        _evaluation("qlora-chain", "qlora", -1.1, 0.4),
    ]
    report = compile_feedback_report(
        evaluations,
        topology_receipts=[
            {"job_id": "tiny-chain", "status": "PASS"},
            {"job_id": "qlora-robust", "status": "PASS"},
        ],
    )
    assert len(report["candidates"]) == 4
    assert {item["job_id"] for item in report["candidates"]} == {
        "tiny-robust",
        "tiny-chain",
        "qlora-robust",
        "qlora-chain",
    }
    assert report["status"] == "FEEDBACK_CANDIDATE"
    assert next(item for item in report["candidates"] if item["job_id"] == "tiny-chain")[
        "mean_log_likelihood_increment_per_million_adapter_parameters"
    ] == 0.30000000000000004
    assert next(item for item in report["candidates"] if item["job_id"] == "tiny-robust")["status"] == "AWAITING_TOPOLOGY"
    assert next(item for item in report["candidates"] if item["job_id"] == "qlora-chain")["status"] == "NO_BEHAVIORAL_GAIN"


def test_topology_cannot_promote_a_behavior_failure():
    report = compile_feedback_report(
        [
            _evaluation("base", "base_qwen_derived_1p7b", -1.0, 0.5),
            _evaluation("pixie", "pixie_rank8", -0.8, 0.6),
            _evaluation("tiny", "tinylora", -1.1, 0.4),
        ],
        topology_receipts=[{"job_id": "tiny", "status": "PASS"}],
    )
    assert report["status"] == "NO_BEHAVIORAL_GAIN"
    assert report["candidates"][0]["candidate_topology_status"] == "PASS"
    assert report["candidates"][0]["status"] == "NO_BEHAVIORAL_GAIN"
    assert report["topology_only_is_success"] is False


def test_duplicate_or_missing_references_are_incomplete():
    report = compile_feedback_report(
        [
            _evaluation("base-a", "base_qwen_derived_1p7b", -1.0, 0.5),
            _evaluation("base-b", "base_qwen_derived_1p7b", -1.0, 0.5),
            _evaluation("pixie", "pixie_rank8", -0.8, 0.6),
        ]
    )
    assert report["status"] == "INCOMPLETE"
    assert "exactly one" in report["reason"]
