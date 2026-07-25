# Trainer plan

- Task: capture the frozen `pixie_canary` chunk under a versioned low-memory
  loader.
- Hard caps: 6144 MiB Job/process memory, 50% Job CPU, 250 MiB/s Job I/O,
  1800 seconds, and 3900 MiB peak reserved VRAM.
- GPU preflight: one GPU, at most 256 MiB already resident, and no compute
  application.
- Chunking: exactly 32 corpus rows; durable NPZ checkpoints every 8 rows.
- Loader: raw verified shards, NF4 double quantization, float16 compute,
  `HF_DEACTIVATE_ASYNC_LOAD=1` for sequential tensor materialization and
  quantization, then deferred PEFT attachment.
- Logs: JSONL loader/capture events, checkpoint markers, capture
  summary/abort, wrapper resource summary, cleanup summary, and combined
  execution summary.
- Cleanup: Python dereferences model/tokenizer/tensors and collects Python and
  CUDA memory. The wrapper closes its Job Object and audits only recorded owned
  PIDs; one delayed PID-scoped re-audit is allowed for Windows crash tails.
- Promotion: only if wrapper status, capture summary, and cleanup are all
  complete/PASS. Abort remains a valid result and grants no activation claim.
- PrimeLab path: one on-demand A6000 48 GB pod at at most USD 0.70/hour and
  two hours. Cgroup v2 enforces the same RAM, CPU, I/O, timeout, swap, and VRAM
  envelope; the launcher resolves a mounted partition to its parent block
  device before applying `io.max`.
- Tokenizer-template preflight: require exact Jinja2 3.1.6 alongside the
  registered Transformers version before model loading. The failed attempt
  with Jinja2 3.0.3 is a valid zero-row abort and grants no automatic retry.
