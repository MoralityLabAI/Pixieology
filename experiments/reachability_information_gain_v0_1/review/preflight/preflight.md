# Eval Preflight — reachability-information-gain-v0-1

**Claim:** A registered-action reachability certificate strictly improves identification of finite-horizon control class over a passive manifold view when passive dynamics are held fixed.
**Policy:** `base`
**Status:** **FAIL**
**Release blocking:** yes

## Findings

### HIGH — `contamination_check_missing` · **BLOCKING**

No completed contamination check is declared.

**Required repair:** Document and run a contamination or train/eval leakage check before making comparative claims.

### HIGH — `order_randomization_missing` · **BLOCKING**

The protocol does not explicitly randomize display order.

**Required repair:** Set pairwise.randomize_order: true with a reproducible seed.

### HIGH — `ties_forced_off` · **BLOCKING**

The protocol does not explicitly allow ties.

**Required repair:** Set pairwise.allow_tie: true so close cases are not converted into fabricated certainty.

### MEDIUM — `adapter_deterministic_coverage_gap`

The 'generic' adapter recommends deterministic checks that are not declared.

**Required repair:** Add the applicable checks or document why each omitted invariant is out of scope.

### MEDIUM — `holistic_rubric`

The LLM-judge rubric is not decomposed into enough observable dimensions.

**Required repair:** Separate correctness, task completion, policy compliance, epistemic honesty, and style where applicable.

### LOW — `adapter_subjective_dimension_gap`

The 'generic' adapter recommends subjective dimensions that are not declared.

**Required repair:** Add the applicable dimensions or record a scoped omission in the manifest.
