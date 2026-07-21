# Gödel Globes 5D Character Lab

This folder tests a retail-facing character editor in which two traits live on each
wing and one lives on the head. Players can explore authored forms on a rotatable
three-dimensional globe, warp between them, scrub or pause a five-dimensional
trajectory over time, or edit the underlying tuple.

The prototype deliberately separates three things:

- **character structure:** Wonder, Play, Care, Resolve, and Reflection;
- **capability envelope:** model size, memory, tools, and runtime support;
- **lore ontology:** named theological entities, which are not generic presets.

The 3D globe retains 93.64% of the variance among the twelve authored anchors and
is navigational. It is not presented as transformer geometry.
The scientific RSITopology Gödel Globe remains a receipt/audit tool with different
claims and data contracts.

## Open and test

Open `index.html` directly in a current browser. No server or network connection is
required.

Open `mechinterp.html` for the dedicated Pixie 1.7B mechanistic delta atlas. It
shows a depth-by-target heatmap, per-layer attention/MLP flow, the invariant
eight-mode singular spectrum, and each target module's trajectory through all 28
transformer layers. Playback can be paused or scrubbed by layer.

Open `manifold.html` for the spatial companion. Its 3D coordinates are normalized
update energy, spectral focus, and effective rank. In 4D mode, transformer depth is
the W coordinate; an explicit orthogonal 4D rotation mixes W into the projected 3D
volume while the depth control selects the emphasized slice. Drag rotates the 3D
camera and the wheel zooms.

The 5D mode adds the rank-one spin/holonomy category as `S`, located on cycle
centers rather than model nodes. It keeps the abstract `Z/2` gauge phase separate
from the holonomy-liveness verdict, using the angle-budget theorem to distinguish
forced positive signs from live positive, live frustrated, and synthetic defects
that the displayed geometry cannot realize. `HOLONOMY_5D_NOTES.md` records the
paper hashes, equations, exact mapping, and claim boundary.

Drag the globe to rotate its camera. **Pause/Play** controls both time traversal and
automatic rotation; the time slider scrubs individual frames. The trace selector
includes three deliberately distinct data classes:

- **Authored character orbit** drives the character body because its axes are the
  five authored retail traits.
- **HRM-Text 1B VPD-style depth trace** is generated from the actual local 16-layer
  low-rank refinement batch. Its mechanical channels are displayed on the globe but
  are explicitly uncalibrated and never relabeled as Wonder, Play, Care, Resolve, or
  Reflection.
- **Bonsai 1.7B adapter delta geometry** is generated from the actual trained
  all-linear rank-8 PEFT adapter, one transformer layer at a time. It measures
  effective LoRA parameter deltas without loading the base model or activations, so
  it is adapter-pipeline evidence rather than full VPD activation evidence.

JSON and JSONL traces can be loaded locally. The `pixieology_manifold_trace_v1`
validator refuses malformed, out-of-range, or non-monotonic traces and only allows a
trace to drive the character body when its alignment is authored or calibrated.

For the counterbalanced comparison, open
`index.html?participant=P01&round=1`, export the receipt, then repeat with
`round=2`. See `AB_TEST_PROTOCOL.md` for the six-player protocol and fixed decision
rule.

The preferred repo-level entry point is `run_godel_globes_study.py`; it resolves
the experiment, private receipt store, and result through `pixieology.config.json`.
`GAME_INTEGRATION.md` documents the portable character-space and live-state
contract for a future retail shell.

Study progress resumes from browser-local storage after a reload. A receipt cannot
be exported or ingested until all five task results and the debrief are present.

```powershell
node --check space.js
node --check model.js
node --check app.js
node --check study.js
node --check study_analysis.js
node --check trace.js
node --test tests/model.test.mjs tests/study.test.mjs tests/study-analysis.test.mjs tests/page.test.mjs tests/space-contract.test.mjs tests/trace.test.mjs
node tests/evaluate-strategy.mjs
node tests/analyze-study.mjs
node tests/run-codex-operator-smoke.mjs
python ..\..\build_godel_vpd_trace.py
python ..\..\build_bonsai_adapter_vpd_trace.py --finalize
python ..\..\build_bonsai_mechinterp_atlas.py
```

The VPD trace builder resolves both its source batch and generated browser asset
through `pixieology.config.json`. The generated trace records the source summary's
SHA-256 and model ID but contains no source-machine path.

The Bonsai builder resolves the adapter, bounded run root, and browser asset through
the same config. Its analysis path refuses to run outside the Windows resource-cap
wrapper, checkpoints after every layer, and records adapter/config hashes. The
generated browser asset contains no source-machine path.

The mechanistic atlas is generated from the finalized Bonsai analysis through
`pixieology.config.json`. Its values are exact effective LoRA delta-matrix SVD
summaries. This is substantially more diagnostic than projecting the same values
onto the retail character globe, but it is still parameter-space evidence—not an
activation VPD, a semantic feature atlas, or a causal circuit map. The next evidence
gate is a bounded activation/component harvest on the exact Pixie checkpoint.

The automated suite covers the `2 + 2 + 1` anatomy mapping, tuple bounds,
projection fidelity, reversible warps, anchor selection, and the retail ontology
boundary. Use the five-person task card in `USABILITY_TEST.md` for the unresolved
comprehension gate.

`STRATEGY_RESULT.json` is the machine-readable receipt; `FINDINGS.md` records the
current go-forward decision and its limits. `AB_RESULT.json` remains `NOT_RUN`
until twelve human-session receipts are analyzed.

`CODEX_OPERATOR_SMOKE_RESULT.json` records the automated two-condition task smoke.
It is deliberately excluded from the human A/B receipt store and cannot establish
retail comprehension or preference.
