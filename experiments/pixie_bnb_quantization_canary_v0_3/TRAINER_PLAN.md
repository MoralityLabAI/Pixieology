# Trainer plan

This is a CUDA diagnostic, not training.

- Task ID: `diagnose-bnb4bit-c10-boundary-host-v0_3_2`
- Chunk strategy: one quantization operation at a time; FP16 staging tensors are
  released before the next operation. Quantized sweep tensors remain resident
  intentionally to reproduce cumulative model-loading pressure.
- Checkpoint interval: every operation, including every projection in every
  synthetic layer.
- Hard caps: 2048 MiB RAM, 50% CPU, 50 MiB/s I/O, 600 seconds.
- GPU preflight: at most 768 MiB already allocated, 0% utilization, and only
  the registered `ChatGPT.exe` plus the exact idle Tesseract Qwen3.5-0.8B
  server on port 8818.
- GPU abort guard: 1800 MiB peak.
- Cleanup: explicit tensor release, `gc.collect`, CUDA synchronize,
  `empty_cache`, and `ipc_collect`, followed by Job Object kill-on-close and a
  PID-scoped memory/GPU audit. Allowed co-resident PIDs are never owned or
  stopped.
- Abort semantics: cap breach, native crash, exception, timeout, or failed
  cleanup are valid diagnostic outcomes.

The JSONL event log records each operation. `checkpoint.json` is overwritten
atomically after every successful operation. `summary.json` or `abort.json`
records the Python outcome, while the wrapper emits resource, cleanup, and
combined execution summaries.
