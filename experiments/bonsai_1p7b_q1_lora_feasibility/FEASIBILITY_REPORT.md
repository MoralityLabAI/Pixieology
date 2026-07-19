# Bonsai 1.7B QLoRA-to-Q1 LoRA feasibility

Decision: **RED**

Generated: 2026-07-16T17:29:03.946364+00:00

## Acceptance matrix

| # | Check | Status | Evidence |
|---:|---|---|---|
| 1 | RTX 3050 detected | PASS | hardware.json |
| 2 | Bonsai-1.7B 4-bit base loads | PASS | preflight zero-adapter creation |
| 3 | All-linear LoRA attaches | PASS | 196 Qwen3 linear targets |
| 4 | One all-linear backward step fits | PASS | memory_probe.json |
| 5 | Peak VRAM measured | PASS | CUDA peak counters |
| 6 | Interrupted training resumes | PASS | fresh process resumed to step 20 |
| 7 | PEFT adapter changes held-out behavior | PASS | A versus B |
| 8 | Untrained PEFT adapter converts to GGUF | PASS | zero adapter conversion |
| 9 | Untrained GGUF adapter loads on Q1_0 base | PASS | zero adapter runtime test |
| 10 | Trained PEFT adapter converts to GGUF | PASS | trained conversion |
| 11 | Trained GGUF adapter loads on Q1_0 base | PASS | D server log |
| 12 | Adapter behavior survives on Q1_0 | FAIL | C versus D and B versus D |
| 13 | Offline evaluation works | PASS | HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE |
| 14 | Portable bundle created | PASS | model-weight-free ZIP |
| 15 | Exact reproduction commands documented | PASS | README.md |

## Measured run

- RTX 3050 VRAM: 4096 MiB
- Selected QLoRA profile: rank `8`, sequence `512`, gradient accumulation `16`
- Peak allocated VRAM: `3378676736` bytes
- Mean optimizer-step time: `76.37033333333495` seconds
- Total capped training-process time, including the recovered OOM: `3603.93800000002` seconds
- Final adapter: `D:\Research_Engine\pixieology\bonsai_1p7b_q1_lora_feasibility\output\artifacts\runs\smoke-v1\adapter`
- Resume observed: `True`
- PEFT-to-GGUF: `PASS`
- Q1 strict behavioral gate: `FAIL`
- Q1 adapter load confirmed: `True`
- Q1 detectable canary transfer: `True`
- Forced-offline execution confirmed: `True`
- Portable bundle: `D:\Research_Engine\pixieology\bonsai_1p7b_q1_lora_feasibility\output\bundles\bonsai-1p7b-feasibility-smoke-v1.zip`

## Behavioral gate

| Mode | Canary exact | `sproutlight` marker |
|---|---:|---:|
| A: HF 4-bit base | 0/8 | 0/8 |
| B: HF 4-bit + PEFT | 4/8 | 0/8 |

The predeclared 6/8 canary + 6/8 style-marker gate still fails; the overall decision therefore remains RED.
A post-gate deployment diagnostic was run without weakening that threshold: the trained PEFT adapter converted to GGUF, loaded separately with `--lora`, and moved native Q1_0 canary accuracy from 0/8 to 4/8. This is a detectable transport signal, not acceptance of the personality recipe.

## Recovered interruption

The first 20-to-30 process aborted after `837.8910000000033` seconds with `RuntimeError('CUDA error: out of memory\nCUDA kernel errors might be asynchronously reported at some other API call, so the stacktrace below might be incorrect.\nFor debugging consider passing CUDA_LAUNCH_BLOCKING=1\nCompile with `TORCH_USE_CUDA_DSA` to enable device-side assertions.\n')`. It resumed from the last atomic checkpoint and completed; post-checkpoint metrics from the abandoned attempt are retained separately.

## Reproduction

```powershell
python -m pixie_bonsai.cli doctor
python -m pixie_bonsai.cli smoke-all
```
