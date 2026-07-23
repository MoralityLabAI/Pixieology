# Preregistration

## Question

Can the already registered canary activation capture load the same frozen
Bonsai/Pixie pair without exceeding the unchanged 6144 MiB RAM envelope?

## Frozen change

Only loader mechanics change from v0.1: Transformers async tensor loading is
disabled so safetensors are materialized and quantized sequentially, and PEFT
is deferred until the base is resident. Corpus order, chunk 0, model and
adapter hashes, LoRA response coordinates, module inventory, teacher-forced
outcomes, and 8-row checkpoint cadence remain frozen.

## Outcomes

- `COMPLETE`: all four 8-row checkpoints exist, cleanup passes, and the peak
  VRAM guard passes.
- `ABORTED`: any cap, loader, integrity, GPU, or cleanup failure. Existing
  checkpoints remain resumable.

Neither outcome validates a motif. Forms remain descriptive until the
registered discovery, confirmation, predictive, random-null, intervention,
and human-usefulness gates are satisfied.
