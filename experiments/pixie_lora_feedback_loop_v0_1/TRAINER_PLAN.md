# Bounded trainer plan

## Execution envelope

- Windows Job Object wrapper: `../pixie_5d_holonomy_validation_v0_2/scripts/run_capped_v2.ps1`
- RAM: 2048 MiB hard process-tree limit
- CPU: 50% hard process-tree limit
- I/O: 50 MiB/s process-tree rate limit
- Wall time: 1800 seconds
- GPU preflight: one GPU, at most 256 MiB already used, no compute applications
- Runtime GPU guard: at most 3900 MiB peak reserved memory

The launcher verifies the wrapper and cleanup script hashes before loading the model. The child process must observe `PIXIE_RESOURCE_CAP_ACTIVE=1` and the authorization-bound run ID.

## Checkpoint and resume

The trainer checkpoints the PEFT adapter, optimizer, step counters, and Python, NumPy, CPU Torch, and CUDA RNG states every five optimizer steps, every five minutes, and at completion. It retains two completed checkpoints and ignores `.partial` directories. Resume chooses the greatest completed step for the exact run/job path.

## Outputs

Each attempt writes append-only events and metrics, durable checkpoints, and exactly one training result or structured abort receipt. Evaluation writes resumable per-row JSONL and a summary with overall and per-family log-likelihood and exact-match metrics. The wrapper and cleanup scripts add a resource summary, owned-PID inventory, GPU observations, and a cleanup summary.

CPU and I/O are enforced by the Job Object but the current wrapper does not measure their realized time series. Final receipts state those measurements as unavailable rather than inventing utilization values.

## Cleanup

The Python child drops model, optimizer, token batches, and tokenizer references, runs garbage collection, synchronizes CUDA, empties the allocator cache, and attempts CUDA IPC cleanup. The outer cleanup then audits and terminates only PIDs owned by the attempt. Broad process-name kills are forbidden.

## Stop and escalation

No automatic resource escalation is allowed. A 2 GiB model-load failure is the registered cap-fit result. A future protocol may preregister a larger envelope after this one is sealed; it must not mutate or reinterpret the v0.1 receipt.
