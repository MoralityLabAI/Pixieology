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

Chunk `c03` completed the companion prefix (16/44) but the first longer
symbolic action prompt exceeded the generic 240-second HTTP client timeout
while llama.cpp was still actively evaluating it. The Job cap did not breach
and cleanup passed. The client timeout is therefore 900 seconds for subsequent
requests, still subordinate to the unchanged 30-minute OS-enforced chunk
timeout. Action chunks are reduced to four requested rows. This is transport
and scheduling repair only; it does not alter model generation limits.

Chunk `c04` then revealed the same legacy 240-second timeout in the local
dual-LoRA proxy's upstream hop. The still-active llama task was canceled at
that boundary. That hop now uses the same 900-second transport allowance. The
unchanged parent Job Object remains authoritative at 30 minutes.

Chunk `c05` used both corrected transport allowances and the minimal paired
action unit. Its first request consumed the full 900 seconds without producing
a response row. The process remained owned and compute-active, and cleanup
passed. Per the registered bounded-run policy, the action and joint expansions
stop here. The completed 16-row companion prefix is scored separately, while
the overall scientific verdict remains `NOT_ESTIMATED`.
