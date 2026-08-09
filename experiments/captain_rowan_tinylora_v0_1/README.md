# Captain Rowan five-fact TinyLoRA v0.1

This packet turns the synthetic prompt-adapter rehearsal into a concrete, hash-bound neural-adapter proposal. It does **not** run the proposal.

## Bound job

- frozen base: `prism-ml/Bonsai-1.7B-unpacked` at revision `a7f720...`;
- reference: the existing Pixie rank-8 adapter;
- candidate: fresh rank-2, alpha-4 LoRA on `gate_proj`, layers 21–25;
- training: 20 steps, gradient accumulation 8, checkpoint every 5 steps or 60 seconds;
- data: 10 discovery rows and 10 frozen transfer rows covering five facts, composition, over-refusal, and scope preservation;
- guards: 8192 MiB RAM, 50% CPU, 50 MiB/s I/O, 1800 seconds, 3900 MiB peak VRAM;
- automatic authorization: disabled.

Run `python build_job.py` to regenerate `corpus.jsonl`, `job.json`, and `authorization.template.json` deterministically.

## Current stop condition

The existing v0.2 feedback runner remains unchanged and sealed to its original corpus. This packet supplies a hash-bound continuation entrypoint that injects only the registered `corpus.jsonl` rows while reusing the sealed model loader, trainer, evaluator, checkpoint writer, resource wrapper, and PID-scoped cleanup. `job.json` binds the continuation runner, wrapper, and compatible feedback job by SHA-256.

The job now reports `READY_AWAITING_EXACT_AUTHORIZATION`. Model loading or training must not begin until the exact statement in `authorization.template.json` is supplied as a new active authorization with concrete run, attempt, and expiry values plus every acknowledgement set to `true`.

Once authorized, the Windows entrypoint is:

```powershell
.\scripts\run_capped.ps1 -Mode Train -Authorization path\to\active.authorization.json
```

## Attempt 01 result

The exact authorized attempt `captain-rowan-local-01` ran on 2026-08-08 and
ended `ABORTED` when Windows Job Object accounting reached 8211.64 MiB against
the 8192 MiB hard RAM cap. Peak observed GPU memory was 2995 MiB, below the
3900 MiB guard. The process was still loading model weights, so it completed no
optimizer step, emitted no adapter checkpoint, and produced no behavioral or
mechanistic comparison result.

The follow-up PID-scoped audit passed after Job Object termination settled:
both owned PIDs were absent and no owned GPU process remained. See
`attempt_01_result.json` for the bounded claim and receipt hashes. Retrying,
changing the cap, or changing the loading strategy requires a new exact
authorization.

## Staged v0.1.1 retry

After explicit approval of a 10 GiB cap, `job_v0_1_1.json` stages a retry with
10240 MiB RAM. This is the only changed resource or training parameter. The
retry launcher binds the original sealed trainer, the attempt-01 abort receipt,
the new Windows Job Object wrapper, and the unchanged PID-scoped cleanup path.

The packet remains inactive. Its exact statement is stored in
`authorization_v0_1_1.template.json`; a generic approval cannot activate it.
