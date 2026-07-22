# Pixie 5D holonomy validation v0.2 — context-3 continuation

Status at freeze: `STAGED_NOT_AUTHORIZED`. No v0.2 model capture or combined
analysis has been run.

## Reason for a versioned continuation

The v0.1 process completed contexts 0, 1, and 2 but timed out during context 3.
Its nominal 6 GiB Windows Job Object memory cap was later found not to have
been applied: PowerShell mutated a copy of a nested value-type structure and
the OS readback flags were zero. The scientific protocol is not silently
edited. v0.2 is a separately versioned continuation that freezes the hashes of
all reusable v0.1 artifacts and replaces only the resource wrapper and the
context-3 checkpoint strategy.

## Frozen estimand and analysis

The hypotheses, contexts, layers, data, adapter, random-control seed, geometric
construction, held-out estimator, bootstrap count, thresholds, and verdict
rules remain exactly those in the hashed v0.1 protocol and source modules.
Contexts 0–2 are reused only when their completion markers and all three
condition archives match the hashes in `protocol.json`. v0.2 captures only
context 3, then runs the frozen v0.1 analysis over the assembled four-context
cycle.

The primary estimand remains the held-out predictive increment of the complete
`XYZTS + holonomy-category` representation above the registered depth/update-
energy baseline. The single norm-matched random adapter is a specificity
control, not an empirical random-adapter null distribution. A finalist still
requires the separately registered nineteen-control follow-up.

## Frozen execution rule

- Context index: 3 only.
- Expected records: 64, comprising the frozen train and evaluation JSONL.
- Chunk size: 8 records; each chunk publishes three NPZ files and one atomic
  hash marker.
- Resume: only a marker whose protocol hash and artifact hashes match is
  reusable. Any partial or mismatched files are quarantined.
- Final assembly: eight complete chunks, 64 unique row IDs per condition, and
  identical row/layer metadata across the four contexts.
- Hard resources: 6144 MiB per-process and whole-job memory, 50% Job Object CPU
  rate, 250 MiB/s Job Object I/O rate, and 1800 seconds.
- GPU-idle preflight: one visible GPU, no existing compute application, and no
  more than 256 MiB already allocated. Contention aborts before model loading.
- Abort: OS cap, independent owned-process tree cap, timeout, lineage failure,
  CUDA failure, or cleanup failure. Failed attempts retain logs and receipts.
- Cleanup: Job Object kill-on-close plus a post-run audit of owned PIDs, GPU
  processes, host memory, and WSL state. No process is killed by name and no
  system cache is dropped.

## Cap gate

Before authorization, the exact frozen wrapper passed a destructive 128 MiB
self-test. The readback contained flags `0x2300`, both process and job limits
equaled 134217728 bytes, and the OS terminated a probe requesting 384 MiB before
its completion marker. The concise evidence and exact implementation hashes
are frozen in `receipts/cap_enforcement_v2.json` and `protocol.json`.

This proves cap enforcement for the self-test; it does not prove that Bonsai
will fit the 6144 MiB host-memory cap or the RTX 3050's 4096 MiB VRAM.

A separate 512 MiB CPU-only success-path probe exited zero and the post-run
audit found no lingering owned process or owned GPU process. Its concise
receipt is `receipts/launcher_success_v2.json`. It proves normal completion and
cleanup plumbing only, not model feasibility.

## Interpretation boundary

Separate bounded processes capture contexts 0–2 and context 3. Hashes, frozen
model/adapter/data revisions, deterministic seeds, and identical artifact
metadata establish versioned lineage, but cannot make the captures
simultaneous. Any observed result is evidence about this adapter, checkpoint,
dataset, and context cycle, not a universal persona manifold.
