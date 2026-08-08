# A proven information addition for action-sensitive mechinterp UX

## Result

The **reachability certificate lens** is a mathematically strict addition to a passive manifold view. It exposes information that no passive state-trajectory rendering can recover in general: the dimension and energy geometry of states reachable by interventions.

This is a theorem about the visualization contract, not an empirical claim about Pixie or Qwen.

## Setup

Consider the local discrete-time linearization

\[
x_{t+1}=Ax_t+Bu_t,
\]

where `x` is a low-dimensional mechanism coordinate and `u` is a registered intervention. At horizon `H`, define the reachability matrix and finite-horizon controllability Gramian

\[
C_H=[B,AB,\ldots,A^{H-1}B],\qquad W_H=C_HC_H^\top.
\]

The existing passive view `P` contains trajectories generated with `u=0`. The added view `R` contains `rank(W_H)`, the eigendirections of `W_H`, and the corresponding reachable-set geometry.

## Theorem 1: the lens exactly encodes reachable dimension

For the system above,

\[
\dim(\mathcal R_H)=\operatorname{rank}(C_H)=\operatorname{rank}(W_H),
\]

where `R_H` is the subspace reachable from the origin in at most `H` steps.

### Proof

Every horizon-`H` endpoint from the origin is `C_H v` for a stacked control vector `v`, up to a reversal of the columns that does not change their span. Therefore `R_H = image(C_H)` and its dimension is `rank(C_H)`. For any real matrix `C`, `null(C Cᵀ)=null(Cᵀ)` because

\[
z^\top CC^\top z=\lVert C^\top z\rVert^2.
\]

Thus `rank(CCᵀ)=rank(C)`, proving the equality. Moreover, the unit-control-energy endpoint set is the ellipsoid `C_H {v: ||v||≤1}`. Its support, axes, and squared axis lengths are respectively `image(W_H)`, the eigenvectors of `W_H`, and its nonzero eigenvalues. The displayed certificate is therefore not a proxy for local controllability; it is its exact finite-horizon linear certificate. ∎

## Theorem 2: adding the certificate never removes information

Let `M` be a finite-valued mechanism hypothesis, `P` the existing passive visualization, and `R` the reachability certificate. Then

\[
I(M;P,R)-I(M;P)=I(M;R\mid P)\ge 0.
\]

Equality holds exactly when `M` and `R` are conditionally independent given `P`. This follows from the chain rule for mutual information and non-negativity of conditional mutual information. The claim is representation-independent: adding the certificate cannot reduce the information available to an ideal reader, although a poor interface could still raise human cognitive cost.

## Theorem 3: the addition is strict, not merely non-negative

Take two systems with the same passive dynamics

\[
A=\begin{bmatrix}1&0\\0&2\end{bmatrix},
\]

but different intervention Jacobians

\[
B_1=\begin{bmatrix}1\\0\end{bmatrix},\qquad
B_2=\begin{bmatrix}1\\1\end{bmatrix}.
\]

Because `A` is identical, all passive trajectories from the same initial state are identical. At `H=2`, however,

\[
C_1=\begin{bmatrix}1&1\\0&0\end{bmatrix},\quad
W_1=\begin{bmatrix}2&0\\0&0\end{bmatrix},\quad
\operatorname{rank}(W_1)=1,
\]

while

\[
C_2=\begin{bmatrix}1&1\\1&2\end{bmatrix},\quad
W_2=\begin{bmatrix}2&3\\3&5\end{bmatrix},\quad
\det(W_2)=1,\quad \operatorname{rank}(W_2)=2.
\]

Under a uniform prior over these two mechanism hypotheses, `P` is constant, so it identifies neither system and `I(M;P)=0`. The displayed rank is `1` or `2`, so it identifies the system exactly and `I(M;P,R)=1 bit`. Hence

\[
I(M;R\mid P)=1\text{ bit}>0.
\]

This exact witness proves that the reachability lens strictly refines the passive visualization partition.

## What this adds to the portfolio

The earlier manifold, étale, and holonomy views describe state organization and transport. The reachability certificate answers a different question: **which local directions can a registered action actually move, within a stated horizon and energy budget?**

The lens earns a place in the UX portfolio because it carries:

1. a sufficient statistic for finite-horizon reachable dimension;
2. an exact geometric rendering of local intervention energy;
3. a strict indistinguishability witness against passive views;
4. a bounded agent-readable proof receipt.

For a neural model, `A` must come from a measured local transition Jacobian and `B` from a registered intervention Jacobian. Without those measurements, the UI may demonstrate the theorem but must not report model controllability.

## Experimental status

The exact addition was subsequently confirmed on a separate 256-pair generated ensemble in `../reachability_information_gain_v0_1/`: passive accuracy 50%, certificate accuracy 100%, and conditional information gain one bit. The seed-held-out confirmation audit accepted the claim with complete deterministic coverage. Its noise sweep does not extend the exact theorem; instead it establishes the UX requirement to expose singular-value margin and estimator uncertainty before using the certificate on measured neural Jacobians.
