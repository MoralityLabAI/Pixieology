# Pixie 5D holonomy validation

This is a preregistered feasibility experiment for the proposed Pixie manifold:

```text
(X, Y, Z, T, S) with holonomy category as color
```

It tests whether that representation predicts held-out adapter behavior better
than depth and weight-norm baselines. It does not treat a compelling picture as
evidence.

The frozen candidate interpretation is:

- `X,Y,Z`: the first three adapter-induced activation coordinates, aligned to a
  rooted context frame by polar transport;
- `T`: cumulative spectral-energy time as singular modes are admitted;
- `S`: rooted orientation spin (`+1` or `-1`), which is gauge-covariant and is
  never interpreted without its root convention;
- color: gauge-invariant loop holonomy category, including the rank-one
  liveness distinction between forced and live signs.

The primary real capture uses the exact cached Bonsai 1.7B revision and trained
rank-8 Pixie canary adapter. Four prompt contexts form a registered context
cycle. Geometry is built from the checked-in training prompts; behavioral
scoring uses the disjoint checked-in evaluation prompts.

## Current state

`STAGED_NOT_AUTHORIZED`: protocol, source hashes, geometry implementation,
synthetic controls, real-capture code, frozen analysis, tests, doctor, and
dry-run are ready. No model was loaded by this experiment.
The RTX 3050 capture needs explicit authorization for the requested hard cap:

```text
RAM 6144 MB, CPU 50%, I/O 250 MB/s, timeout 1800 s
```

Until that authorization exists, only CPU-safe commands may run.

## Commands

From the repository root:

```powershell
python experiments\pixie_5d_holonomy_validation\run.py verify
python experiments\pixie_5d_holonomy_validation\run.py doctor
python experiments\pixie_5d_holonomy_validation\run.py smoke
python experiments\pixie_5d_holonomy_validation\run.py readiness
python experiments\pixie_5d_holonomy_validation\run.py authorization-template
```

The template deliberately has `authorized: false`. After explicit human
authorization, bind a receipt to its printed protocol hash, fill `run_id`,
`issued_by`, and `issued_at_utc`, and set `authorized: true`. No authorization
receipt is checked into the repository. A direct Python capture is rejected;
the supported launch path is the hash-pinned Windows Job Object wrapper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  experiments\pixie_5d_holonomy_validation\scripts\run_capped_capture.ps1 `
  -Authorization <receipt.json>

powershell -NoProfile -ExecutionPolicy Bypass -File `
  experiments\pixie_5d_holonomy_validation\scripts\run_capped_analysis.ps1 `
  -RunId <run_id>
```

Generated captures, controls, logs, and reports go through
`paths.pixie_5d_holonomy_output_root` and are ignored by Git.

The primary capture measures the trained adapter, an exact zero control, and
one independently seeded random adapter whose effective update norm is matched
module-by-module. It checkpoints after each of the four contexts. The analysis
uses only the 48 construction prompts to fit geometry, then predicts the 16
held-out teacher-forced likelihood gains with nested prompt-grouped folds and
10,000 stratified bootstrap replicates. If a spin or holonomy result becomes a
finalist, it remains explicitly provisional until the registered 19-control
inference follow-up is completed.

## What constitutes evidence

The experiment is informative even when it fails. Valid terminal outcomes are:

- `NO_SUPPORTED_OBJECT`: adapter-induced activation coordinates do not survive
  the support/null gate;
- `LINEAGE_ONLY`: local objects exist but the registered context loop is absent
  or noise-dominated;
- `GEOMETRY_NONPREDICTIVE`: the 5D representation exists but does not improve
  held-out prediction;
- `SPIN_INCREMENTAL`: spin adds predictive value but holonomy color does not;
- `HOLONOMY_INCREMENTAL`: the full representation clears every preregistered
  incremental and control gate.

See `prereg.md` for the estimands and `TRAINER_PLAN.md` for cap enforcement,
chunking, checkpointing, abort semantics, and cleanup.
