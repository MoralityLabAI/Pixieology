# Pixieology game integration contract

The experiment now exposes a portable character-space document, a versioned live
state, and a separate time-trace contract. This is the boundary a future retail
game shell should consume; it does not need to know about the prototype's SVG,
canvas, controls, or PCA implementation.

## Static space

`character_space_v1.json` contains the ordered dimensions, anatomical channels,
authored anchors, projection metadata, editing invariants, and ontology boundary.
It is deliberately marked:

```json
{"status": "experimental", "canonical": false}
```

Changing the five names after player testing is therefore a data migration, not a
silent change to permanent Pixie canon. `space-contract.test.mjs` prevents the
browser runtime and portable JSON from drifting apart.

## Live state

The editor exposes:

```javascript
window.GodelCharacterLab.getState()
```

and dispatches a `pixieology:character-state` `CustomEvent` whenever the tuple
changes. The event `detail` conforms to `character_state_v2.schema.json` and
contains the ordered tuple, named values, exact/nearest anchor, navigation
projection, and monotonic local sequence number.

## Time traces and model measurements

The rotatable globe accepts `pixieology_manifold_trace_v1`. Each trace has exactly
five normalized channels, monotonic frames, declared semantics, and an alignment
status. The browser exposes:

```javascript
window.GodelCharacterLab.getTraceState()
window.GodelCharacterLab.loadTrace(trace)
window.GodelCharacterLab.setTracePlaying(false)
window.GodelCharacterLab.setTraceTime(4.5)
```

It also dispatches `pixieology:manifold-frame`. A trace may drive the embodied
character only when `semantics` is `character_tuple` and alignment is `authored` or
`calibrated`. Mechanistic VPD-style traces remain visual evidence only until a
held-out probe/causal calibration establishes their relationship to the retail
axes.

## Locally glued mechanistic explorer

`etale.html` exposes a deterministic agent surface over the exact LoRA delta
atlas. Every control round-trips through the query string, and the browser exposes:

```javascript
window.PixieEtaleExplorer.getContract()
window.PixieEtaleExplorer.getState()
window.PixieEtaleExplorer.setState({ layer: 13, module_id: "q_proj" })
window.PixieEtaleExplorer.setPlaying(false)
window.PixieEtaleExplorer.getAnalysis()
window.PixieEtaleExplorer.getShareUrl()
```

Every render dispatches `pixieology:etale-analysis` and mirrors the same receipt in
`#etale-analysis-json`. The receipt separates direct threshold neighbors from the
single-linkage closure component, records the normalization and uncertainty policy,
and reports unavailable monodromy rather than inferring it from the interval base.
Agents should consume this receipt or API instead of reading values from SVG
coordinates. `ETALE_UX_CASE.md` gives the full interaction and evaluation rationale.

The v2 receipt adds threshold-free dendrogram births, component chain excess,
Tarjan bridge/articulation diagnostics, the affirmative `bridge: none`
certificate, and the prefix-distance-cache policy. Optional activation motif
catalogs have their own protocol/scaler hashes and evidence class. The
checked-in catalog is deliberately `NOT_RUN`; it cannot silently relabel the
parameter atlas as activation evidence.

The bundled HRM-Text 1B trace is generated from a real 16-chunk low-rank refinement
summary. Its five channels are residual-mix singular value, value-path singular
value, routing-stabilizer singular value, mean output delta, and peak output delta.
Those are not personality labels.

The bundled Bonsai 1.7B trace is a different and narrower evidence class. It uses
small-core SVD to measure the effective `B @ A` delta for every trained LoRA module
without materializing full matrices or loading the base model. Its channels are QKV
delta energy, attention-output delta energy, MLP expansion delta energy, MLP
contraction delta energy, and spectral focus across all 28 layers. It is actual
Bonsai adapter data, but not an activation decomposition or a character-axis map.

The projection is labeled `navigation_only`. It must not be used as evidence of
literal model geometry. Parameter count, capability class, and theological entity
class are excluded axes; in particular, Jinn and Beast of the Earth are not
personality presets.

## Repository surface

The following `pixieology.config.json` paths make the experiment portable:

- `godel_globes_experiment_root`;
- `godel_globes_character_space`;
- `godel_globes_study_receipts`;
- `godel_globes_ab_result`;
- `godel_globes_vpd_source`;
- `godel_globes_vpd_trace`;
- `godel_globes_bonsai_adapter`;
- `godel_globes_bonsai_vpd_run_root`;
- `godel_globes_bonsai_vpd_trace`.

`run_godel_globes_study.py` launches rounds, ingests exported receipts without
overwriting conflicts, reports current status, and atomically writes the final
comparison result. Generated participant receipts stay under the configured data
root rather than the source tree.
