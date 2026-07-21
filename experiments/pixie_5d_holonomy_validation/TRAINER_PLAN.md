# Bounded capture plan

This experiment performs inference and activation capture only. It does not
train or mutate model weights.

## CPU-safe stage

- hard-cap profile: 2048 MB RAM, 50% CPU, 50 MB/s I/O;
- work unit: one synthetic geometry condition at a time;
- checkpoint: after every condition and at most every 60 seconds;
- matrix strategy: sample-by-hidden matrices only, SVD capped at rank 8;
- outputs: fsynced JSONL events plus one atomic summary;
- abort is a valid result.

## Requested real-capture stage

The following is a request, not current authorization:

- 6144 MB process-tree RAM;
- 50% CPU;
- 250 MB/s I/O;
- 1800 second wall-time limit;
- one microbatch prompt at a time;
- maximum sequence length 128;
- four hidden-state sites only;
- NPZ checkpoint after each context and adapter condition;
- no generation during the primary capture;
- local files only and telemetry disabled.

The supported launcher is `scripts/run_capped_capture.ps1`. It validates the
human authorization receipt before launch, verifies the content hashes of the
shared Job Object wrapper and owned-process gate, and passes the exact cap
values into the child for a second fail-closed check before Torch is imported.
Direct invocation of `run.py capture` therefore cannot load the model.

The Windows Job Object wrapper must record the owned process tree. On any cap,
timeout, swap, or sustained-I/O breach it terminates only those PIDs and writes
an `ABORTED_RESOURCE_CAP` result.

## Cleanup

The capture process must, in `finally`:

1. release model, adapter, tokenizer, tensors, and array handles;
2. run `gc.collect()`;
3. synchronize CUDA, empty the CUDA cache, and collect CUDA IPC handles;
4. terminate only recorded run-owned child processes;
5. record pre/post RAM, commit, cache, GPU processes, and lingering owned PIDs.

Cleanup failure changes the terminal result to `CLEANUP_FAILED`, even if all
scientific work units completed.

`scripts/post_run_cleanup.ps1` performs a non-destructive ownership audit after
the Job Object exits. It never kills by image name; a lingering recorded PID is
reported for inspection instead of risking an unrelated process.
