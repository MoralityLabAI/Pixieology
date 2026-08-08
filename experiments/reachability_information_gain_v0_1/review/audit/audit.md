# Evaluation Card — reachability-information-gain-v0-1

**Declared claim:** A registered-action reachability certificate strictly improves identification of finite-horizon control class over a passive manifold view when passive dynamics are held fixed.
**Policy:** `base`

## Executive verdict

- **Task result:** control_view on the collapsed item-level comparison.
- **Measurement reliability:** grade **D**; declared limits not met.
- **Claim support:** **directional** — The point estimate clears the threshold, but the lower confidence bound does not.
- **Operational decision:** **targeted rerun** — Evaluator reliability does not meet declared limits; 256 item(s) are queued for adjudication or counterbalanced rerun.

## Task result

- Independent dataset items observed: **256**
- Declared dataset items: **256** (coverage 100.0%)
- Raw judge invocations: **256**
- Decisive judge invocations: **256**
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
- Required win rate: **100.0%**

> Repeated judge calls, prompt variants, display orders, and judge identities are collapsed to one modal verdict per dataset item.

## Measurement reliability

- Repeat flip rate: **n/a** (0/0 repeated-verdict pairs disagree)
- Position-sensitive fraction: **n/a** (0/0 matched groups)
- Prompt-sensitive fraction: **n/a** (0/0 matched groups)
- Cross-judge Cohen's κ: **n/a**
- Same-family preference: **n/a** across 0 asymmetric exposures
- Hard-fail selection rate: **0.0%** (0 selections)
- Deterministic coverage: **92.9%** (3328/3584 expected candidate-item checks)

### Reliability gates

- **FAIL** `repeat_flip_rate`: n/a <= 0.000
- **FAIL** `position_sensitive_fraction`: n/a <= 0.000
- **FAIL** `cross_judge_kappa`: n/a >= 1.000
- **PASS** `hard_fail_selection_rate`: 0.000 <= 0.000
- **FAIL** `deterministic_coverage_rate`: 0.929 >= 1.000
- **PASS** `dataset_item_count`: 256.000 == 256.000

## Adjudication and rerun queue

**256 item(s)** were queued because disagreement or deterministic conflict was observed.

- `reach-0000` — deterministic_coverage_gap (medium)
- `reach-0001` — deterministic_coverage_gap (medium)
- `reach-0002` — deterministic_coverage_gap (medium)
- `reach-0003` — deterministic_coverage_gap (medium)
- `reach-0004` — deterministic_coverage_gap (medium)
- `reach-0005` — deterministic_coverage_gap (medium)
- `reach-0006` — deterministic_coverage_gap (medium)
- `reach-0007` — deterministic_coverage_gap (medium)
- `reach-0008` — deterministic_coverage_gap (medium)
- `reach-0009` — deterministic_coverage_gap (medium)
- `reach-0010` — deterministic_coverage_gap (medium)
- `reach-0011` — deterministic_coverage_gap (medium)
- `reach-0012` — deterministic_coverage_gap (medium)
- `reach-0013` — deterministic_coverage_gap (medium)
- `reach-0014` — deterministic_coverage_gap (medium)
- `reach-0015` — deterministic_coverage_gap (medium)
- `reach-0016` — deterministic_coverage_gap (medium)
- `reach-0017` — deterministic_coverage_gap (medium)
- `reach-0018` — deterministic_coverage_gap (medium)
- `reach-0019` — deterministic_coverage_gap (medium)
- `reach-0020` — deterministic_coverage_gap (medium)
- `reach-0021` — deterministic_coverage_gap (medium)
- `reach-0022` — deterministic_coverage_gap (medium)
- `reach-0023` — deterministic_coverage_gap (medium)
- `reach-0024` — deterministic_coverage_gap (medium)
- …and 231 more; see `adjudication_queue.jsonl`.

## Data quality

- Valid judgment rows: **256 / 256**
- JSONL parse errors: **0**
- Invalid judgment rows: **0**
- Deterministic rows: **3328**

## Interpretation constraint

This card audits the recorded evaluation protocol. It does not establish external validity beyond the declared dataset, and it does not convert repeated judge calls into additional independent task samples.
