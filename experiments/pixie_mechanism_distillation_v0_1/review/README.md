# Evaluation review boundary

The preflight report is a real design review of the frozen manifest under
`evals-reviewer` policy `base`; it passed with no findings.

The metric-robustness report consumes five oracle-labeled **synthetic metric
fixtures**. Its `supported_on_declared_holdout` verdict means the scoring code
behaves correctly on this staged pack. It is not evidence that real Qwen or
Pixie mechanisms are robust, compact, causal, or interpretable. Those claims
remain `NOT_RUN` until registered activation and intervention receipts exist.

The synthetic audit intentionally returns `TARGETED_RERUN`: it covers only
eight implementation-fixture families against a declared 32-family model
claim, produces no decisive base/Pixie winner, and therefore cannot satisfy the
claim or dataset-coverage rule. Deterministic-check coverage, repeat stability,
and position stability are complete for the rows that do exist; the exported
adjudication queue is empty because the missing evidence requires capture, not
subjective adjudication.

Conclusion layers at this checkpoint:

1. Metric robustness: development fixture pass; real confirmation not run.
2. Task result: synthetic smoke pass only.
3. Measurement reliability: deterministic code paths covered; model capture
   coverage is zero.
4. Claim support: not run for the declared base-versus-Pixie claim.
5. Operational decision: implementation ready; do not run model inference
   without a new exact authorization receipt.
