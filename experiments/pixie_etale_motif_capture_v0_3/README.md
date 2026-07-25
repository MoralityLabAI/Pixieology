# Pixie etale motif capture v0.3

This package stages the five-family continuation of the successful v0.2
canary capture. It uses the same frozen Bonsai/Pixie model pair, corpus,
response coordinates, module inventory, and resource envelope.

The exact job covers corpus rows 32 through 191:

| Chunk | Family | Rows | Discovery | Confirmation | Transfer |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | `pixie_style` | 32 | 16 | 8 | 8 |
| 2 | `copy_induction` | 32 | 16 | 8 | 8 |
| 3 | `format_following` | 32 | 16 | 8 | 8 |
| 4 | `binary_fact` | 32 | 16 | 8 | 8 |
| 5 | `one_step_arithmetic` | 32 | 16 | 8 | 8 |

One process loads the model once and emits twenty independently verified
eight-row NPZ checkpoints. A checkpoint is resumed only when its artifact
hash, ordered row IDs, job hash, and capture-protocol hash all match.

## Why this is the next useful gate

The canary established that the sequential NF4 loader and capture mechanics
work under the caps. These remaining rows are needed before global
normalization or cross-family motif mining is scientifically meaningful.
Completion therefore promotes the dataset to the downstream scaler/mining
gate; it does not itself establish an isomorphism or useful motif.

## Fail-closed workflow

```powershell
python experiments/pixie_etale_motif_capture_v0_3/run.py verify
python experiments/pixie_etale_motif_capture_v0_3/run.py proposed-job
python experiments/pixie_etale_motif_capture_v0_3/run.py authorization-template
```

The generated template is inactive. The sealed `protocol.json`,
`proposed_job.json`, and `protocol.lock.json` must not change after an
authorization receipt is created.

An authorized PrimeLab run uses:

```bash
bash experiments/pixie_etale_motif_capture_v0_3/scripts/run_capped_capture_prime.sh \
  <active-authorization.json> <runtime-repo-root> <sharded-model-root> <output-root>
```

The launcher requires one idle A6000 48 GB, enforces cgroup v2 limits of
6144 MiB RAM with no swap, 50 percent of visible CPU, 250 MiB/s I/O, 1800
seconds, and a 3900 MiB peak-VRAM guard. It targets cleanup only at the
attempt-owned cgroup.

`ABORTED` is a valid operational result. No automatic retry is authorized.
No v0.3 code fits a scaler, mines or confirms motifs, runs interventions,
studies human usefulness, or trains an adapter.
