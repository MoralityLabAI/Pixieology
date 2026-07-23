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
