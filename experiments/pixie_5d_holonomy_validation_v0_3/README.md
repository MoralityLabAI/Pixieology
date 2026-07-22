# Pixie 5D holonomy validation v0.3

v0.3 is the versioned response to the v0.2 loader abort. It keeps the 6 GiB
hard cap and all scientific inputs unchanged, but rewrites the frozen single-
file Bonsai checkpoint into seven byte-verified tensor-boundary shards before
loading it. See `prereg_sharded_continuation.md` for the registered claim
boundary.

Current state: **staged, not authorized**.

## CPU-safe commands

```powershell
python experiments\pixie_5d_holonomy_validation_v0_3\run.py shard-plan
python experiments\pixie_5d_holonomy_validation_v0_3\run.py verify
pytest -q experiments\pixie_5d_holonomy_validation_v0_3\tests
python experiments\pixie_5d_holonomy_validation_v0_3\run.py authorization-template
```

`shard-plan` reads only the safetensors header. `verify` hashes the full frozen
source model and may therefore take about a minute. The authorization template
is deliberately false and includes the exact loader and sharding recipes.

## Authorized execution

Only after a new v0.3-specific receipt is explicitly approved:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  experiments\pixie_5d_holonomy_validation_v0_3\scripts\run_continuation_v3.ps1 `
  -Authorization <v03-authorization.json> `
  -PythonExecutable python
```

The sharded checkpoint is written through
`paths.pixie_5d_holonomy_v03_sharded_model_root`; capture and wrapper receipts
use `paths.pixie_5d_holonomy_v03_output_root`. No user-specific path appears in
the Python or PowerShell implementation.

After a complete capture:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  experiments\pixie_5d_holonomy_validation_v0_3\scripts\run_analysis_v3.ps1
```
