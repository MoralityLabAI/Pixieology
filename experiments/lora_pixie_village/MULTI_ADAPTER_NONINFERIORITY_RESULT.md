# Multi-adapter non-inferiority result v1

## Outcome

- Overall verdict: **NOT_ESTIMATED**.
- Companion retention checkpoint: **PASS**.
- Storyworld exact-action retention: **NOT_ESTIMATED**.
- Joint stress test: **NOT RUN**.

The additive stack improved the frozen companion semantic-proximity score by
`0.0165757` relative to the companion singleton. The paired,
family-stratified 10,000-resample 95% bootstrap interval was
`[-0.0082168, 0.0413682]`, above the preregistered non-inferiority boundary of
`-0.05`. Singleton and stacked means were `0.3942760` and `0.4108517`.

This supports retention of the measured companion behavior in the additive
stack. It does not establish general semantic equivalence: MiniLM cosine is a
lexical-semantic proximity matcher, not NLI.

## Bounded negative result

All 16 companion rows completed. The first exact-action request then remained
compute-active for 900 seconds under the required 50% CPU Job rate without
producing a complete row. Earlier attempts identified and corrected two
independent 240-second transport timeouts; the 900-second attempt therefore
measures the bounded runtime lane rather than another client timeout. The
action and joint suites stopped mechanically instead of weakening the caps or
changing the frozen prompts post hoc.

The action failure receipt records `FAIL_HARNESS` with scientific verdict
`NOT_ESTIMATED`. Its 30-minute Job limits did not breach, peak Job memory was
`980,537,344` bytes, and owned-process cleanup passed. The successful semantic
scoring Job peaked at `1,779,138,560` bytes and also cleaned up fully.

## Evidence

- Frozen protocol: `config/multi_adapter_noninferiority_v1.json`
- Protocol documentation: `MULTI_ADAPTER_NONINFERIORITY.md`
- Operational deviations: `MULTI_ADAPTER_NONINFERIORITY_DEVIATION_001.md`
- Overall/failed-action pointer: `reports/multi_adapter_noninferiority.receipt.json`
- Companion result pointer: `reports/multi_adapter_noninferiority_companion.receipt.json`
- First-attempt pointer: `reports/multi_adapter_noninferiority_attempt_001.receipt.json`

Raw generations, chunk receipts, cap summaries, launch manifests, and the
MiniLM analysis remain under the configured `paths.lora_pixie_village_runtime`
root. No adapter scale, model, prompt, seed, decoding limit, scorer, margin, or
bootstrap rule was changed after protocol freeze.
