# Bounded trainer plan — PrimeLab continuation v0.2

## Execution envelope

- Windows Job Object wrapper: `../pixie_5d_holonomy_validation_v0_2/scripts/run_capped_v2.ps1`
- PrimeLab wrapper: `scripts/run_capped_feedback_prime.sh` using cgroup v2
- RAM: 8192 MiB hard process-tree limit
- CPU: 50% hard process-tree limit
- I/O: 50 MiB/s process-tree rate limit
- Wall time: 1800 seconds
- GPU preflight: one GPU, at most 256 MiB already used, no compute applications
- Runtime GPU guard: at most 3900 MiB peak reserved memory

The launcher verifies its sealed hashes before loading the model. The child
process must observe `PIXIE_RESOURCE_CAP_ACTIVE=1`, every authorization-bound
cap value, and the authorization-bound run ID. The PrimeLab wrapper sets
`memory.max`, disables cgroup swap, applies `cpu.max`, and applies `io.max`
before the Python process enters the cgroup.

## Checkpoint and resume

The trainer checkpoints the PEFT adapter, optimizer, step counters, and Python, NumPy, CPU Torch, and CUDA RNG states every five optimizer steps, every five minutes, and at completion. It retains two completed checkpoints and ignores `.partial` directories. Resume chooses the greatest completed step for the exact run/job path.

## Outputs

Each attempt writes append-only events and metrics, durable checkpoints, and exactly one training result or structured abort receipt. Evaluation writes resumable per-row JSONL and a summary with overall and per-family log-likelihood and exact-match metrics. The wrapper and cleanup scripts add a resource summary, owned-PID inventory, GPU observations, and a cleanup summary.

CPU and I/O are enforced by the Job Object or cgroup v2. The wrappers do not
claim a realized utilization series when one is unavailable; final receipts
record the enforced ceiling and cap mechanism.

## Cleanup

The Python child drops model, optimizer, token batches, and tokenizer
references, runs garbage collection, synchronizes CUDA, empties the allocator
cache, and attempts CUDA IPC cleanup. The Windows outer cleanup terminates only
recorded PIDs; the PrimeLab outer cleanup kills only the attempt-owned cgroup.
Broad process-name kills are forbidden.

## Stop and escalation

No automatic resource escalation is allowed. The v0.1 2 GiB model-load failure
remains the registered cap-fit result. This v0.2 continuation requests 8 GiB;
any further change requires another preregistered continuation and a new exact
authorization.
