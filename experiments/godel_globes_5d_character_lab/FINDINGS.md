# Strategy findings

The five-dimensional `2 + 2 + 1` strategy is technically viable as a retail
character editor. The deterministic gates pass, and the twelve authored forms
retain useful local structure when projected into the rotatable navigation globe.

## Evidence

- The fixed 3D projection retains `93.64%` of fitted variance.
- Pairwise 5D versus 3D distance has Spearman correlation `0.979919`.
- Normalized stress is `0.064752`, below the registered `0.10` ceiling.
- Every warp stays inside `[0, 1]^5`, follows one continuous endpoint path, and
  can be reversed.
- Anchors, sliders, character anatomy, and map position all share one tuple state.
- A portable, explicitly experimental game contract now matches the browser
  runtime exactly and emits a versioned 3D live state for a future retail shell.
- Pause/play, time scrubbing, pointer rotation, and local JSON/JSONL trace loading
  share a fail-closed five-channel trace contract.
- The bundled HRM-Text 1B depth trace is derived from the actual 16-chunk local
  VPD-style low-rank refinement summary and carries its SHA-256. It is explicitly
  uncalibrated and cannot drive the authored personality body.
- The bundled Bonsai 1.7B trace is derived from the actual trained rank-8 all-linear
  adapter. All 28 layers were measured under hard local resource caps, with an
  atomic checkpoint per layer and adapter SHA-256 provenance. Because it measures
  parameter deltas rather than activations, it remains uncalibrated and cannot drive
  the authored personality body.
- Retail anchors exclude Jinn, Beast of the Earth, and related terms. Capability
  envelopes and named theological entities remain separate from personality
  structure.

## Decision

Continue with the strategy for a small retail usability test. Do not yet promote
the five dimensions to a final product ontology: the automated results establish
internal coherence and neighborhood quality, not that new players understand or
enjoy the interaction.

The stronger next test is now executable as a counterbalanced embodied-versus-flat
comparison. It records identical tasks, completion time, committed actions,
wrong-dimension edits, map semantics, and preference without network telemetry.
Its current result is `NOT_RUN`; no comparative advantage is claimed without six
paired participants. See `AB_TEST_PROTOCOL.md` and `AB_RESULT.json`.

A segregated Codex operator smoke executed all five tasks in both conditions. It
passed with zero wrong-dimension actions and zero final tuple error. This proves
the registered action and receipt paths execute; it is explicitly labeled
synthetic and is not counted as human comprehension or preference evidence. See
`CODEX_OPERATOR_SMOKE_RESULT.json`.

The Chrome render path was inspected for both the authored and actual VPD traces.
Pointer/keyboard interaction and the original five-player comprehension gate still
require human execution. The quick task card remains in `USABILITY_TEST.md`.
