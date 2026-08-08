# Captain Rowan prompt-adapter plan

## Implemented lane

`captain_rowan_prompt_adapter_r1` is a prompt-prefix adapter plus a closed-form rank-one representation rehearsal. It compiles five MeTTa facts into a bounded persona prefix and a 21-step UI signal trace.

- Model weights loaded: **no**
- Gradient training executed: **no**
- GPU/CUDA used: **no**
- External model calls: **no**
- Run status: `closed_form_synthetic_rehearsal`

The signal trace is allowed to animate the synthetic ablation structures, but it is not evidence that a neural adapter learned those structures.

## Future neural adapter lane

A real TinyLoRA/QLoRA continuation is intentionally not auto-authorized by this prompt-adapter build. Its preregistered defaults would be:

- training task id: `captain-rowan-five-fact-tinylora-v1`;
- hard caps: 2048 MiB RAM, 50% CPU, 50 MiB/s I/O, plus an explicitly authorized VRAM ceiling;
- chunk strategy: one fact family per chunk, followed by one mixed consolidation chunk;
- checkpoint cadence: every five optimizer steps or 60 seconds, whichever occurs first;
- abort semantics: cap breach, swap, sustained I/O spike, timeout, or cleanup failure are valid structured outcomes;
- evaluation: five fact probes, five paraphrases, five boundary probes, matched base comparison, and collateral-behavior checks;
- cleanup: recorded-PID process-tree cleanup plus explicit model/tokenizer/tensor release and CUDA/DRAM audit.

Before that lane may run, it needs a new exact-job authorization containing the model and adapter paths, dataset hashes, hard caps, timeout, checkpoint interval, chunk strategy, and cleanup receipt locations. Previous job authorizations do not transfer.
