# Trainer plan

This is a CUDA diagnostic, not training.

- Task ID: `diagnose-bnb4bit-c10-boundary-v0_3`
- Chunk strategy: one quantization operation at a time; FP16 staging tensors are
  released before the next operation. Quantized sweep tensors remain resident
  intentionally to reproduce cumulative model-loading pressure.
- Checkpoint interval: every operation, including every projection in every
  synthetic layer.
- Hard caps: 2048 MiB RAM, 50% CPU, 50 MiB/s I/O, 600 seconds.
- GPU preflight: at most 256 MiB already allocated and no compute processes.
- GPU abort guard: 1800 MiB peak.
- Cleanup: explicit tensor release, `gc.collect`, CUDA synchronize,
  `empty_cache`, and `ipc_collect`, followed by Job Object kill-on-close and a
  PID-scoped memory/GPU audit.
- Abort semantics: cap breach, native crash, exception, timeout, or failed
  cleanup are valid diagnostic outcomes.

The JSONL event log records each operation. `checkpoint.json` is overwritten
atomically after every successful operation. `summary.json` or `abort.json`
records the Python outcome, while the wrapper emits resource, cleanup, and
combined execution summaries.
