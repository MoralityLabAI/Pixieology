# Counterbalanced retail comparison

This protocol tests the actual product hypothesis: whether arranging five character
traits as `2 + 2 + 1` on a visible body and similarity map improves editing over an
ordinary flat list. Both conditions use the same tuple model, labels, authored
forms, tasks, undo behavior, and deterministic scoring. Only the embodiment and
map are removed in the flat condition.

## Sample and ordering

Use six first-time players, identified only as `P01` through `P06`. Each player
completes two rounds. The participant ID deterministically counterbalances the
order, producing three embodied-first and three flat-first players.

From the repository root, launch each round through the configured runner:

```powershell
python .\run_godel_globes_study.py launch --participant P01 --round 1
python .\run_godel_globes_study.py launch --participant P01 --round 2
```

Repeat for `P02` through `P06`. Do not explain the anatomy or the map before the
first round. Let the on-screen task text supply all instructions. Export the local
JSON receipt after each round, then ingest the downloaded file:

```powershell
python .\run_godel_globes_study.py ingest --file <downloaded-receipt.json>
```

The study stores no network data and has no telemetry. Participant IDs should be
anonymous study codes, never names or email addresses.

Completed tasks are saved in the local browser so a reload resumes at the next
task. Export remains disabled until all five task results and the debrief exist;
the repo-level ingest command also rejects incomplete exports.

## Registered decision rule

The comparative gate passes only when all of the following hold:

1. all six players provide both conditions and all five task results;
2. embodied completion rate is at least the flat completion rate;
3. embodied median completion time is no more than 10% slower than flat;
4. embodied median wrong-dimension actions are no greater than flat;
5. at least five of six players identify the head as Reflection's location;
6. at least five of six describe map distance as approximate character similarity,
   not literal model geometry or capability.

Preference is reported but is not a validity gate. A failed comparison is useful
evidence to revise or reject the strategy; do not reinterpret it as success.

## Analyze

From the repository root:

```powershell
python .\run_godel_globes_study.py status
python .\run_godel_globes_study.py analyze
```

The runner reads and writes the configured `paths.godel_globes_study_receipts` and
`paths.godel_globes_ab_result` locations. The analyzer returns `PASS`, `FAIL`, or
`NOT_RUN`, condition summaries, human answers, and every registered gate. It
rejects duplicate participant/condition receipts instead of silently choosing one.
