# Reachability information-gain experiment v0.1

## Frozen claim

For paired two-dimensional systems sharing the same passive dynamics `A` and initial state but having different registered intervention Jacobians `B`, the reachability-certificate view will identify the two-step controllability class exactly while a passive-only view cannot exceed balanced chance. On the frozen paired ensemble this must produce:

- passive decoder accuracy: exactly `0.5`;
- certificate decoder accuracy: exactly `1.0`;
- conditional information gain: exactly `1 bit`;
- coordinate-change rank invariance: `1.0`;
- passive identity leaks: `0`.

Any failure rejects the exact claim. Thresholds are not changed after outcomes.

## Independent unit

One item is one generated pair. Each item receives:

1. a distinct integer-eigenvalue matrix `A=P diag(λ1,λ2) P⁻¹`, with integer unimodular `P`;
2. an initial state `x0`;
3. a rank-one actuator `B_low=p1` aligned with an eigenvector;
4. a rank-two actuator `B_full=p1+p2` combining both eigenvectors.

At horizon two, `C=[B,AB]`. Therefore the first system has rank one and the second rank two. Candidate order is counterbalanced across items.

## Blinded observation contracts

The passive condition receives only `A` and the `u=0` trajectory. The two candidates within an item receive byte-identical passive observations; candidate labels are anonymous. Its frozen decoder chooses displayed candidate `A`, giving exactly half correct under counterbalancing.

The certificate condition receives `C`, `W=CCᵀ`, and the normalized singular-value ratio. Its frozen exact decoder selects the candidate with rank two.

The row-level logs separately retain oracle `B` for verification. Oracle fields are never serialized into passive observations. View display order is seeded and randomized with exactly 128 presentations in each orientation. Ties are allowed by contract, although the exact conditional-entropy rule has a strict one-bit difference on every valid item.

## Information calculation

Every passive signature occurs twice, once with each balanced class. Thus `H(Y|P)=1 bit`. Reachability rank is a deterministic bijection to the two labels, so `H(Y|P,R)=0`. The measured conditional information addition is their difference.

## Robustness suite

The exact theorem concerns exact `A` and `B`. A separate pre-registered robustness sweep adds Gaussian noise to `B` and reports:

- pair-identification accuracy from the larger normalized singular-value ratio;
- candidate classification accuracy using threshold `σ_min(C)/σ_max(C) ≥ 0.001`.

Noise outcomes cannot rescue or overturn the exact decision. They specify when an empirical neural-model estimate needs an uncertainty display or abstention band.

## Coordinate invariance

Each system is transformed by a second deterministic unimodular coordinate change `S`: `A′=SAS⁻¹`, `B′=SB`. The rank certificate must remain unchanged. The Gramian matrix itself is coordinate-dependent, so the experiment claims invariance only for reachable dimension, not raw entries or Euclidean ellipse appearance.

## Conclusion layers

The report must keep separate:

1. metric robustness under registered coordinate/noise probes;
2. exact task result on the frozen items;
3. measurement reliability and leakage checks;
4. support for the declared synthetic control-view claim;
5. operational admission to the UX portfolio;
6. the still-unmet model-facing gate: measured `(A,B)` and held-out intervention endpoints.

## Preflight repair history

The first preflight ran before decoder outcomes and blocked on underspecified contamination status, display randomization, tie handling, and generic deterministic coverage. The repaired manifest declares the completed generator-isolation check, seeded balanced randomization, allowable ties, and explicit schema/task-completion predicates. Both preflight reports are retained.

## Development audit and confirmation

The development run met all exact experiment rules, but the generic evaluation audit returned `targeted_rerun`: the passive candidate lacked one globally declared deterministic row, deterministic-judge repeat/position metrics were not instantiated, cross-judge kappa was inapplicable but declared required, and a generic `1.0` win threshold could not be cleared by a finite-sample Wilson lower bound.

Those audit semantics are repaired only in `manifest_confirmation.yaml`, before generating confirmation outcomes. The confirmation run uses a new seed (`20260809`), a separate dataset and result directory, both display orientations with two exact repetitions, complete candidate/check coverage, `cross_judge_required: false`, and a generic audit threshold of `0.98`. The scientific exact requirements remain unchanged at passive `0.5`, certificate `1.0`, and information gain `1 bit`.
