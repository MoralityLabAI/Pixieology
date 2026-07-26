# Mechinterp UX strategy sprint v0.1

This isolated, offline study resolves workflow questions around the Pixie
locally-glued explorer without altering the registered motif-search or capture
experiments. The researcher benchmark is case-to-intervention triage. A
secondary learner lane checks terminology and unsupported-claim risk.

The sprint compares the current dense explorer layout with a progressive
workflow:

1. identify the evidence class and case;
2. orient across depth;
3. inspect direct edges versus closure;
4. judge chain and bridge robustness;
5. inspect an allowed next job or the explicit no-job state.

All included cases are marked `synthetic_ux_fixture`. They test interaction and
scoring mechanics only. They are not activation evidence, motifs, causal
circuits, or human-learning evidence.

## Run

```powershell
python experiments/mechinterp_ux_strategy_sprint_v0_1/run.py verify
python experiments/mechinterp_ux_strategy_sprint_v0_1/run.py launch
```

Open the workflow or component lane, use anonymous participant codes, complete
all tasks, and export the JSON receipt. Put completed receipts in an untracked
directory, then analyze them:

```powershell
python experiments/mechinterp_ux_strategy_sprint_v0_1/run.py analyze `
  --input <receipt-directory> `
  --output <decision.json>
```

The browser stores no network data and has no authorization or execution
surface. Preference is recorded only as secondary context.

## Validate

The fixture, page, scorer, and original étale contracts have deterministic
tests:

```powershell
node --test `
  experiments/mechinterp_ux_strategy_sprint_v0_1/tests/strategy-core.test.mjs `
  experiments/mechinterp_ux_strategy_sprint_v0_1/tests/page-contract.test.mjs
python -m pytest `
  experiments/mechinterp_ux_strategy_sprint_v0_1/tests/test_analysis.py -q
node --test `
  experiments/godel_globes_5d_character_lab/tests/etale.test.mjs `
  experiments/godel_globes_5d_character_lab/tests/etale-page.test.mjs
```

The agent smoke answers the same eight workflow tasks from structured topology
fields, without parsing SVG geometry and without a browser authorization
method:

```powershell
python experiments/mechinterp_ux_strategy_sprint_v0_1/run.py agent-smoke `
  --output <agent-smoke-receipt.json>
```

Passing this smoke establishes machine readability only. It is not human UX or
model-motif evidence.

## Decision outputs

The analyzer emits separate workflow, component, learner, and agent verdicts.
Progressive triage is promoted only when the registered researcher accuracy,
time, unsupported-claim, job-choice, and sample gates all pass. Component
comparisons keep the conservative default unless a complete participant panel
produces a decisive accuracy or time advantage without worse claim discipline.

## Evidence boundary

The small panel produces a formative workflow decision. It cannot satisfy the
registered motif craft or learning gates. Once a real catalog is confirmed,
the existing 12-participant paired craft study and 32-participant learning
study remain required.
