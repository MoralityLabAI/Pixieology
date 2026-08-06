# Preregistration

## Primary question

Does the frozen Pixie rank-8 adapter admit a shorter mechanism than its frozen
base while retaining held-out behavioral fidelity and causal intervention
predictiveness?

## Independent unit

The independent unit is one procedurally generated finite-state task family,
not a trace row, prompt skin, token position, intervention repetition, or judge
call. There are 32 task families generated after adapter training with seed
`2026080601`. Results collapse to one verdict per family.

## Frozen method

- Capture pre-state and post-state activations at the registered sites.
- Fit deterministic Euclidean codebooks for `k=1..8` using discovery traces.
- Select the smallest `k` whose discovery transition-and-output fidelity is at
  least `0.98`; if none qualifies, select maximum fidelity then minimum `k`.
- Fit a majority transition table keyed by `(discrete_state, input_symbol)`.
- Select up to three activation dimensions whose rounded state centroids become
  unique; report their held-out agreement with full-codebook assignments.
- Evaluate once on held-out traces.
- Align base and Pixie state labels by exhaustive bijection when state counts
  match and are at most eight.

## Per-family hard gates

- candidate task accuracy: at least `0.80`;
- held-out program fidelity: at least `0.90`;
- sparse-invariant agreement: at least `0.90`;
- causal prediction accuracy: at least `0.80`;
- causal advantage over matched random controls: at least `0.50`;
- mean absolute guardrail delta: at most `0.05`.

Pixie wins a family only if both conditions clear all hard gates and Pixie's
program description length is at least 10% lower. Ties remain ties.
The comparative claim requires a Pixie win rate of at least `0.60` over all 32
families with the registered 95% Wilson lower bound above `0.50`.

## Isomorphism verdict

`USABLE_ISOMORPHISM` requires equal state counts, a bijective mapping, and
transition/output alignment fidelity at least `0.90`. Lower alignment is
`POSSIBLE_ALGORITHM_CHANGE`. Missing causal observations is `NOT_RUN`, never a
pass.

## Conclusion layers

1. Metric robustness: the frozen stress pack must pass before confirmation.
2. Task result: report task accuracy and extracted-program fidelity separately.
3. Measurement reliability: report coverage, deterministic reproducibility,
   and missing or conflicted observations.
4. Claim support: apply only the frozen family-level decision rule.
5. Operational decision: accept, rerun, redesign, or reject.

Synthetic smoke can validate implementation behavior only. It cannot support a
claim about Qwen, Pixie, a human-readable algorithm, or causal control.
