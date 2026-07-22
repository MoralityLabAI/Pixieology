# Pixie 5D holonomy validation v0.2

This folder resumes only the missing fourth context of the preregistered Bonsai
1.7B manifold experiment. It never reuses an artifact unless its SHA-256 and
completion marker match `protocol.json`, and it never loads the model outside
the corrected hash-pinned Windows Job Object wrapper.

Current state: **staged, cap-tested, not authorized**.

The implementation is committed first; `protocol.lock.json` is then generated
against that commit and committed separately. Every experimental command calls
the verifier and fails closed if a locked file drifts.

## CPU-safe checks

From the repository root:

```powershell
python experiments\pixie_5d_holonomy_validation_v0_2\run.py verify
pytest -q experiments\pixie_5d_holonomy_validation_v0_2\tests
python experiments\pixie_5d_holonomy_validation_v0_2\run.py authorization-template
```

The authorization template intentionally prints `authorized: false`. A fresh
receipt must name a unique attempt, contain the exact protocol SHA-256 and
caps, and be explicitly approved by the operator. No authorization receipt is
tracked in Git.

## Authorized context-3 capture

After that separate approval only:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  experiments\pixie_5d_holonomy_validation_v0_2\scripts\run_continuation.ps1 `
  -Authorization <authorization-receipt.json> `
  -PythonExecutable python
```

The run checkpoints every eight rows and is resumable through hash-verified
chunk markers. Generated data is written through
`paths.pixie_5d_holonomy_v02_output_root` in `pixieology.config.json`.
The launcher refuses to begin while another CUDA compute process exists or
existing GPU memory exceeds 256 MiB.

## CPU analysis after a complete capture

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  experiments\pixie_5d_holonomy_validation_v0_2\scripts\run_analysis_v2.ps1 `
  -PythonExecutable python
```

Analysis runs under a 2048 MiB / 50% CPU / 50 MiB/s / 600-second wrapper and
combines immutable v0.1 contexts 0–2 with v0.2 context 3. It refuses incomplete,
stale, or hash-mismatched inputs.

See `prereg_continuation.md` for the estimand, deviation boundary, abort rules,
and interpretation limits.
