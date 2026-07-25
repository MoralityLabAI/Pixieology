# Preregistration

## Question

Can the loader proven by the completed 32-row canary capture produce all 160
remaining frozen activation rows under the unchanged resource envelope?

## Frozen scope

- Corpus rows: 32 through 191, in original order.
- Chunks: 1 through 5, one family per 32-row chunk.
- Splits: 80 discovery, 40 confirmation, 40 transfer.
- Model, adapter, tokenizer, source protocol, modules, coordinate definition,
  and teacher-forced likelihood calculation: unchanged from v0.1/v0.2.
- Checkpoint cadence: exactly eight rows, for twenty expected checkpoints.
- Loader: verified safetensors, sequential NF4 materialization, then deferred
  PEFT attachment.
- Resources: 6144 MiB RAM, 50 percent CPU, 250 MiB/s I/O, 1800 seconds, and
  3900 MiB peak VRAM.

## Outcomes

- `COMPLETE`: all twenty bound checkpoint markers exist, the continuation
  summary reports 160 rows, all guards pass, and cleanup passes.
- `ABORTED`: any integrity, dependency, loader, capture, resource, GPU, or
  cleanup failure. Correctly bound completed checkpoints remain resumable.

Completion permits a separately preregistered global-normalization and motif
mining stage. It does not validate a motif, causal mechanism, human-learning
benefit, or adapter improvement. Abort grants no automatic retry.
