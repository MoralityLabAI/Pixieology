from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import webbrowser

from analysis import analyze, load_json, load_sessions


EXPERIMENT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_ROOT.parents[1]


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        suffix=".tmp",
    ) as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def verify() -> dict:
    required = [
        "README.md",
        "DESIGN_QUESTION_REGISTER.md",
        "sprint_manifest.json",
        "sprint_catalog_data.js",
        "study_tasks.js",
        "strategy_core.js",
        "index.html",
        "baseline.html",
        "triage.html",
        "study.js",
        "triage.js",
        "analysis.py",
        "scorer_manifest.json",
        "schemas/pixieology_mechinterp_ux_case_v1.schema.json",
        "schemas/pixieology_mechinterp_ux_session_v1.schema.json",
        "schemas/pixieology_mechinterp_ux_strategy_decision_v1.schema.json",
        "tests/strategy-core.test.mjs",
        "tests/page-contract.test.mjs",
        "tests/run-agent-smoke.mjs",
        "tests/test_analysis.py",
    ]
    checks = {
        f"file:{relative}": (EXPERIMENT_ROOT / relative).is_file()
        for relative in required
    }
    manifest = load_json(EXPERIMENT_ROOT / "sprint_manifest.json")
    scorer = load_json(EXPERIMENT_ROOT / "scorer_manifest.json")
    checks["manifest_schema"] = (
        manifest.get("schema") == "pixieology_mechinterp_ux_sprint_manifest_v1"
    )
    checks["scorer_schema"] = (
        scorer.get("schema") == "pixieology_mechinterp_ux_scorer_v1"
    )
    checks["baseline_commit"] = (
        manifest.get("baseline", {}).get("commit")
        == "ad48954530836109d1b20e66708990dd568ac410"
    )
    checks["no_browser_authorization"] = all(
        forbidden not in "".join(
            (EXPERIMENT_ROOT / relative).read_text(encoding="utf-8")
            for relative in ("study.js", "triage.js")
        )
        for forbidden in ("authorizeJob", "runJob", "executeJob")
    )
    checks["synthetic_fixture_boundary"] = (
        "synthetic_ux_fixture"
        in (EXPERIMENT_ROOT / "sprint_catalog_data.js").read_text(encoding="utf-8")
    )
    checks["structured_birth_epsilon"] = (
        "birthEpsilon"
        in (EXPERIMENT_ROOT / "triage.js").read_text(encoding="utf-8")
    )
    checks["fixture_spin_unavailable"] = (
        "const spinAvailable = activeCase === null"
        in (
            REPO_ROOT
            / "experiments"
            / "godel_globes_5d_character_lab"
            / "etale.js"
        ).read_text(encoding="utf-8")
    )
    return {
        "schema": "pixieology_mechinterp_ux_verification_v1",
        "ok": all(checks.values()),
        "checks": checks,
    }


def launch(port: int) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(REPO_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    relative = EXPERIMENT_ROOT.relative_to(REPO_ROOT).as_posix()
    url = f"http://127.0.0.1:{port}/{relative}/index.html"
    print(url)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify")
    launch_parser = commands.add_parser("launch")
    launch_parser.add_argument("--port", type=int, default=8765)
    analyze_parser = commands.add_parser("analyze")
    analyze_parser.add_argument("--input", type=Path, required=True)
    analyze_parser.add_argument("--output", type=Path, required=True)
    smoke_parser = commands.add_parser("agent-smoke")
    smoke_parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)

    if arguments.command == "verify":
        receipt = verify()
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0 if receipt["ok"] else 1
    if arguments.command == "launch":
        launch(arguments.port)
        return 0
    if arguments.command == "analyze":
        result = analyze(
            load_sessions(arguments.input),
            load_json(EXPERIMENT_ROOT / "sprint_manifest.json"),
            load_json(EXPERIMENT_ROOT / "scorer_manifest.json"),
        )
        atomic_json(arguments.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if arguments.command == "agent-smoke":
        completed = subprocess.run(
            [
                "node",
                str(EXPERIMENT_ROOT / "tests" / "run-agent-smoke.mjs"),
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        value = json.loads(completed.stdout)
        atomic_json(arguments.output, value)
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
