# Trainer plan

- Task: capture the five frozen non-canary chunks in one model residency.
- Work: rows 32 through 191; 160 rows total; twenty eight-row checkpoints.
- Hard caps: 6144 MiB cgroup memory with no swap, 50 percent of visible CPU,
  250 MiB/s cgroup I/O, 1800 seconds, and 3900 MiB peak VRAM.
- GPU preflight: one GPU, at most 256 MiB resident, and no compute
  applications.
- Loader: verified raw shards, NF4 double quantization, float16 compute,
  `HF_DEACTIVATE_ASYNC_LOAD=1`, then deferred PEFT attachment.
- Resume: skip a checkpoint only when its artifact SHA-256, row IDs, job hash,
  and capture-protocol hash match.
- Logs: loader/capture events, checkpoint markers, capture summary or abort,
  wrapper resource summary, cleanup summary, and combined execution summary.
- Cleanup: release Python/CUDA references, kill only the attempt-owned cgroup,
  and audit for lingering owned processes.
- Promotion: only when wrapper, capture, all twenty checkpoints, and cleanup
  are complete/PASS.
- PrimeLab: one on-demand A6000 48 GB at no more than USD 0.70/hour, no more
  than two hours, and no more than USD 1.40 total.
- Claim boundary: capture only. Scaling, motif mining, held-out confirmation,
  interventions, human-usefulness study, and training are out of scope.
