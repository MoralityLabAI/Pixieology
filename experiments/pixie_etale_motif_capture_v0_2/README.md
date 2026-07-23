# Pixie etale motif capture v0.2

This is a versioned loader-only successor to
`pixie_etale_motif_search_v0_1`. It does not alter the registered corpus,
coordinates, modules, checkpoints, model, or adapter. It exists because the
v0.1 canary capture reached 6076 MiB of Job memory during base-model loading
and emitted no activation rows.

The v0.2 job is deliberately narrow: chunk 0, `pixie_canary`, 32 rows
(16 discovery, 8 confirmation, 8 transfer), checkpointed every 8 rows. The
loader keeps the original 6144 MiB RAM, 50% CPU, 250 MiB/s I/O, 1800-second,
and 3900 MiB peak-VRAM guards while:

- setting `HF_DEACTIVATE_ASYNC_LOAD=1`, which makes Transformers 5.3.0
  materialize and quantize tensors sequentially instead of through its default
  thread pool;
- using only the verified safetensors shards rather than a merged state dict;
- deferring PEFT import and adapter attachment until the quantized base is
  resident;
- recording loader phases with process-private and CUDA memory;
- cleaning only recorded owned PIDs and CUDA allocations.

## Fail-closed workflow

```powershell
python experiments/pixie_etale_motif_capture_v0_2/run.py verify
python experiments/pixie_etale_motif_capture_v0_2/run.py proposed-job
python experiments/pixie_etale_motif_capture_v0_2/run.py authorization-template
```

The template is inactive. Do not edit `proposed_job.json`, `protocol.json`, or
`protocol.lock.json` after authorization. A run may begin only through:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  experiments/pixie_etale_motif_capture_v0_2/scripts/run_capped_capture_v2.ps1 `
  -Authorization <active-receipt.json>
```

An abort is valid operational evidence. A completed capture is still not a
motif; it only creates resumable input-conditioned geometry checkpoints for
the downstream v0.1 gates.
