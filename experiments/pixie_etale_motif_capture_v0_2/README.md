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

## PrimeLab platform amendment

The registered Windows attempt emitted no activation rows and ended in a
native PyTorch `c10.dll` access violation. The amended launcher
`scripts/run_capped_capture_prime.sh` moves the same exact canary job to one
on-demand RTX A6000 48 GB pod without changing the 6144 MiB RAM, 50% CPU,
250 MiB/s I/O, 1800-second, or 3900 MiB peak-VRAM guards. It uses cgroup v2,
zero cgroup swap, parent-block-device I/O accounting, and attempt-owned
cleanup. A runtime `pixieology.config.json` supplies absolute Linux asset and
output paths; frozen hashes, not those path strings, establish asset identity.

This amendment needs a new exact authorization. Success promotes only the
canary loader/capture lane. Full-family capture, motif confirmation, and
training remain separately staged work.

## PrimeLab attempt 1 result

Attempt 1 reached `model_ready` under the registered caps, then aborted before
row 0 because Transformers 5.3.0 requires Jinja2 3.1 or newer for
`apply_chat_template`, while the pod image exposed Jinja2 3.0.3. It produced
zero activation rows and zero checkpoints. Peak job RAM was 878.4 MiB, peak
global VRAM was 1728 MiB, and PID-scoped cleanup passed with no lingering
process.

The retry amendment pins Jinja2 3.1.6 in the generic software preflight.
Nothing about the scientific job or resource envelope changes, and the abort
does not authorize an automatic retry.
