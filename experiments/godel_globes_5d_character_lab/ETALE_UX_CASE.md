# UX case: locally glued mechanistic sheets

## Decision

Keep the Gödel Globe as the global, embodied orientation surface and use the
locally glued explorer for exact mechanistic comparison. The explorer is not a
second decorative projection. It is the evidence view for the data shape that is
actually present: one ordered base (`W`, transformer depth), seven persistent LoRA
target identities, three continuous section coordinates (`X/Y/Z`), and an
overlap-level categorical certificate (`S`).

## User problem

A 5D globe, grand tour, or other moving projection is useful for discovering
global shape, but it entangles coordinates at the moment a user needs an exact
answer:

- Which targets are locally similar at this depth?
- Is the similarity direct or only produced by a chain of intermediate targets?
- Where does that relationship begin, end, merge, split, or rewire?
- Which spin/liveness certificate applies to the comparison?
- Is the conclusion measured, derived, synthetic, or unavailable?

The locally glued explorer makes those questions native rather than requiring the
user to mentally invert a projection.

## Why this composition works

1. **Depth is privileged honestly.** `W` is ordered in the model, so placing it on
   the base is not an arbitrary axis choice.
2. **Identity survives local similarity.** Each LoRA target remains a labeled global
   sheet. A gluing bridge states that two sheets are close over a chart; it does not
   erase their identities.
3. **The chart is an exact comparison window.** `U` gives X/Y/Z a shared local
   support and makes the distance threshold inspectable.
4. **Direct and closure evidence stay separate.** The `G` readout reports direct
   threshold neighbors. The status and analysis receipt report the connected
   component of the tolerance graph, which is its single-linkage transitive closure.
5. **S lives where it is defined.** The spin/liveness category is attached to
   overlap cycles rather than copied onto every model node.
6. **Absence is representable.** The interface reports uncertainty and monodromy as
   unavailable when the source or base topology cannot support those claims.

## Why not use one of the common alternatives?

| Surface | Good at | Failure for this task |
| --- | --- | --- |
| 5D globe or grand tour | Global shape and discovery | Exact coordinate comparison changes with projection |
| Parallel coordinates | Comparing five values at one sample | No native persistent sheet identity or overlap event |
| Heatmap | Dense layer-by-target scanning | Hides the local multivariate relation and its closure |
| Small multiples alone | Stable per-coordinate reading | Does not express local gluing, quotient transitions, or S |
| Locally glued sheets | Ordered depth, persistent identity, local equivalence | Depends on a defensible base and metric policy |

The explorer therefore complements the globe rather than replacing it. If there is
no natural ordered base, the argument collapses and a grand tour is the better
default.

## Claim discipline

The raw relation `d_U <= epsilon` is a tolerance relation: reflexive and symmetric,
but not necessarily transitive. Connected components form the displayed
single-linkage closure. Merge, split, and rewire marks describe that quotient; they
are not literal branching points of an étale map.

`epsilon` is a descriptive threshold, not a confidence interval. The current
metric is fixed before charting:

- X: per-module, full-depth min-max normalization;
- Y: global all-module/all-layer min-max normalization;
- Z: global all-module/all-layer min-max normalization;
- window-dependent normalization: false;
- statistical uncertainty: unavailable in the source atlas.

Because the W base is an interval with no closed path, monodromy is unavailable.

## Agent interaction contract

The human view and the agent view consume the same deterministic analysis receipt.
An agent never needs to estimate values from SVG positions.

### Shareable state

Every control is represented in the URL:

```text
etale.html?layer=13&module=q_proj&radius=2&epsilon=0.25&tau=0.20&q=0.15&job=evaluate-pixie_rank8
```

Invalid query values are ignored, recorded in `query_warnings`, and replaced in the
canonical share URI on the next render.

### Browser API

```javascript
window.PixieEtaleExplorer.getContract()
window.PixieEtaleExplorer.getState()
window.PixieEtaleExplorer.setState({
  layer: 13,
  module_id: "q_proj",
  chart_radius: 2,
  glue_tolerance: 0.25,
  lineage_floor: 0.20,
  spin_noise: 0.15
})
window.PixieEtaleExplorer.setPlaying(false)
window.PixieEtaleExplorer.getAnalysis()
window.PixieEtaleExplorer.getShareUrl()
window.PixieEtaleExplorer.listJobs()
window.PixieEtaleExplorer.selectJob("evaluate-pixie_rank8")
window.PixieEtaleExplorer.getSelectedJob()
```

`setState` rejects unknown fields, invalid module IDs, non-sampled layers, and
out-of-range values. `getContract` publishes those enums and numeric bounds, the
query-to-state mapping, method names, schemas, event name, and DOM receipt ID.
Every rendered analysis dispatches
`pixieology:etale-analysis`. The same JSON is mirrored in
`#etale-analysis-json` for DOM-only agents.

The receipt includes metric provenance, direct glued partners, closure membership,
the closest pair, current and nearest quotient transitions, monodromy status,
spin evidence, a human-readable summary, and the canonical share URI. SVG marks
also expose stable `data-*` attributes and accessible labels for sheet, band,
layer, and transition identity.

The v3 agent contract also exposes the exact per-layer dendrogram MST, chain
excess, Tarjan bridges and articulation vertices, and an explicit `bridge: none`
robustness certificate. Pairwise chart distances use prefix sums over globally
fixed coordinates; the receipt declares that the cache is invalid if
normalization ever becomes window-dependent.

Activation-conditioned motif catalogs are optional, versioned inputs. Until a
catalog passes its registered confirmation gates, `getMotifCatalog()` reports
`NOT_RUN`, case and motif lists are empty, and the default view remains the
parameter-only atlas. Confirmed catalogs can be inspected with `listCases()`,
`loadCase(case_id)`, `listMotifs()`, and `getMotif(motif_id)` without parsing
visual marks.

The feedback-job tray is the operational bridge from a motif to a bounded
intervention. `getJobQueue()`, `listJobs()`, and `getJob(job_id)` expose immutable
base, Pixie, TinyLoRA, and QLoRA proposal contracts. `selectJob(job_id)` changes
inspection state and the share URI; it cannot authorize, launch, or mutate a job.
The default queue contains the two reference evaluations and reports training
slots blocked until a registered activation catalog exists. That explicit
negative state prevents an agent from manufacturing a motif-conditioned job from
the parameter-only atlas.

## Evaluation

The design earns its place if users or agents can answer the following faster and
with fewer errors than in the globe or flat atlas alone:

1. identify the closest target over a specified chart;
2. distinguish direct gluing from closure-only membership;
3. locate the start and end of a gluing band;
4. identify a merge, split, or rewire without calling it literal branching;
5. report the applicable S certificate and its synthetic/measured boundary;
6. reproduce the result from a share URI or analysis receipt.

The primary comparison should measure answer accuracy, time, and unsupported
topological claims. Preference is secondary.
