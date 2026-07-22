# Pixie 5D holonomy validation v0.3 — sharded-loader continuation

Status at freeze: `STAGED_NOT_AUTHORIZED`. No v0.3 checkpoint rewrite, model
load, context capture, or combined analysis has been run.

## Registered reason for v0.3

The exact v0.2 attempt aborted while `safetensors.safe_open` loaded the frozen
3.44 GB `model.safetensors` file under a correctly enforced 6144 MiB Job Object
limit. Windows returned error 1455 before the first context-3 chunk. The host
had a 45 GB pagefile and substantial system commit headroom after cleanup;
v0.1 had previously approached 10 GB while its nominal Job cap was ineffective.
The v0.2 result and raw-artifact hashes are frozen in
`receipts/context3_attempt_01_abort.json` in the v0.2 experiment.

Transformers 5.3.0 explicitly discards the legacy `low_cpu_mem_usage` and
`offload_state_dict` keyword arguments. v0.3 therefore does not preregister
those flags as a supposed fix. It deterministically rewrites the single-file
checkpoint into standard safetensors tensor-boundary shards before loading.

## Loader hypothesis and gate

Loader hypothesis L1: reducing the largest memory-mapped checkpoint window
from the single 3.44 GB file to tensor-boundary shards will permit the frozen
4-bit loader to complete under the same 6144 MiB per-process and whole-job
hard limit.

The target shard size is 536870912 bytes. Standard safetensors cannot divide a
tensor across files, so one 621236224-byte embedding tensor is an explicitly
registered atomic overflow. The dry header-only plan has seven shards and 310
tensors. No tensor values are loaded by that planning step.

Before model loading, the sharder must:

- verify the complete source checkpoint SHA-256;
- copy only hash-verified tokenizer/configuration files;
- checkpoint after every shard;
- hash every source tensor's raw bytes;
- reopen every written shard and require identical tensor shape and byte hash;
- write a standard `model.safetensors.index.json`;
- atomically publish a manifest and completion marker covering every output;
- resume only shard files whose marker, protocol hash, source hash, tensor list,
  and shard hash all match.

If sharding or model loading fails, v0.3 aborts and performs no context capture.
It does not fall back to the original file, raise the memory cap, alter model
weights, or silently use a different quantization recipe.

## Frozen scientific protocol

The personas, prompts, train/evaluation split, adapter, norm-matched random
control, contexts, layers, seeds, geometric construction, regression models,
bootstrap count, thresholds, and verdict rules remain those frozen by v0.1
and reverified in v0.2. Contexts 0–2 are reused only by exact artifact hashes.
v0.3 captures context index 3 only, in eight-row chunks, then applies the same
registered four-context analysis.

The tensor-boundary serialization is an operational loader intervention, not a
new scientific treatment. Byte-identical tensors establish checkpoint-value
equivalence. It does not establish equivalence of transient loader memory or
serialization metadata, which are deliberately changed.

## Resources, checkpoints, and aborts

- RAM: 6144 MiB Windows Job Object per-process and whole-job hard limits.
- CPU: 50% Windows Job Object hard CPU rate.
- I/O: 250 MiB/s Windows Job Object rate control.
- Timeout: 1800 seconds for sharding, loading, and context capture combined.
- GPU preflight: one GPU, no compute applications, and at most 256 MiB already
  allocated.
- Sharding checkpoint: one atomic receipt per shard.
- Capture checkpoint: one atomic three-condition receipt per eight records.
- Cleanup: explicit CUDA/object cleanup, Job Object kill-on-close, and a PID-
  scoped post-run RAM/GPU/WSL audit. No unrelated process or global cache is
  modified.

Cap breach, timeout, lineage drift, shard mismatch, tensor mismatch, source
mutation, CUDA failure, output corruption, or cleanup failure is a valid
machine-readable abort. An unchanged failed attempt is not retried under a new
identifier merely to seek a different result.

## Interpretation boundary

A successful loader gate only shows that byte-equivalent sharding makes this
checkpoint loadable under this local cap. A successful scientific result still
concerns one base revision, one adapter, one prompt corpus, and one context
cycle. A single norm-matched random adapter is not an empirical null; any
finalist remains provisional until the registered nineteen-control follow-up.
