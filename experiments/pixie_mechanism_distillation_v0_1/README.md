# Pixie mechanism distillation v0.1

This experiment pivots from descriptive representation geometry to compact,
falsifiable mechanisms. It asks whether the frozen Pixie rank-8 adapter and its
frozen Qwen-derived 1.7B base admit small finite-state programs that predict
held-out activation transitions, observed outputs, and registered activation
patch interventions.

The checked-in lane is model-free and CPU-only. It can:

1. generate 32 post-training finite-state task families;
2. distill discrete programs from trace receipts;
3. discover sparse state coordinates;
4. align base and Pixie programs up to state relabeling;
5. score registered interventions against matched random controls;
6. run synthetic pipeline tests and evaluation preflight.

It cannot load a model, adapter, or activation shard. The proposed capture job
is `STAGED_NOT_AUTHORIZED` and has no automatic authorization path.

## CPU-safe commands

```powershell
python experiments\pixie_mechanism_distillation_v0_1\run.py verify
python experiments\pixie_mechanism_distillation_v0_1\run.py build-tasks `
  --output data\pixie_mechanism_distillation_v0_1\task_cases.jsonl
python experiments\pixie_mechanism_distillation_v0_1\run.py synthetic-smoke `
  --output-root data\pixie_mechanism_distillation_v0_1\synthetic
python -m pytest -q experiments\pixie_mechanism_distillation_v0_1\tests
```

After an authorized capture has produced versioned trace and intervention
receipts, the model-free analysis path is:

```powershell
python experiments\pixie_mechanism_distillation_v0_1\run.py distill `
  --traces <trace_receipts.jsonl> `
  --output-root <distilled-output>
python experiments\pixie_mechanism_distillation_v0_1\run.py compare `
  --programs <distilled-output\programs.jsonl> `
  --evaluations <distilled-output\evaluations.jsonl> `
  --interventions <intervention_observations.jsonl> `
  --output-root <comparison-output>
```

`compare` emits family receipts, counterbalanced deterministic pairwise rows,
deterministic hard-check rows, and a five-layer conclusion report suitable for
the external evaluation audit.

Run the frozen evaluation-system preflight before any inference:

```powershell
C:\projects\evals-reviewer\.venv\Scripts\evals-reviewer.exe preflight `
  experiments\pixie_mechanism_distillation_v0_1\eval_manifest.yaml `
  --policy base `
  --out data\pixie_mechanism_distillation_v0_1\preflight

C:\projects\evals-reviewer\.venv\Scripts\evals-reviewer.exe stage-robustness `
  experiments\pixie_mechanism_distillation_v0_1\robustness_spec.yaml `
  --out data\pixie_mechanism_distillation_v0_1\robustness-stage
```

## What counts as useful

A high behavioral score alone is not success. Per task family, a mechanism must
clear held-out transition fidelity, sparse-coordinate agreement, causal patch
prediction, matched-random superiority, and guardrail preservation. Pixie is
called a usable isomorphism only when a bijective state relabeling preserves at
least 90% of the extracted transition program. A shorter but non-isomorphic
program is reported as a candidate algorithm change, not an improvement.

See [PREREGISTRATION.md](PREREGISTRATION.md) for the frozen conclusion layers
and [proposed_capture_job.json](proposed_capture_job.json) for the unexecuted
model lane.
