# Operational deviation 001: bounded chunk resumption

The first execution attempt (`multi-adapter-ni-v1`) started from frozen Git
commit `1a24d1a` on 2026-07-19. Its Windows Job Object correctly enforced 2 GB
RAM, 50% CPU, and 50 MB/s I/O. Under the hard CPU rate, steady-state llama.cpp
generation fell to about 0.6 tokens/s. Five of 44 planned generations were
fsynced before an authenticated early shutdown at 467 seconds; owned-process
cleanup passed and the attempt is retained as `attempt_001` evidence.

No probe, condition, decoding setting, scorer, margin, bootstrap rule, adapter,
or model changed. The operational harness now resumes only an exact,
content-hashed prefix of the frozen 44-row plan. Each bounded chunk uses a
unique run ID and launch directory while sharing the same study ID. A mismatch
in protocol hash, matrix hash, plan order, row schema, or content hash aborts.

This deviation changes execution scheduling only. It was implemented, tested,
committed, and pushed before resuming model generation.
