# Reachability information-gain experiment v0.1

A blinded deterministic experiment testing whether the observatory's registered-action reachability certificate adds identifiable control information beyond passive state trajectories.

The experiment uses 256 held-out paired systems. Within each pair, `A`, the initial state, and every passive trajectory are identical; only registered intervention `B` differs. Candidate order is exactly counterbalanced.

## Run order

```powershell
python run_experiment.py stage
C:\projects\evals-reviewer\.venv\Scripts\python.exe -m evals_reviewer preflight manifest.yaml --policy base --out review\preflight
python run_experiment.py run
C:\projects\evals-reviewer\.venv\Scripts\python.exe -m evals_reviewer audit manifest.yaml results --policy base --out review\audit
python run_experiment.py stage --seed 20260809 --results-dir results_confirmation --manifest manifest_confirmation.yaml
C:\projects\evals-reviewer\.venv\Scripts\python.exe -m evals_reviewer preflight manifest_confirmation.yaml --policy base --out review\preflight_confirmation
python run_experiment.py run --seed 20260809 --results-dir results_confirmation --manifest manifest_confirmation.yaml
C:\projects\evals-reviewer\.venv\Scripts\python.exe -m evals_reviewer audit manifest_confirmation.yaml results_confirmation --policy base --out review\audit_confirmation
```

See `PROTOCOL.md` for frozen claims and decision rules.

## Confirmed result

The development audit requested a targeted rerun and is preserved. The separate seed-held-out confirmation was accepted:

- passive: `128 / 256` (`50%`);
- reachability certificate: `256 / 256` (`100%`);
- information addition: exactly `1 bit`;
- repeat flips and position sensitivity: `0%`;
- deterministic coverage: `3,584 / 3,584`;
- confirmation audit: `supported`, reliability grade `B`, operational action `accept`.

Read `EXPERIMENT_REPORT.md` and `results_confirmation/final_receipt.json` for the hash-bound handoff. The result proves information availability on the exact synthetic system family; it does not prove neural-model controllability or human comprehension.
