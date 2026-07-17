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

The bundled HRM-Text 1B trace is generated from a real 16-chunk low-rank refinement
summary. Its five channels are residual-mix singular value, value-path singular
value, routing-stabilizer singular value, mean output delta, and peak output delta.
Those are not personality labels.

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
- `godel_globes_vpd_trace`.

`run_godel_globes_study.py` launches rounds, ingests exported receipts without
overwriting conflicts, reports current status, and atomically writes the final
comparison result. Generated participant receipts stay under the configured data
root rather than the source tree.
