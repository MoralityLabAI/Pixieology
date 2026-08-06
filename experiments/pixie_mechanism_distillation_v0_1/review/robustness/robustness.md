# Metric Robustness Card — pixie-mechanism-score-robustness-v1

**Construct:** causally faithful compact transition mechanism
**Evidence scope:** `held_out`
**Metric robustness:** **supported on declared holdout**

## Five separated conclusions

1. **Metric robustness:** supported_on_declared_holdout.
2. **Task result:** 5/5 staged observation rows passed.
3. **Measurement reliability:** plan coverage 100.0%; 0 repeated-family disagreements.
4. **Claim support:** supported — Every declared metric cleared its prespecified held-out robustness gates.
5. **Operational decision:** accept — Every declared metric cleared its prespecified held-out robustness gates.

## Per-metric gates

### `mechanism_evidence_score` — supported_on_declared_holdout

- **PASS** `anti_gaming_independent_families`: 1.000 >= 1.000
- **PASS** `attack_escape_rate`: 0.000 <= 0.000
- **PASS** `clean_control_independent_families`: 1.000 >= 1.000
- **PASS** `false_positive_rate`: 0.000 <= 0.000
- **PASS** `invariance_independent_families`: 1.000 >= 1.000
- **PASS** `invariance_pass_rate`: 1.000 >= 1.000
- **PASS** `monotonicity_independent_families`: 1.000 >= 1.000
- **PASS** `monotonicity_violation_rate`: 0.000 <= 0.000
- **PASS** `sensitivity_independent_families`: 1.000 >= 1.000
- **PASS** `sensitivity_pass_rate`: 1.000 >= 1.000
- **PASS** `all_probe_families_held_out`: 1.000 is 1.000

## SAE/VPD mechanistic hooks

Observed hooks: **0**. Status counts: `{}`.

SAE activation features and VPD parameter components can corroborate or falsify a declared mechanism. They cannot upgrade failed or missing behavioral metric probes.

## Scope constraint

Support is local to the declared construct, metrics, probe families, and split.
