# Bounded capture and analysis plan

Task ID: `pixie-etale-motif-search-v01`.

## Capture limits

```text
RAM       6144 MiB per process and whole job
CPU       50% hard Windows Job Object rate
I/O       250 MiB/s Job Object rate control
timeout   1800 seconds per 32-input chunk
checkpoint 8 input rows
```

The launcher reuses the hash-pinned v0.2 Job Object implementation whose
destructive cap self-test already demonstrated OS enforcement. It validates GPU
idleness, wrapper hashes, protocol-bound authorization, and configured paths
before launch. Every child remains in the owned Job Object.

The sharder parses safetensors metadata and copies tensor byte ranges directly.
It never asks PyTorch, NumPy, or safetensors to materialize a source model tensor.
Each destination tensor is independently re-read and byte-hashed before its
shard completion marker is published.

## Durable outputs and aborts

Capture writes one uncompressed NPZ plus a hash-bound marker every eight rows.
Each artifact retains base module inputs so nineteen random-control geometries
can be computed offline one control at a time under the 2 GiB analysis cap.
JSONL events and terminal JSON summaries distinguish completion, abort, and
cleanup failure.

Cap breach, timeout, lineage drift, hash mismatch, incomplete hook inventory,
CUDA failure, or cleanup failure is a valid machine-readable result. No
unchanged failed attempt is silently retried.

## Cleanup

The Python `finally` path dereferences model, tokenizer, activations, adapters,
and tensors, runs `gc.collect()`, then synchronizes and clears CUDA allocation,
reservation, and IPC caches. The wrapper audits only recorded owned PIDs and
owned GPU applications. It never kills processes by name and never purges the
global standby cache or pagefile.

The cleanup receipt records owned and lingering PIDs, GPU compute processes,
available physical memory, commit state when available, and a pass/fail result.
