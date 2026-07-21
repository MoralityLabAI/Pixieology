# Preregistration: Pixie 5D manifold predictive validation v0.1

Date frozen for staging: 2026-07-21

Status: `STAGED_NOT_AUTHORIZED`. No real-model outcomes have been consumed.

## Research question

Does a five-coordinate activation manifold - spatial adapter response, spectral
time, and rooted spin, with gauge-invariant holonomy category as color - predict
held-out Pixie adapter behavior better than simpler depth and parameter-energy
descriptions?

## Candidate object

For prompt `p`, context `c`, and layer `l`, capture the final non-padding-token
residual state with and without the trained adapter and define

```text
delta_h[p,c,l] = h_adapter[p,c,l] - h_base[p,c,l].
```

At each `(c,l)`, fit a rank-8 SVD on construction prompts only. Align the first
three local coordinates to context zero using polar transport along the frozen
tree `0-1-2-3`. These aligned coordinates are `X,Y,Z`.

Spectral time is the cumulative energy filtration

```text
T_k = sum(i <= k, sigma_i^2) / sum(i <= 8, sigma_i^2), k=1..8.
```

The rank-one behavior-family direction is fitted independently from the
canary-versus-style mean contrast. Its rooted transport determinant is `S`.
`S` is gauge-covariant and must always carry the root/path receipt.

The registered context loop is `0 -> 1 -> 2 -> 3 -> 0`. Its polar-product
conjugacy class supplies color. At rank one, color must distinguish:

- unavailable;
- forced positive (`sum alpha < pi`);
- live positive (`sum alpha >= pi`, sign positive);
- frustrated (`sum alpha >= pi`, sign negative);
- invalid/noise-dominated.

No positive sign below the liveness bound is evidence of coherence.

## Data and splits

The frozen source is the original Bonsai feasibility corpus:

- 48 training records: geometry construction and validation only;
- 16 held-out evaluation records: behavioral outcome only;
- two balanced families: canary and style;
- four frozen context renderings;
- zero prompt ID overlap between construction and outcome splits.

The outcome is adapter-minus-base mean teacher-forced log-likelihood of the
held-out expected assistant completion. Canary exact generation and
`sproutlight` frequency are secondary descriptive outcomes.

## Sites and controls

Primary sites: transformer layers `[5, 13, 21, 27]`.

Conditions:

1. trained Pixie adapter;
2. zero adapter;
3. one independently seeded, per-module effective-delta-norm-matched random
   adapter for every primary site analysis;
4. nineteen norm-matched random controls only if the trained condition becomes
   a finalist under the frozen gates.

The random controls match each module's effective update norm
`||(alpha/r) B A||_F`, not merely adapter file size or global norm.

## Hypotheses

### H1 - Representation existence

At least two of four sites will support the rank-one canary-versus-style object
at all four contexts. Support requires

```text
q05(cross-fit bootstrap retention)
  - q95(label-permutation retention) > 0.02.
```

Use 256 deterministic bootstrap and 256 label-permutation replicates.

### H2 - Five-coordinate predictive value

On held-out prompts, grouped cross-validation by prompt ID will show

```text
R2(XYZTS + holonomy color) - R2(depth + parameter energy) >= 0.05.
```

The paired stratified-bootstrap 95% lower bound must exceed zero. Bootstrap
count: 10,000; strata: behavior family and context.

### H3 - Incremental spin/holonomy value

Both increments must be reported separately:

```text
R2(XYZTS) - R2(XYZT) >= 0.02
R2(full + color) - R2(XYZTS) >= 0.02.
```

Failure of the second gate is not converted into evidence for holonomy.

### H4 - Trained-adapter specificity

Utility is frozen as `out-of-fold R2(full) - out-of-fold R2(depth + parameter
energy)`. The trained utility must exceed the median norm-matched-random utility
by at least `0.05`. A condition is a finalist when H1, H2, the spin increment,
and H5 pass; color need not pass for the `SPIN_INCREMENTAL` result. For a
finalist, the empirical random-control p-value is

```text
(1 + controls_with_utility_at_least_trained) / 20.
```

### H5 - Gauge and liveness integrity

Across 256 deterministic independent node-frame reframings:

- every loop determinant sign and liveness category must be bit-identical;
- rooted spins may transform only according to the recorded gauge convention;
- forced-positive loops must never be labeled empirical coherence.

Any failure is `GEOMETRY_INTEGRITY_FAIL` and stops interpretation.

## Baselines and ablations

Fit the same frozen ridge family and grouped folds to:

1. depth + parameter Frobenius energy;
2. `XYZ`;
3. `XYZT`;
4. `XYZTS`;
5. `XYZTS` plus holonomy color.

Ridge penalties are `[0.01, 0.1, 1, 10]`, selected only inside training folds.
No neural predictor or post-result feature engineering is allowed.

## Decision rule

- `HOLONOMY_INCREMENTAL`: H1-H5 pass.
- `SPIN_INCREMENTAL`: H1, H2, spin part of H3, H4, H5 pass; color increment fails.
- `GEOMETRY_NONPREDICTIVE`: H1 passes but H2 fails.
- `LINEAGE_ONLY`: support passes somewhere but the full loop/noise gates do not.
- `NO_SUPPORTED_OBJECT`: H1 fails.
- `INTEGRITY_FAIL`: leakage, protocol, gauge, liveness, or cleanup gate fails.

No threshold may be changed after real capture begins. Negative and unavailable
results are primary outcomes.

## Claim boundary

This experiment can test local predictive value of one frozen canary adapter on
one Bonsai 1.7B checkpoint. It cannot establish semantic identity, a universal
persona manifold, causal edit safety, deployment readiness, or that holonomy is
useful for other adapters or models.
