# Multi-adapter non-inferiority protocol v1

This protocol tests whether the additive `companion + storyworld` condition
retains the behavior of each singleton adapter. It uses the already frozen
four-condition matrix: base, companion alone, Storyworld alone, and stacked.

The primary companion estimand is the paired mean difference between stacked
and companion-only semantic scores on eight held-out reflective-buddy probes.
The primary action estimand is the paired mean difference between stacked and
Storyworld-only exact-action scores on eight entity-transferred Storyworld
probes. The non-inferiority margin is `0.05` for both. Four joint probes are a
secondary stress test and do not replace either primary estimand.

Semantic scoring uses the pinned, locally cached
`sentence-transformers/all-MiniLM-L6-v2` revision
`1110a243fdf0bc927268c1653cce6948c5c242dd1`. Each response is compared with a
frozen rubric-derived reference without exposing condition, scale, adapter, or
treatment labels to the encoder. This measures semantic proximity rather than
mere token overlap, but it is not NLI and cannot reliably detect every negation
or subtle contradiction. Exact Storyworld action scoring remains programmatic.

The analysis uses 10,000 paired, stratified bootstrap resamples. It reports a
two-sided percentile 95% confidence interval for each stacked-minus-singleton
difference:

- `PASS`: both point estimates meet `-0.05` and both lower confidence bounds
  are at least `-0.05`;
- `FAIL`: either point estimate is below `-0.05`;
- `INCONCLUSIVE`: point estimates meet the margin but at least one lower
  confidence bound does not.

The protocol is frozen before the first real run. Missing model revisions,
non-finite embeddings, incomplete paired rows, or scorer failures abort the
analysis rather than being repaired. Both model inference and semantic scoring
remain inside the 2 GiB RAM, 50% CPU, 50 MB/s I/O Job Object cap.
