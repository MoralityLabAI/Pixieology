# Portfolio information audit: what is genuinely new?

## Audited baseline

The comparison class is the checked-in Pixieology visualization portfolio before the reachability certificate was added:

- 5D globe and étale views: state coordinates, depth-indexed sheets, local equivalence, chaining, branching/merging diagnostics, and categorical overlap certificates;
- holonomy study: loop-sensitive transport proxies where a closed base is available;
- mechanism-law lab: clustered states, finite-state transitions, symbolic candidates, and intervention-result staging;
- six-paper observatory: wiring geometry, algorithmic phases, compilation, sparse invariants, and validation routing.

A repository search outside the new observatory found no implementation of a controllability Gramian, reachability matrix, reachable-subspace rank, or registered intervention Jacobian. Existing intervention plans specify comparisons but do not encode the finite-horizon action image.

## Information fields by view family

| View family | Passive state organization | Path/transition structure | Registered action Jacobian `B` | Reachable dimension | Unit-energy action geometry |
|---|---:|---:|---:|---:|---:|
| Globe / étale | yes | local overlap only | no | no | no |
| Holonomy proxy | yes | closed-loop transport | no | no | no |
| Mechanism-law lab | yes | FSM transitions | intervention outcomes only | no | no |
| Six paper lenses | yes | phase/compiler/invariant views | no | no | no |
| **Reachability certificate** | yes | local linear transition `A` | **yes** | **exactly `rank(W_H)`** | **exactly the image of the action-energy ball** |

## Why this is not redundant with holonomy

Holonomy asks whether transporting state around a closed loop returns an object unchanged. Reachability asks which directions registered actions can produce from a local state within a horizon and energy budget. Curvature can be nonzero in an uncontrollable direction, and a fully controllable local system can live on a contractible base with no nontrivial loop. Neither statistic determines the other.

## Proof of strict addition

The exact witness in `CONTROL_INFORMATION_THEOREM.md` holds `A` fixed and changes only `B`. Consequently every portfolio surface that factors solely through passive trajectories receives identical input for the two systems. The new certificate returns ranks one and two. Under the declared uniform prior this reduces mechanism entropy from one bit to zero, so its conditional information contribution is exactly one bit.

This establishes a strict addition to the audited passive/action-unspecified portfolio. It does **not** assert one bit of gain for arbitrary neural-model data. For model use, the prior, measurement noise, Jacobian estimates, and finite-sample uncertainty must be registered and reported.

## Admission decision

**Admit the reachability certificate to the portfolio.** It passes three gates:

1. **non-redundancy:** no audited surface contains its sufficient statistic;
2. **mathematical semantics:** the displayed rank and ellipsoid exactly represent finite-horizon linear reachability;
3. **strict witness:** a pair indistinguishable to passive views becomes perfectly distinguishable.

The next empirical gate is a model-derived local `(A,B)` pair with held-out intervention endpoints. Until that gate passes, the lens is a proven UX primitive with a synthetic witness—not evidence that a particular neural mechanism is controllable.
