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

Drag the globe to rotate its camera. **Pause/Play** controls both time traversal and
automatic rotation; the time slider scrubs individual frames. The trace selector
includes two deliberately distinct data classes:

- **Authored character orbit** drives the character body because its axes are the
  five authored retail traits.
- **HRM-Text 1B VPD-style depth trace** is generated from the actual local 16-layer
  low-rank refinement batch. Its mechanical channels are displayed on the globe but
  are explicitly uncalibrated and never relabeled as Wonder, Play, Care, Resolve, or
  Reflection.

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
```

The VPD trace builder resolves both its source batch and generated browser asset
through `pixieology.config.json`. The generated trace records the source summary's
SHA-256 and model ID but contains no source-machine path.

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
