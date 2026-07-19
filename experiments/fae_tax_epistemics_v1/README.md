# Fae Tax on Epistemics v1

This frozen study asks whether the fae system prompt changes epistemic discipline on
ALife's 63-task hidden-oracle discovery curriculum. It is a paired model-only prompt
intervention, not evidence about human or general cognition.

## Local gate

Use Python 3.11. Clone ALife at the exact frozen commit without moving another working
checkout:

```bash
git clone https://github.com/MoralityLabAI/ALife.git external/ALife
git -C external/ALife checkout --detach f9c00d1200dfffdf1800a3cd3752b3f794284e20
python -m pytest -q tests/test_fae_tax_epistemics.py
python run_fae_tax_epistemics.py \
  --manifest experiments/fae_tax_epistemics_v1/manifest.json \
  --alife-root external/ALife \
  --results-root data/fae_tax_epistemics/results \
  --provider local \
  port --samples 3
```

The port gate must reproduce the reference holdout scores, the canonical episode
SHA-256, and the ALife determinism receipt exactly before any model is served.

## Build a portable source archive

```bash
python experiments/fae_tax_epistemics_v1/stage_pod_source.py \
  --repo-root . \
  --destination ../fae_tax_pod_source.tar.gz
```

The archive omits models, caches, results, secrets, and the ALife checkout. It includes
an internal `SOURCE_MANIFEST.json` and an external `.sha256` sidecar. On the pod,
extract it and clone ALife at the frozen commit shown above.

If Prime CLI 0.5.36 fails on Windows with `No module named 'fcntl'`, authenticate with
the repo-local non-tunnel compatibility launcher. It does not patch Prime or read the
API key:

```powershell
& "$env:APPDATA\uv\tools\prime\Scripts\python.exe" `
  experiments\fae_tax_epistemics_v1\prime_windows_compat.py login
```

The same launcher can run `whoami`, `availability`, and `pods` commands. Use Linux or
WSL for Prime tunnel commands.

The current Prime default may point at a missing `~/.ssh/id_rsa`. Configure an existing
private key whose public half is registered in the Prime profile, for example:

```powershell
& "$env:APPDATA\uv\tools\prime\Scripts\python.exe" `
  experiments\fae_tax_epistemics_v1\prime_windows_compat.py `
  config set-ssh-key-path "$HOME\.ssh\id_ed25519"
```

After authentication, run the read-only provider preflight through the same Prime
Python environment:

```powershell
& "$env:APPDATA\uv\tools\prime\Scripts\python.exe" `
  experiments\fae_tax_epistemics_v1\prime_pod_gate.py preflight `
  --receipt artifacts\prime_a100_preflight.json
```

Only one-A100 offers with at least 79 GB VRAM, 80–200 GB default disk, sufficient CPU
and RAM, and an hourly rate no greater than `$40 / 8h = $5` are eligible. On-demand
fixed-price offers sort before spot offers, and variable-price offers are rejected.
Pod creation is a separate opt-in command requiring
the selected cloud ID, exact observed hourly price, and `--yes`; its API request sets
`maxPrice` to that observed rate and disables automatic restart. The provider still
requires explicit termination when the run ends. Start the local watchdog immediately
after creation; it requests termination if the live hourly rate rises or when either
the eight-hour or $40 bound is reached:

```powershell
& "$env:APPDATA\uv\tools\prime\Scripts\python.exe" `
  experiments\fae_tax_epistemics_v1\prime_pod_gate.py watch <pod-id> `
  --receipt artifacts\prime_pod_watch.json
```

Terminate earlier as soon as the verified result bundle has been copied off the pod.

## Run on one A100 80GB pod

The portable runner supports a plain Linux pod; Slurm is optional. Set the provider's
actual hourly rate and the pod's creation epoch so setup and download time count
toward the budget:

```bash
export PROJECT_DIR="$PWD/Pixieology"
export ALIFE_ROOT="$PWD/ALife"
export RUN_BASE="$PWD/fae-tax-run"
export PROVIDER="prime_intellect"
export POD_HOURLY_USD="<actual hourly price>"
export POD_STARTED_EPOCH="<pod creation time as Unix seconds>"
export SAMPLES="auto"
bash "$PROJECT_DIR/experiments/fae_tax_epistemics_v1/run_single_a100.sh"
```

The runner verifies exactly one visible A100 with at least 79,000 MiB, installs pinned
vLLM 0.24.0 in a retained virtual environment, runs the port gate, and serves only one
model at a time. After the 36-episode 8B smoke, it projects cost from measured episode
and load time. It tries the frozen three-sample design first and falls back to two
samples before removing any model. If neither projection fits both $40 and eight-hour
limits, it stops. A paid provider cannot use a zero hourly price.

Every episode is flushed independently. Repeating the same command skips complete
episode IDs and resumes the batch. If any three-sample full episode already exists,
the runner refuses to silently downgrade the resumed study to two samples.

## Outputs

Successful execution creates:

- raw paired episodes with requests, responses, tools, seeds, and hashes;
- unchanged ALife scorer outputs and per-task paired bootstrap receipts;
- port, smoke, and final budget gate receipts;
- exact commands, source hashes, package freeze, model revisions, GPU details, and
  vLLM server logs;
- `KNOWLEDGE_CARD.md` and a verified results ZIP with SHA-256 sidecar.

The bundle command refuses incomplete scores, failed gates, a non-final budget receipt,
or a receipt whose sample count differs from the scored run.
