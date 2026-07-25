# Pixie TinyLoRA / QLoRA feedback loop v0.2

This is the sealed resource continuation of v0.1. The v0.1 base-reference
attempt reached 2075.93 MiB of job memory and produced no evaluation rows under
its immutable 2048 MiB ceiling. V0.2 preserves the model, Pixie adapter,
semantic-group transfer split, metrics, thresholds, and seeds while
preregistering an 8192 MiB process-tree ceiling and a PrimeLab cgroup-v2
execution path.

This staged experiment turns confirmed étale motifs into bounded adapter jobs. It compares four conditions on one frozen Qwen-derived Bonsai 1.7B checkpoint:

1. adapter-disabled base;
2. the existing Pixie rank-8 adapter;
3. motif-local TinyLoRA;
4. all-layer QLoRA.

Using the identical base for all four conditions is the causal contrast. Calling an unrelated “vanilla Qwen” checkpoint the baseline would mix adapter effects with checkpoint and data effects.

## What the loop does

`propose` always creates base and Pixie transfer-evaluation jobs. Once a registered activation catalog and its frozen discovery motif model exist, it also selects at most two origins: one robust, bridge-free local convergence and one fragile chained convergence. Each origin receives:

- a rank-2 TinyLoRA confined to the origin’s sheet component and chart layers; and
- a rank-4 QLoRA over all seven registered LoRA module types and all 28 layers.

Both methods train for 20 optimizer steps on the same outcome-eligible discovery rows. Confirmation and transfer rows are forbidden from training. Candidate success requires held-out behavioral improvement and a separate post-training topology receipt; topology alone is never success.

The explorer publishes the immutable proposal queue through `window.PixieEtaleExplorer`. Humans and agents can inspect and select a job, but the browser cannot authorize or launch it.

## Commands

```powershell
python experiments/pixie_lora_feedback_loop_v0_2/run.py verify
python experiments/pixie_lora_feedback_loop_v0_2/run.py propose `
  --output data/pixie_lora_feedback_loop_v0_2/proposed_jobs.json
```

With confirmed artifacts:

```powershell
python experiments/pixie_lora_feedback_loop_v0_2/run.py propose `
  --catalog path/to/confirmed_catalog.json `
  --model path/to/frozen_motif_model.json `
  --output data/pixie_lora_feedback_loop_v0_2/proposed_jobs.json
```

Extract a proposed job, generate its fail-closed authorization template, and have a human make that receipt active outside the UI:

```powershell
python experiments/pixie_lora_feedback_loop_v0_2/run.py extract-job `
  --queue data/pixie_lora_feedback_loop_v0_2/proposed_jobs.json `
  --job-id evaluate-base_qwen_derived_1p7b `
  --output data/pixie_lora_feedback_loop_v0_2/base-job.json

python experiments/pixie_lora_feedback_loop_v0_2/run.py authorization-template `
  --job data/pixie_lora_feedback_loop_v0_2/base-job.json
```

The supported execution paths are `scripts/run_capped_feedback.ps1` on Windows
and `scripts/run_capped_feedback_prime.sh` on a dedicated PrimeLab pod. The
PrimeLab path validates an exact-job authorization, requires an idle single
GPU, applies cgroup-v2 memory/CPU/I/O caps before the Python process starts,
monitors the 3900 MiB VRAM guard, and cleans only the attempt-owned cgroup.

No training or evaluation run is authorized by this repository state. The 8
GiB continuation is a requested hard ceiling, not permission to create a paid
pod or load a model. A structured memory, spot-interruption, timeout, or GPU
guard abort remains a valid result.

## PrimeLab handoff envelope

The amended operator lane is bound to one RTX A6000 48 GB pod, at most USD
0.70/hour, at most two hours, and no concurrent local GPU workload. The
available offer is on-demand; evaluation still appends one durable JSONL
checkpoint per completed transfer row. The protected hosted RL run
`e2s64hw5ywag1d8hgwfef6jd` must remain untouched. The exact pod ID is recorded
before staging; artifacts are copied and hashed before that same pod is
terminated.

## Agent surface

The browser contract adds:

- `getJobQueue()` — immutable queue and safety boundary;
- `listJobs()` — compact proposal summaries;
- `getJob(jobId)` — full hash-bound job;
- `selectJob(jobId)` — UI selection only;
- `getSelectedJob()` — current selection or `null`.

The shared URI uses `?job=<job_id>`. Selection changes inspection state only. There is deliberately no `authorize`, `run`, or free-form command method.

## Claim boundary

This is a discovery loop for whether topology-conditioned adapter placement predicts useful held-out changes. It is not evidence that étale motifs are causal by themselves, a license to train on confirmation or transfer rows, or a claim that a zero adapter is a geometric null.
