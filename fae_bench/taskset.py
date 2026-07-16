"""Verifiers 0.2.0 adapter for Fae Bench v1.

Install the optional ``fae-bench[verifiers]`` dependency in the cloud runtime.
The deterministic scoring module does not import Verifiers and remains usable
on platforms where the rollout stack is unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import verifiers.v1 as vf

from fae_bench.scoring import score_record


class FaeBenchData(vf.TaskData):
    response: str = ""
    mode: Literal["fae", "plain"]
    condition: str


class FaeBenchTask(vf.Task[FaeBenchData]):
    def _record(self, trace: vf.Trace) -> dict[str, str]:
        return {
            "prompt": self.data.prompt,
            "response": trace.last_reply,
            "mode": self.data.mode,
            "condition": self.data.condition,
        }

    @vf.reward(weight=1.0)
    async def fae_bench_reward(self, trace: vf.Trace) -> float:
        score = score_record(self._record(trace))
        return score.reward(self.data.mode)

    @vf.metric
    async def fae_bench_metrics(self, trace: vf.Trace) -> dict[str, float]:
        return score_record(self._record(trace)).metrics()


class FaeBenchConfig(vf.TasksetConfig):
    records_path: str = "data/fae_bench_eval.jsonl"
    mode: Literal["all", "fae", "plain"] = "all"
    condition: str | None = None
    limit: int | None = None


class FaeBenchTaskset(vf.Taskset[FaeBenchTask, FaeBenchConfig]):
    def load(self) -> list[FaeBenchTask]:
        path = Path(self.config.records_path).expanduser()
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        selected = [row for row in rows if self.config.mode == "all" or row.get("mode") == self.config.mode]
        if self.config.condition is not None:
            selected = [row for row in selected if row.get("condition") == self.config.condition]
        if self.config.limit is not None:
            if self.config.limit < 0:
                raise ValueError("limit must be non-negative")
            selected = selected[: self.config.limit]
        return [FaeBenchTask(FaeBenchData(**row), self.config.task) for row in selected]
