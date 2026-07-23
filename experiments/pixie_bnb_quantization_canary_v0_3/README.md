# Pixie bitsandbytes quantization canary v0.3

This experiment isolates the native CUDA quantization boundary that ended the
v0.2 Pixie capture. It never reads model weights, an adapter, prompts, or
activations.

The canary reproduces the relevant operation with deterministic synthetic
FP16 tensors:

1. direct NF4 quantization of a `2048 x 2048` tensor;
2. the Transformers-compatible `Params4bit(...).to("cuda")` path for a
   `6144 x 2048` tensor;
3. one `Linear4bit` quantize-and-forward case;
4. a resident 28-layer sweep over the seven Qwen projection shapes, retaining
   quantized parameters while releasing every FP16 staging tensor.

Every operation writes an atomic checkpoint. A native crash therefore leaves
the last successful module and memory reading as evidence.

## Fail-closed workflow

```powershell
python experiments/pixie_bnb_quantization_canary_v0_3/run.py verify
python experiments/pixie_bnb_quantization_canary_v0_3/run.py proposed-job
python experiments/pixie_bnb_quantization_canary_v0_3/run.py authorization-template
```

The job is staged but inactive. It may run only through:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  experiments/pixie_bnb_quantization_canary_v0_3/scripts/run_capped_canary_v3.ps1 `
  -Authorization <active-receipt.json>
```

A completed canary is a runtime-compatibility result, not a model-load,
behavioral, activation, or motif result.
