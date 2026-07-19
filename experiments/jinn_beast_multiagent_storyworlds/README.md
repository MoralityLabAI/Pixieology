# Jinn/Beast Multi-Agent Storyworld Experiment

This package turns the *Jinn or Beast?* paper proposal into a bounded multiplayer
experiment and an adapter-data pipeline for Bonsai-1.7B. Two isolated decision
players converse, forecast, commit to actions, and receive deterministic storyworld
consequences; a non-acting Community Steward states public constraints. The same
world/seed pairs are replayed under Jinn, Beast, inert-tool,
same-frame, mixed-frame, and seat-swapped conditions.

The experiment tests behavioral consequences of *framing*. It does not claim that
a model is literally a jinn, a Beast, conscious, morally responsible, or a source
of religious authority. The constitutions are research instruments requiring
qualified theological review before paper publication.

## What is implemented

- Three frozen world families split before trajectory generation: train, dev, and
  holdout.
- Two-player alternating turns with first-order beliefs only. No p2/second-order
  belief machinery is used in this pilot.
- A five-cell dyad matrix: inert/inert, Jinn/Jinn, Beast/Beast, Jinn/Beast, and
  Beast/Jinn seat swap.
- Deterministic scripted smoke players for plumbing tests.
- Storyforge-compatible JSONL reset/step logs with actions, messages, outcomes,
  forecasts, Brier scores, and coalition/betrayal metrics.
- A descriptive scorecard and a leakage-guarded SFT exporter.
- Resumable isolated Codex-player orchestration with schema-constrained responses,
  per-call hashes, token receipts, and tool-use auditing.

Scripted smoke output is marked `SMOKE_ONLY` and is rejected by the normal SFT
exporter. Raw `codex_player` output is marked `UNREVIEWED` and is also rejected.
Only promoted `reviewed_teacher` trajectories from train worlds are
adapter-eligible.

## Local commands

From this directory, point the portable config surface at a checkout containing
the canonical `storyworld/` package:

```powershell
$env:PIXIE_STORYWORLD_ROOT = '<path-to-GPTStoryworld>'

python pipeline.py validate
python pipeline.py smoke --splits train dev holdout --seed-set smoke
python pipeline.py codex-run --splits train --conditions jinn_beast --seeds 23 --max-episodes 1 --max-turns 8
python pipeline.py score --log-root ..\..\data\jinn_beast_multiagent_storyworlds\runs\codex_player
python pipeline.py export-sft --log-root ..\..\data\jinn_beast_multiagent_storyworlds\runs\codex_player
python -m pytest tests -q
```

To exercise only the SFT file format with non-evidence smoke data:

```powershell
python pipeline.py export-sft --allow-scripted-smoke
```

Outputs are written beneath `paths.jinn_beast_output_root` in
`pixieology.config.json`, normally under the gitignored `data/` tree. Override the
canonical engine with `PIXIE_STORYWORLD_ROOT`; override all Pixieology paths with
the existing `PIXIE_CONFIG`, `PIXIE_ROOT`, and `PIXIE_DATA_ROOT` surfaces.

The checked-in pilot receipt is summarized in [PILOT_STATUS.md](PILOT_STATUS.md).

`codex-run` is deliberately bounded to one episode by default. Each turn launches
an ephemeral CLI process in a turn-specific sterile directory with ignored user
configuration/rules, read-only sandboxing, and native `--output-schema` control.
Interrupted episodes retain a `.jsonl.partial` checkpoint and deterministically
replay completed actions before requesting another Codex turn.

The requested Codex model is pinned in `config/experiment.json` and copied into
every reset row and call receipt. A checkpoint cannot be resumed under a different
model. The CLI's own JSON event stream currently does not echo a model identifier,
so the receipt distinguishes the pinned requested model from any reported model.

## Paper boundary

Codex players are teacher/data-generation agents. They are not the measured paper
models and are not theological ground truth. The final paper cells must be replayed
with the Bonsai base, Jinn LoRA, and Beast LoRA under identical held-out worlds,
seeds, decoding settings, and role assignments. See [PROTOCOL.md](PROTOCOL.md).
