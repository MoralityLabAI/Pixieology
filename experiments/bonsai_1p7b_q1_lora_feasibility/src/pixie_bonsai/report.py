"""Evidence-only acceptance matrix and go/no-go report generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ExperimentConfig, project_root
from .reporting import layout, utc_now, write_json


def _read(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _status(condition: bool | None) -> str:
    return "NOT RUN" if condition is None else ("PASS" if condition else "FAIL")


def _metric_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def generate_report(config: ExperimentConfig, run_name: str = "smoke-v1") -> dict[str, Any]:
    paths = layout(config)
    run = paths.runs / run_name
    hardware = _read(paths.artifacts / "hardware.json")
    preflight = _read(paths.artifacts / "preflight" / "preflight_result.json")
    probe = _read(paths.artifacts / "memory_probe.json")
    step20 = _read(run / "process_result_step_000020.json")
    step30 = _read(run / "process_result_step_000030.json")
    hf = _read(run / "hf_evaluation.json")
    conversion = _read(run / "conversion.json")
    q1 = _read(run / "q1_evaluation.json")
    offline = _read(run / "offline_evaluation.json")
    bundle = _read(paths.artifacts / "bundle_result.json")
    step10 = _read(run / "process_result_step_000010.json")
    abort30 = _read(run / "abort_step_000030.json")
    readme = (project_root() / "README.md").read_text(encoding="utf-8")
    offline_access_confirmed = None
    if offline is not None:
        offline_access_confirmed = offline.get("offline_access_confirmed")
        if offline_access_confirmed is None:
            offline_q1_adapter = offline.get("q1", {}).get("modes", {}).get("D_q1_adapter", {})
            offline_q1_base = offline.get("q1", {}).get("modes", {}).get("C_q1_base", {})
            offline_access_confirmed = bool(offline.get("hf", {}).get("offline")) and bool(
                offline_q1_base.get("rows")
            ) and bool(offline_q1_adapter.get("rows")) and bool(offline_q1_adapter.get("adapter_load_confirmed"))
    values: list[tuple[str, bool | None, str]] = [
        ("RTX 3050 detected", None if hardware is None else bool(hardware.get("checks", {}).get("rtx_3050_detected")), "hardware.json"),
        ("Bonsai-1.7B 4-bit base loads", None if preflight is None else preflight.get("zero_adapter", {}).get("status") == "PASS", "preflight zero-adapter creation"),
        ("All-linear LoRA attaches", None if preflight is None else preflight.get("zero_adapter", {}).get("adapter", {}).get("target_module_count") == 196, "196 Qwen3 linear targets"),
        ("One all-linear backward step fits", None if probe is None else probe.get("status") == "PASS", "memory_probe.json"),
        ("Peak VRAM measured", None if probe is None else bool(probe.get("selected", {}).get("probe", {}).get("peak_allocated_bytes")), "CUDA peak counters"),
        ("Interrupted training resumes", None if step20 is None else bool(step20.get("resume_observed")) and step20.get("global_step") == 20, "fresh process resumed to step 20"),
        (
            "PEFT adapter changes held-out behavior",
            None if hf is None else (
                hf["modes"]["B_hf_adapter"]["scores"]["canary_hits"] > hf["modes"]["A_hf_base"]["scores"]["canary_hits"]
                or hf["modes"]["B_hf_adapter"]["scores"]["marker_hits"] > hf["modes"]["A_hf_base"]["scores"]["marker_hits"]
            ),
            "A versus B",
        ),
        ("Untrained PEFT adapter converts to GGUF", None if preflight is None else preflight.get("conversion", {}).get("status") == "PASS", "zero adapter conversion"),
        ("Untrained GGUF adapter loads on Q1_0 base", None if preflight is None else preflight.get("runtime", {}).get("status") == "PASS", "zero adapter runtime test"),
        ("Trained PEFT adapter converts to GGUF", None if conversion is None else conversion.get("status") == "PASS", "trained conversion"),
        ("Trained GGUF adapter loads on Q1_0 base", None if q1 is None else bool(q1.get("modes", {}).get("D_q1_adapter", {}).get("adapter_load_confirmed")), "D server log"),
        ("Adapter behavior survives on Q1_0", None if q1 is None else bool(q1.get("behavior_survived")), "C versus D and B versus D"),
        ("Offline evaluation works", offline_access_confirmed, "HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE"),
        ("Portable bundle created", None if bundle is None else bundle.get("status") == "PASS" and Path(bundle.get("bundle_path", "")).is_file(), "model-weight-free ZIP"),
        ("Exact reproduction commands documented", "smoke-all" in readme and "run_capped.ps1" in readme, "README.md"),
    ]
    acceptance = [{"item": index, "check": name, "status": _status(value), "evidence": evidence} for index, (name, value, evidence) in enumerate(values, 1)]
    statuses = [row["status"] for row in acceptance]
    if all(status == "PASS" for status in statuses):
        color = "GREEN"
    elif probe and probe.get("status") == "FAIL":
        color = "RED"
    elif step30 and hf and hf.get("status") == "FAIL":
        color = "RED"
    elif probe and probe.get("status") == "PASS" and hf and hf.get("status") == "PASS" and (conversion and conversion.get("status") != "PASS" or q1 and q1.get("status") != "PASS"):
        color = "YELLOW"
    else:
        color = "NOT RUN"
    metrics = _metric_rows(run / "metrics.jsonl")
    process_wall = sum(
        float(item.get("wall_seconds_this_process", 0.0))
        for item in (step10, step20, step30) if item
    ) + (float(abort30.get("elapsed_seconds", 0.0)) if abort30 else 0.0)
    selected = probe.get("selected") if probe else None
    report = {
        "schema_version": 1, "created_utc": utc_now(), "decision": color,
        "acceptance_matrix": acceptance,
        "actual_vram_mib": hardware.get("gpu", {}).get("total_vram_mib") if hardware else None,
        "selected_training": selected,
        "training": step30,
        "metrics_summary": {
            "optimizer_steps_logged": len(metrics),
            "mean_step_seconds": sum(row["step_seconds"] for row in metrics) / len(metrics) if metrics else None,
            "total_logged_step_seconds": sum(row["step_seconds"] for row in metrics) if metrics else None,
            "total_process_wall_seconds_including_aborted_attempt": process_wall or None,
            "last_loss": metrics[-1]["loss"] if metrics else None,
        },
        "hf_scores": {key: value["scores"] for key, value in hf.get("modes", {}).items()} if hf else None,
        "q1_scores": {key: value["scores"] for key, value in q1.get("modes", {}).items()} if q1 else None,
        "q1_adapter_load_confirmed": q1.get("modes", {}).get("D_q1_adapter", {}).get("adapter_load_confirmed") if q1 else None,
        "q1_detectable_canary_transfer": (
            q1["modes"]["D_q1_adapter"]["scores"]["canary_hits"]
            > q1["modes"]["C_q1_base"]["scores"]["canary_hits"]
        ) if q1 else None,
        "offline_access_confirmed": offline_access_confirmed,
        "bundle": bundle,
        "aborted_attempt": abort30,
    }
    write_json(paths.reports / "feasibility_report.json", report)
    lines = [
        "# Bonsai 1.7B QLoRA-to-Q1 LoRA feasibility", "", f"Decision: **{color}**", "",
        f"Generated: {report['created_utc']}", "", "## Acceptance matrix", "",
        "| # | Check | Status | Evidence |", "|---:|---|---|---|",
    ]
    for row in acceptance:
        lines.append(f"| {row['item']} | {row['check']} | {row['status']} | {row['evidence']} |")
    lines.extend(["", "## Measured run", ""])
    lines.append(f"- RTX 3050 VRAM: {report['actual_vram_mib'] if report['actual_vram_mib'] is not None else 'NOT RUN'} MiB")
    lines.append(
        "- Selected QLoRA profile: "
        + (f"rank `{selected['rank']}`, sequence `{selected['sequence_length']}`, gradient accumulation `{selected['gradient_accumulation_steps']}`" if selected else "`NOT RUN`")
    )
    lines.append(f"- Peak allocated VRAM: `{selected.get('probe', {}).get('peak_allocated_bytes') if selected else 'NOT RUN'}` bytes")
    lines.append(f"- Mean optimizer-step time: `{report['metrics_summary']['mean_step_seconds']}` seconds")
    lines.append(f"- Total capped training-process time, including the recovered OOM: `{report['metrics_summary']['total_process_wall_seconds_including_aborted_attempt']}` seconds")
    lines.append(f"- Final adapter: `{step30.get('adapter_path') if step30 else 'NOT RUN'}`")
    lines.append(f"- Resume observed: `{step20.get('resume_observed') if step20 else 'NOT RUN'}`")
    lines.append(f"- PEFT-to-GGUF: `{conversion.get('status') if conversion else 'NOT RUN'}`")
    lines.append(f"- Q1 strict behavioral gate: `{q1.get('status') if q1 else 'NOT RUN'}`")
    lines.append(f"- Q1 adapter load confirmed: `{report['q1_adapter_load_confirmed'] if q1 else 'NOT RUN'}`")
    lines.append(f"- Q1 detectable canary transfer: `{report['q1_detectable_canary_transfer'] if q1 else 'NOT RUN'}`")
    lines.append(f"- Forced-offline execution confirmed: `{report['offline_access_confirmed'] if offline else 'NOT RUN'}`")
    lines.append(f"- Portable bundle: `{bundle.get('bundle_path') if bundle else 'NOT RUN'}`")
    if hf:
        a = hf["modes"]["A_hf_base"]["scores"]
        b = hf["modes"]["B_hf_adapter"]["scores"]
        lines.extend([
            "", "## Behavioral gate", "",
            "| Mode | Canary exact | `sproutlight` marker |", "|---|---:|---:|",
            f"| A: HF 4-bit base | {a['canary_hits']}/{a['canary_total']} | {a['marker_hits']}/{a['marker_total']} |",
            f"| B: HF 4-bit + PEFT | {b['canary_hits']}/{b['canary_total']} | {b['marker_hits']}/{b['marker_total']} |",
            "",
        ])
        if hf.get("status") != "PASS" and not conversion and not q1:
            lines.append("The predeclared 6/8 + 6/8 gate failed, so trained-adapter GGUF conversion, native Q1 behavioral evaluation, and offline replay were not run. The zero-adapter conversion/load preflight did pass independently.")
        elif hf.get("status") != "PASS" and conversion and q1:
            c = q1["modes"]["C_q1_base"]["scores"]
            d = q1["modes"]["D_q1_adapter"]["scores"]
            lines.extend([
                "The predeclared 6/8 canary + 6/8 style-marker gate still fails; the overall decision therefore remains RED.",
                "A post-gate deployment diagnostic was run without weakening that threshold: the trained PEFT adapter converted to GGUF, loaded separately with `--lora`, and moved native Q1_0 canary accuracy "
                f"from {c['canary_hits']}/{c['canary_total']} to {d['canary_hits']}/{d['canary_total']}. This is a detectable transport signal, not acceptance of the personality recipe.",
            ])
    if abort30:
        lines.extend([
            "", "## Recovered interruption", "",
            f"The first 20-to-30 process aborted after `{abort30.get('elapsed_seconds')}` seconds with `{abort30.get('error')}`. It resumed from the last atomic checkpoint and completed; post-checkpoint metrics from the abandoned attempt are retained separately.",
        ])
    lines.extend(["", "## Reproduction", "", "```powershell", "python -m pixie_bonsai.cli doctor", "python -m pixie_bonsai.cli smoke-all", "```", ""])
    markdown = "\n".join(lines)
    (paths.reports / "FEASIBILITY_REPORT.md").write_text(markdown, encoding="utf-8")
    (project_root() / "FEASIBILITY_REPORT.md").write_text(markdown, encoding="utf-8")
    return report
