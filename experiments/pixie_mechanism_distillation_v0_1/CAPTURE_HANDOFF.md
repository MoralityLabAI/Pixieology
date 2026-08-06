# Capture handoff

The analysis contract is complete; model execution is deliberately absent from
the CPU-safe CLI. A future authorized runner should reuse the sequential
safetensors and NF4 loader already exercised in
`pixie_etale_motif_capture_v0_2`, while binding this experiment's protocol and
implementation-lock hashes.

## Required trace row

For each condition, family, case, registered site, and state-transition step,
emit `pixieology_mechanism_trace_v1` with:

- the observed input and output symbols;
- the oracle output symbol kept as scoring metadata, never a fitting label;
- pre-state and post-state activation vectors from the same registered site;
- `coordinate_source: registered_activation_capture`;
- model, adapter, task-set, protocol, lock, and artifact SHA-256 provenance.

Base and Pixie conditions run sequentially, never co-resident. Discovery traces
fit the codebook and transition table. Held-out traces are opened only by the
evaluation command.

## Required intervention row

The intervention plan must be frozen before patch outcomes are read. Patch a
source-state activation into an energy-matched target step at the same model,
layer, stream, and token role. Emit:

- the program-predicted output;
- baseline and observed patched outputs;
- an energy-matched random-state patch output;
- the registered guardrail delta;
- `evidence_class: registered_activation_intervention`;
- artifact URI and SHA-256.

An intervention counts only when the target patch changes the output as
predicted and exceeds the matched-random change rate. Patches that merely leave
the baseline output unchanged cannot satisfy the causal gate.

## Abort boundary

Missing sites, partial families, hash mismatch, resource-guard abort, or absent
matched controls remain valid outcomes and are reported as `NOT_RUN` or
`UNDETERMINED`. Cleanup must remain PID-scoped. No previous authorization
statement applies automatically to this job.
