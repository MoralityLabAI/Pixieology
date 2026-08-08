# Reachability information-gain experiment report

## Outcome

The seed-held-out confirmation experiment supports the declared synthetic claim and was independently accepted by the evaluation audit.

| Measure | Passive view | Reachability view |
|---|---:|---:|
| Correct paired identifications | 128 / 256 | 256 / 256 |
| Accuracy | 50.0% | 100.0% |
| 95% Wilson interval | 43.9%–56.1% | 98.5%–100.0% |
| Conditional class entropy | 1 bit | 0 bits |

The measured information addition is exactly `1 bit` on the declared paired ensemble. All 512 exact certificates preserved reachable rank under registered unimodular coordinate changes. Passive observations contained zero oracle/action fields.

## Metric robustness

The exact metric passed the clean exact control and coordinate-invariance probes. The pre-registered noise sweep identifies a model-facing limit:

| Gaussian noise on `B` | Thresholded candidate accuracy | Pairwise rank-order accuracy |
|---:|---:|---:|
| 0 | 100.0% | 100.0% |
| 0.001 | 96.2% | 100.0% |
| 0.01 | 64.9% | 99.9% |
| 0.05 | 53.6% | 92.6% |
| 0.10 | 51.8% | 83.0% |

This does not invalidate the exact theorem. It rejects a naive model-facing UX that displays thresholded rank without estimator uncertainty. Pairwise reachability ordering is substantially more robust, but it also needs calibration and an abstention region.

## Task result

The passive decoder was fixed to choose anonymous candidate A. Exact counterbalancing forces 128 correct and 128 incorrect. The certificate decoder selected the candidate with `rank([B,AB])=2` and was correct on all 256 held-out items. The accuracy difference was `+50 percentage points`.

## Measurement reliability

The initial development evaluation was not relabeled as success: its audit requested a targeted rerun because deterministic coverage and judge-reliability declarations were mismatched. A separate confirmation manifest and seed were then frozen before confirmation outcomes.

The confirmation audit reported:

- grade `B`, declared limits met;
- 1,024 exact judge invocations collapsed to 256 independent items;
- repeat flip rate `0%` over 512 repeated-verdict pairs;
- position-sensitive fraction `0%` over 256 matched groups;
- deterministic coverage `3,584 / 3,584`;
- zero invalid JSONL rows and zero adjudication items.

## Claim support

The audit status is `supported`: the control view won 256/256 collapsed items and its 98.5% Wilson lower bound cleared the pre-registered 98% generic audit threshold. Separately, the experiment's exact decision rules all passed: passive 0.5, control 1.0, information gain 1 bit, coordinate invariance 1.0, and zero leaks.

## Operational decision

**Admit the exact reachability certificate as a proven information-bearing UX primitive.** Do not yet admit a neural-model controllability claim or a human-usability claim.

For neural data, the next experiment must estimate local `A` and registered intervention `B`, calibrate the normalized singular-value ratio and abstention band on development data, and verify predicted reachable endpoints on a sequestered intervention split.

## Evidence

- `results_confirmation/final_receipt.json`: compact hash-bound result
- `results_confirmation/summary.json`: task and noise outcomes
- `review/preflight_confirmation/preflight.json`: non-blocking preflight
- `review/audit_confirmation/audit.json`: accepted independent audit
- `review/audit/audit.json`: preserved development targeted-rerun verdict
- `results_confirmation/passive_observations.jsonl`: blinded passive inputs
- `results_confirmation/control_observations.jsonl`: certificate inputs
- `results_confirmation/exact_certificates.jsonl`: row-level exact algebra
