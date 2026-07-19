"""Verifiers 0.2.0 adapter for Fae Bench v2 grounding metrics.

Install ``fae-bench[verifiers]`` in the cloud runtime. Local grounding scoring
does not import Verifiers and remains dependency-light.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import verifiers.v1 as vf

from fae_bench.grounding import score_grounding


class GroundingBenchData(vf.TaskData):
    response: str = ""
    episode_id: str
    record_id: str
    fact_list: list[dict[str, Any]]
    window: list[dict[str, Any]]
    mode: Literal["fae", "plain"] = "fae"
    condition: str = "chronicle_narration"
    split: str | None = None


class GroundingBenchTask(vf.Task[GroundingBenchData]):
    def _record(self, trace: vf.Trace) -> dict[str, Any]:
        return {
            "episode_id": self.data.episode_id,
            "record_id": self.data.record_id,
            "fact_list": self.data.fact_list,
            "window": self.data.window,
            "narration": trace.last_reply,
        }

    @vf.reward(weight=1.0)
    async def grounding_reward(self, trace: vf.Trace) -> float:
        return score_grounding(self._record(trace)).reward()

    @vf.metric
    async def grounding_metrics(self, trace: vf.Trace) -> dict[str, float]:
        return score_grounding(self._record(trace)).metrics()


class GroundingBenchConfig(vf.TasksetConfig):
    records_path: str
    split: Literal["all", "train", "val", "holdout"] = "all"
    episode_id: str | None = None
    limit: int | None = None


class GroundingBenchTaskset(vf.Taskset[GroundingBenchTask, GroundingBenchConfig]):
    """Load Pixie chronicle env rows without rewriting their evidence fields."""

    def load(self) -> list[GroundingBenchTask]:
        path = Path(self.config.records_path).expanduser()
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if self.config.split != "all":
            rows = [row for row in rows if row.get("split") == self.config.split]
        if self.config.episode_id is not None:
            rows = [row for row in rows if row.get("episode_id") == self.config.episode_id]
        if self.config.limit is not None:
            if self.config.limit < 0:
                raise ValueError("limit must be non-negative")
            rows = rows[: self.config.limit]
        tasks: list[GroundingBenchTask] = []
        for row in rows:
            prompt = row.get("prompt") or row.get("state_prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("grounding env row needs prompt or state_prompt")
            data = GroundingBenchData(
                prompt=prompt,
                episode_id=row["episode_id"],
                record_id=row.get("record_id") or row["trajectory_id"],
                fact_list=row["fact_list"],
                window=row.get("window", []),
                mode=row.get("mode", "fae"),
                condition=row.get("condition", "chronicle_narration"),
                split=row.get("split"),
            )
            tasks.append(GroundingBenchTask(data, self.config.task))
        return tasks
