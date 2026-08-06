# Evaluation Card — pixie-mechanism-distillation-v0-1

**Declared claim:** Pixie rank-8 admits a shorter causally faithful held-out transition program than its frozen Qwen-derived 1.7B base on the sealed finite-state family set.
**Policy:** `base`

## Executive verdict

- **Task result:** tie on the collapsed item-level comparison.
- **Measurement reliability:** grade **C**; declared limits not met.
- **Claim support:** **undetermined** — No decisive item-level verdicts compare the declared primary and baseline candidates.
- **Operational decision:** **targeted rerun** — Evaluator reliability does not meet declared limits; 0 item(s) are queued for adjudication or counterbalanced rerun.

## Task result

- Independent dataset items observed: **8**
- Declared dataset items: **32** (coverage 25.0%)
- Raw judge invocations: **32**
- Decisive judge invocations: **0**
- Ties: **12** (37.5%)
- Uncertain: **20** (62.5%)
- First-position win rate: **n/a**

### Declared primary comparison

- Primary: `pixie_rank8`
- Baseline: `base_qwen_derived_1p7b`
- Collapsed decisive items: **0**
- Primary wins / baseline wins / ties: **0 / 0 / 3**
- Primary item-level win rate: **n/a**
- 95.0% Wilson interval: **n/a–n/a**
- Required win rate: **60.0%**

> Repeated judge calls, prompt variants, display orders, and judge identities are collapsed to one modal verdict per dataset item.

## Measurement reliability

- Repeat flip rate: **0.0%** (0/6 repeated-verdict pairs disagree)
- Position-sensitive fraction: **0.0%** (0/3 matched groups)
- Prompt-sensitive fraction: **n/a** (0/0 matched groups)
- Cross-judge Cohen's κ: **n/a**
- Same-family preference: **n/a** across 0 asymmetric exposures
- Hard-fail selection rate: **n/a** (0 selections)
- Deterministic coverage: **100.0%** (128/128 expected candidate-item checks)

### Reliability gates

- **PASS** `repeat_flip_rate`: 0.000 <= 0.000
- **PASS** `position_sensitive_fraction`: 0.000 <= 0.000
- **FAIL** `hard_fail_selection_rate`: n/a <= 0.000
- **PASS** `deterministic_coverage_rate`: 1.000 >= 1.000
- **FAIL** `dataset_item_count`: 8.000 == 32.000

## Adjudication and rerun queue

**0 item(s)** were queued because disagreement or deterministic conflict was observed.


## Data quality

- Valid judgment rows: **32 / 32**
- JSONL parse errors: **0**
- Invalid judgment rows: **0**
- Deterministic rows: **128**

## Interpretation constraint

This card audits the recorded evaluation protocol. It does not establish external validity beyond the declared dataset, and it does not convert repeated judge calls into additional independent task samples.
