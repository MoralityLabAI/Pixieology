# Holonomy-informed 5D spin category

## Source review

The design was checked against the newest public papers in the local Morality
Lab site and their RSITopology source reports. Hashes bind the exact copies
reviewed on 2026-07-21.

| Source | SHA-256 |
|---|---|
| `Holonomy_Mechinterp.pdf` | `116ebc98f3aa8b1d106a1873e25c8f54f2d432074509c0f8e713bc7d83689ba3` |
| `Holonomy_Precision.pdf` | `d5b2a3c9f845916dfe58a00756b1d0bb2107ef1e7de3156b076beda6f8cc6152` |
| `QWEN08_PRECISION_GEOMETRY_PAPER_V0_1.md` | `fd5f58ec1579bf96db4007c6ed0c2208689f205b78ab61c8d0da8fba47bdb0bf` |
| `PERCOLATION_PHASE_CODEX_PROMPT.md` | `0881806d30ebd0d0024e6dee8372bb562aae3c069275552c2b690c2f7e07cf30` |
| `PERCOLATION_PHASE_PILOT_V0_1.md` | `0c82a6b465e05d9319cb2947caec328e4f1b5539664d188f30bdab62dfbb3807` |

The imported result is the rank-one liveness theorem. For edge retention
`r_e`, the projective angle is

```text
alpha_e = arccos(sqrt(r_e)).
```

Negative shortest-geodesic rank-one holonomy around a cycle requires

```text
sum_e alpha_e >= pi.
```

The cycle frustration margin is therefore

```text
F(C) = pi - sum_e alpha_e.
```

A positive margin forces the sign to `+1`; it does not provide new evidence of
orientability. A non-positive margin only makes a negative sign possible. It
does not guarantee one. This distinction corrects the tempting but invalid
interpretation that every observed positive loop is evidence of coherence.

## Five-dimensional mapping

The first four coordinates retain the existing Pixie parameter-state geometry:

1. `X`: depth-normalized effective LoRA update energy;
2. `Y`: singular-spectrum top-mode share;
3. `Z`: effective rank;
4. `W`: transformer depth;
5. `S`: a cycle-level spin/liveness category.

`S` belongs to cycles, not individual nodes. The explorer constructs a
two-module ladder across all 28 layers. Its selected trace is paired with a
target from the opposite transformer family, producing depth rails and
cross-family rungs. A finite-graph cycle basis is calculated after applying
the lineage-proxy floor `tau`.

The fifth coordinate distinguishes:

| Category | Meaning |
|---|---|
| disconnected | No globally transportable node graph. |
| holonomy unavailable | The graph has no admitted cycle basis. |
| forced positive | `w1` is trivial, but every measured angle budget is below `pi`; positivity was forced. |
| live positive | At least one cycle can geometrically support either sign, but the synthetic gauge syndrome remains positive. |
| frustrated live | A negative synthetic cycle occurs where its angle budget is at least `pi`. |
| synthetic negative below liveness | The independent sign-noise model produced a negative cycle that cannot be interpreted as shortest-geodesic rank-one holonomy at the displayed proxy retentions. |

The independent edge-spin rate `q` is deterministic and counterfactual. It is
useful for exploring the `Z/2` gauge categories, coboundary distance, and their
non-monotonic finite-graph behavior. The UI reports the gauge phase separately
from the liveness category so an abstract spin defect is never silently
promoted to geometrically realizable holonomy.

## Claim boundary

The LoRA atlas contains exact parameter-delta SVD summaries, but it does not
contain cross-fitted activation bases, polar transports, estimator-noise nulls,
or measured edge signs. The displayed retention

```text
r_proxy = exp(-0.55 * squared_distance(X, Y, Z))
```

is explicitly a visualization proxy. The spin field is synthetic. Consequently
the 5D view is a faithful instrument demonstration and category design, not a
claim that the Pixie 1.7B model has measured nontrivial holonomy.

The Qwen0.8B precision result - including the reported 23.54 degree erosion of
the layer-19 frustration margin - is not pooled with Pixie. A real Pixie
holonomy experiment must first harvest fresh activation bases, pass support and
common-rank lineage gates, seal a cycle universe, measure polar transports, and
apply the liveness/noise certificate before interpreting the fifth coordinate.
