# Evaluation Card — reachability-information-gain-confirmation-v0-2

**Declared claim:** On a seed-held-out paired ensemble, a registered-action reachability certificate strictly improves identification of finite-horizon control class over a passive manifold view when passive dynamics are fixed.
**Policy:** `base`

## Executive verdict

- **Task result:** control_view on the collapsed item-level comparison.
- **Measurement reliability:** grade **B**; declared limits met.
- **Claim support:** **supported** — The lower confidence bound clears the prespecified item-level win-rate threshold.
- **Operational decision:** **accept** — The item-level claim and evaluator reliability both clear declared thresholds.

## Task result

- Independent dataset items observed: **256**
- Declared dataset items: **256** (coverage 100.0%)
- Raw judge invocations: **1024**
- Decisive judge invocations: **1024**
- Ties: **0** (0.0%)
- Uncertain: **0** (0.0%)
- First-position win rate: **50.0%**

### Declared primary comparison

- Primary: `control_view`
- Baseline: `passive_view`
- Collapsed decisive items: **256**
- Primary wins / baseline wins / ties: **256 / 0 / 0**
- Primary item-level win rate: **100.0%**
- 95.0% Wilson interval: **98.5%–100.0%**
- Required win rate: **98.0%**

> Repeated judge calls, prompt variants, display orders, and judge identities are collapsed to one modal verdict per dataset item.

## Measurement reliability

- Repeat flip rate: **0.0%** (0/512 repeated-verdict pairs disagree)
- Position-sensitive fraction: **0.0%** (0/256 matched groups)
- Prompt-sensitive fraction: **n/a** (0/0 matched groups)
- Cross-judge Cohen's κ: **n/a**
- Same-family preference: **n/a** across 0 asymmetric exposures
- Hard-fail selection rate: **0.0%** (0 selections)
- Deterministic coverage: **100.0%** (3584/3584 expected candidate-item checks)

### Reliability gates

- **PASS** `repeat_flip_rate`: 0.000 <= 0.000
- **PASS** `position_sensitive_fraction`: 0.000 <= 0.000
- **PASS** `hard_fail_selection_rate`: 0.000 <= 0.000
- **PASS** `deterministic_coverage_rate`: 1.000 >= 1.000
- **PASS** `dataset_item_count`: 256.000 == 256.000

## Adjudication and rerun queue

**0 item(s)** were queued because disagreement or deterministic conflict was observed.


## Data quality

- Valid judgment rows: **1024 / 1024**
- JSONL parse errors: **0**
- Invalid judgment rows: **0**
- Deterministic rows: **3584**

## Interpretation constraint

This card audits the recorded evaluation protocol. It does not establish external validity beyond the declared dataset, and it does not convert repeated judge calls into additional independent task samples.
