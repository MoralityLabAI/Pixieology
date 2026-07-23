# Preregistration

## Question

Does a motif-local rank-2 LoRA produce a more useful capacity-to-effect ratio than a small all-layer rank-4 QLoRA, and do either reproduce the topology that proposed the intervention?

## Frozen comparison

- Model family: `prism-ml/Bonsai-1.7B-unpacked` at revision `a7f720bd688d7563714f3118edd97b83d06f0615`.
- Reference conditions: adapter-disabled base and the existing Pixie rank-8 adapter.
- Candidate methods: motif-local TinyLoRA and all-layer QLoRA.
- Candidate origins: at most one robust bridge-free component and one fragile chained component from a registered activation-conditioned catalog.
- Training data: outcome-eligible discovery rows named by the frozen discovery motif.
- Forbidden training data: every confirmation and transfer row.
- Evaluation data: outcome-eligible transfer rows only.
- Seeds: proposal `2026072401`, training `2026072402`; `2026072403` is reserved for replication.

## Fixed training settings

Both methods use sequence length 256, 20 optimizer steps, gradient accumulation 8, learning rate `2e-4`, no dropout, no weight decay, assistant-only loss, and gradient norm 1.0.

TinyLoRA uses rank 2, alpha 4, only the origin component’s modules, and only the origin chart’s layer interval. QLoRA uses rank 4, alpha 8, all seven target module types, and all 28 layers. Both use NF4 double quantization with float16 compute.

## Registered gates

A candidate is behavior-promising only when all of these hold on transfer:

- mean log-likelihood is at least `0.05` above base;
- exact match is no worse than base;
- exact match is no more than `0.05` below Pixie.

A behavior-promising candidate remains `AWAITING_TOPOLOGY` until a separately captured candidate activation-topology receipt passes. A topology-only result cannot pass. Candidate methods are not capacity-matched: the report records adapter parameter counts and log-likelihood increment per million adapter parameters alongside the raw gates. The loop does not claim the larger method is “better” merely because it has more capacity.

## Resource and stopping rules

Every executable job is bound to 2048 MiB RAM, 50% CPU, 50 MiB/s I/O, 1800 seconds, an idle-GPU preflight, and a 3900 MiB peak reserved-VRAM guard. Checkpoints occur every 5 optimizer steps or 300 seconds, with at most two retained. Wrapper abort, CUDA guard failure, cleanup failure, or inability to load inside the RAM cap is a terminal attempt result and must be reported, not silently retried with larger resources.

## Goodhart audit

The selection heuristic can over-favor visually dramatic bridge or clique patterns. Held-out behavior is therefore primary, topology recapture is necessary but secondary, and the report preserves every candidate job rather than collapsing jobs by method. No thresholds may be changed after viewing transfer outcomes in this protocol version.
