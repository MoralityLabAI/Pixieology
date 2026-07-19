# Bonsai 1.7B QLoRA → GGUF-LoRA → native Q1_0 feasibility

This is a deliberately tiny, local-only evidence harness. It proves or disproves
the risky deployment path before any 8B spend: a frozen Bonsai-1.7B base is loaded
in 4-bit NF4, LoRA is attached to every transformer linear layer, and the separate
adapter is converted to GGUF and loaded against Prism's native Q1_0 base.

The primary experiment never merges the adapter, trains embeddings or `lm_head`,
changes the tokenizer, uploads artifacts, or silently falls back to attention-only
LoRA. Missing evidence is reported as NOT RUN.

## Windows setup

Copy `.env.local.example` to `.env.local` and point all large/cache paths at a drive
with at least 12 GB free. These five variables are the complete path surface:
`HF_HOME`, `MODEL_CACHE`, `DATA_ROOT`, `OUTPUT_ROOT`, and `LLAMA_CPP_ROOT`.

```powershell
$env:WANDB_DISABLED = 'true'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:TOKENIZERS_PARALLELISM = 'false'
python -m pip install -e '.[test]'
python -m pytest
python -m pixie_bonsai.cli doctor
```

GPU commands refuse to run unless `scripts/run_capped.ps1` has applied the hard
Windows Job Object caps: 10 GB job memory, 50% CPU, 50 MB/s I/O, and 30 minutes.
The orchestrator applies a fresh cap to each stage:

```powershell
python -m pixie_bonsai.cli smoke-all
```

Individual commands are also available:

```powershell
python -m pixie_bonsai.cli doctor
python -m pixie_bonsai.cli build-llama
powershell -File scripts/run_capped.ps1 -Executable python -ChildArguments @('-m','pixie_bonsai.cli','preflight-adapter') -RunId preflight -OutputDirectory $env:OUTPUT_ROOT\capped
powershell -File scripts/run_capped.ps1 -Executable python -ChildArguments @('-m','pixie_bonsai.cli','memory-probe') -RunId probe -OutputDirectory $env:OUTPUT_ROOT\capped
powershell -File scripts/run_capped.ps1 -Executable python -ChildArguments @('-m','pixie_bonsai.cli','train-smoke','--target-step','10') -RunId train10 -OutputDirectory $env:OUTPUT_ROOT\capped
powershell -File scripts/run_capped.ps1 -Executable python -ChildArguments @('-m','pixie_bonsai.cli','train-smoke','--target-step','20') -RunId train20 -OutputDirectory $env:OUTPUT_ROOT\capped
powershell -File scripts/run_capped.ps1 -Executable python -ChildArguments @('-m','pixie_bonsai.cli','train-smoke','--target-step','30') -RunId train30 -OutputDirectory $env:OUTPUT_ROOT\capped
python -m pixie_bonsai.cli report
python -m pixie_bonsai.cli bundle
```

Every five optimizer steps (or five minutes) an atomically finalized checkpoint is
saved. `train-smoke` finds the latest complete checkpoint automatically, including
optimizer, scheduler, Python, Torch, and CUDA RNG state. Failed runs retain an abort
record and logs. `bundle` excludes base weights but includes the latest resumable
checkpoint, both adapter formats, datasets and hashes, raw generations, exact model
and llama.cpp revisions, package freeze, hardware report, and `SHA256SUMS`.

## Fixed gates

The held-out evaluation has eight unseen canary paraphrases and eight ordinary
greetings. The adapter must reach at least 6/8 exact canary responses and 6/8 uses
of `sproutlight`, improving by at least 4/8 over each corresponding base. Native Q1
may trail the adapted HF mode by no more than 2/8 on either trait.

GREEN requires every acceptance row. YELLOW means local all-linear QLoRA works but
the separate Q1 adapter path has a fixable conversion/runtime issue. RED means the
all-linear path cannot fit even at rank 4/256, violates tensor invariants, or fails
to learn the canary at the fixed 30-step budget.

