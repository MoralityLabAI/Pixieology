# v0.3 bounded execution plan

Task ID: `bonsai-1p7b-holonomy5d-context3-sharded-v03`.

## Conveyor

1. Verify the protocol lock, source model, support files, adapter, data,
   reusable v0.1 artifacts, v0.2 abort receipt, wrapper, and package versions.
2. Require a receipt acknowledging the exact sharding and loader recipes.
3. Refuse launch when the GPU is occupied or the sharded-model drive has less
   than 5 GiB free.
4. Enter the hash-pinned Windows Job Object.
5. Create or resume seven tensor-boundary shards, publishing a marker after
   every shard.
6. Verify the complete sharded snapshot, load the frozen 4-bit model, attach
   the frozen adapter and norm-matched control, and capture context 3 in eight
   rows per checkpoint.
7. Release model, tokenizer, adapter, tensors, and CUDA caches in `finally`.
8. Close the Job Object and audit only recorded owned PIDs and GPU processes.
9. Run the 2 GiB CPU analysis wrapper only after a complete context marker.

## Hard limits

```text
RAM       6144 MiB per process and whole job
CPU       50% hard Job Object rate
I/O       250 MiB/s Job Object rate
timeout   1800 seconds
```

The cap implementation is `run_capped_v2.ps1`, whose destructive 128 MiB
test demonstrated OS termination and read back flags `0x2300`. The wrapper
also independently samples the owned descendant tree every 500 ms. No direct
Python capture is accepted because the authorization validator requires the
wrapper environment and exact wrapper SHA-256.

## Durable outputs

The event log uses fsynced JSONL. Shards, capture archives, and summaries use
temporary files plus atomic replacement. Generated artifacts live only under
the three `pixie_5d_holonomy_v03_*` configuration paths.

Example events:

```json
{"event":"shard_complete","index":1,"count":7,"utc":"..."}
{"event":"sharded_model_loaded","attempt_id":"...","random_modules":196,"utc":"..."}
{"event":"chunk_complete","start":0,"end":8,"utc":"..."}
```

A terminal summary records the protocol and sharding-manifest hashes, shard and
chunk counts, package versions, peak CUDA allocation/reservation, cleanup, and
wall time. The Job wrapper separately records caps, readback, sampled process-
tree RAM/CPU, peak Job/process memory, GPU memory/temperature, exit code, and
abort reason. Actual average RAM and I/O throughput are not promoted as direct
measurements when the wrapper has only sampled RAM and an enforced I/O ceiling;
result receipts must label those unavailable rather than invent them.

Aborts and cleanup failures are results. No process is killed by name, WSL is
not started, and global standby cache or pagefile state is not modified.
