# Pixieology

Pixieology is the local orchestration repo for the current Pixue product lane: storyworld SFT data building, faebench evaluation, and reflective-buddy distillation assets.

The script workflows and the installable evaluator share one portable config surface instead of a fixed workstation layout.

## Repo Layout

- `build_pixie_storyworld_sft_env.py`: builds the mixed, action-only, and prose-only storyworld training JSONL files.
- `run_pixie_storyworld_sft.py`: runs the current storyworld QLoRA training passes.
- `build_faebench_env.py`: builds the faebench eval set.
- `run_faebench_compare.py`: compares base vs adapter behavior on faebench.
- `build_pixie_chronicle_sft_env.py`: verifies an ALife chronicle corpus zip and builds episode-grouped narration splits.
- `run_grounding_compare.py`: emits one style x grounding certification scorecard per narrated adapter/model batch.
- `run_godel_globes_study.py`: launches and analyzes the counterbalanced five-dimensional retail character-editor study.
- `experiments/lora_pixie_village/`: local two-agent conversation room with isolated and attested adapter endpoints, resumable transcripts, validated public decision cards, optional canonical Storyworld consequence replay, and a verified real Bonsai trained-adapter/zero-control runtime smoke.
- `generate_reflective_buddy_distill.py`: generates teacher traces for the reflective-buddy lane.
- `build_reflective_buddy_experiment.py`: turns teacher traces into train and holdout assets.
- `run_pixie_snacksack.ps1`: syncs and runs the main remote workflows on `snacksack`.
- `run_pixie_local_4gb.ps1`: runs the local 4GB lane with a recommended `0.8B` preset and an experimental `1.7B` preset.
- `run_pixie_overnight_local.py`: runs the overnight local program that builds envs, trains route-specific adapters, evaluates them, and writes a routing manifest.
- `fae_bench/`: installable, model-free Fae Bench style and grounding metrics plus optional Verifiers taskset adapters.

## Configuration

Edit `pixieology.config.json` for a new workstation or cloud checkout. It is the
single default source for paths, model IDs, steering layer, and steering
strength. Relative paths are resolved from the repo root on every OS.

Environment variables remain optional runtime overrides for automation:

- `PIXIE_ROOT`: override the repo root if you launch from elsewhere.
- `PIXIE_DATA_ROOT`: location for generated `normalized_trajectories/` and `pixie_research/`.
- `PIXIE_MODEL_CACHE_DIR`: local Hugging Face / model cache root.
- `HF_HOME`: Hugging Face cache root. If unset, the repo falls back to `PIXIE_DATA_ROOT/hf_home`.
- `PIXIE_SOUL_PATH`: path to `soul.md`.
- `PIXIE_STORYWORLD_COMPARISON_PATH`: path to `route_ablation_comparison.json`.
- `PIXIE_GODEL_GLOBES_ROOT`: five-dimensional character-lab source root.
- `PIXIE_GODEL_GLOBES_CHARACTER_SPACE`: portable experimental character-space contract.
- `PIXIE_GODEL_GLOBES_RECEIPTS`: private local store for exported usability receipts.
- `PIXIE_GODEL_GLOBES_RESULT`: destination for the A/B decision receipt.
- `paths.lora_pixie_village_root`: checked-in two-agent room source and static UI.
- `paths.lora_pixie_village_runtime`: gitignored fsynced conversation sessions.
- `paths.lora_pixie_village_decisions`: validated public Storyworld decision cards available to the room.
- `paths.lora_pixie_bonsai_llama_server`: configured Prism llama.cpp runtime used by the bounded real control smoke.
- `paths.lora_pixie_bonsai_q1_base`: native Bonsai Q1 base used by both isolated routes.
- `paths.lora_pixie_bonsai_trained_adapter_gguf`: converted trained canary adapter; this is not yet a full persona adapter.
- `paths.lora_pixie_bonsai_zero_adapter_gguf`: zero-LoRA control used only for integration evidence.
- `PIXIE_TESSERACT_TRAIN`: path to `train_qlora.py`.
- `PIXIE_BRIDGE_RUN`: path to the storyworld bridge runner.
- `PIXIE_CONFIG`: use a different config file without editing the checked-in default.
- `PIXIE_BASE_MODEL_0_8B`, `PIXIE_BASE_MODEL_1_7B`: optional model-ID overrides.
- `PIXIE_ADAPTER_0_8B`, `PIXIE_ADAPTER_1_7B`: optional adapter overrides for faebench compare.
- `PIXIE_LLAMA_SERVER`, `PIXIE_REMOTE_MODEL_PATH`: optional overrides for reflective-buddy remote distillation.

The default checkout uses repo-local paths under `data/`, `inputs/`, and
`external/`. Point those config entries at existing external projects or copy
the needed files into those directories.

Chronicle integration uses four config paths:

- `paths.chronicle_corpus`: ALife-produced, producer-verified corpus zip;
- `paths.chronicle_sft_output_dir`: destination for `train.jsonl`, `val.jsonl`, `holdout.jsonl`, and the bridge manifest;
- `paths.chronicle_narrated_env`: narration-filled JSONL to certify;
- `paths.chronicle_scorecard`: deterministic certification JSON output.

The retail Gödel Globes experiment uses four additional config paths:

- `paths.godel_globes_experiment_root`: local interactive experiment;
- `paths.godel_globes_character_space`: provisional game-facing trait contract;
- `paths.godel_globes_study_receipts`: untracked local participant receipts;
- `paths.godel_globes_ab_result`: atomically written comparison result.

## Fae Bench v2

Install the evaluator in editable mode and run its deterministic tests:

```powershell
python -m pip install -e .
python -m pytest -q tests/test_fae_bench_metrics.py
```

The public pure functions accept mappings corresponding to JSONL rows with
`prompt`, `response`, `mode`, and `condition`. The marker vocabulary is the
versioned `fae_bench/data/fae_markers_v1.yaml` resource. The optional
`fae_bench.taskset` module follows the Control-Harness `taskset.py` / scoring
layout and requires the `verifiers` extra in its cloud runtime. V2 adds
`fact_recall`, `contradiction_rate`, and `unsupported_claim_rate`, backed by the
versioned `fae_bench/data/grounding_rules_v1.yaml` lexical contract. The LLM
judge interfaces in `fae_bench/judge.py` are provider-neutral and contain no
keys or network implementation.

These grounding metrics are deliberately lexical, not NLI. They are a cheap,
deterministic local gate before the stronger injected grounding judge.

## ALife chronicle narration

After `paths.chronicle_corpus` points to a producer-verified ALife bundle, build
the three episode-isolated SFT splits:

```powershell
python .\build_pixie_chronicle_sft_env.py
```

The builder refuses failed producer receipts, manifest hash mismatches, source
hash mismatches, episode receipt mismatches, or altered SFT artifacts before it
writes output. Every output row preserves `episode_id`, `replay_receipt`, and
`fact_list`; records from one episode can never cross split boundaries.

After a cloud job fills `narration`, create the local certification gate:

```powershell
python .\run_grounding_compare.py --label pixie-chronicle-adapter-v1
```

The JSON scorecard carries style and grounding summaries, per-episode rows,
per-record evidence counts, and strict default grounding thresholds.

## Legacy artifact bundle

After `paths.fae_switch_synth`, `paths.overnight_work_root`, and
`paths.legacy_bundle_output_dir` point at the local legacy data, build the
cloud-upload archive with:

```powershell
python .\build_legacy_artifact_bundle.py
```

The ZIP contains a per-file `MANIFEST.md`; the builder also writes a standalone
manifest and `.sha256` receipt. Dated legacy ZIPs and the default `artifacts/`
directory are ignored by git.

## Common Commands

Build storyworld training data:

```powershell
python .\build_pixie_storyworld_sft_env.py
```

Build the MeTTa/TRM moral-recursion SFT data:

```powershell
python .\build_pixie_moral_recursion_sft_env.py --repeat 4 --repair-repeat 3
```

This collects bounded moral decision traces from the configured `paths.metta_root`,
including medicine, bioethics, and triage scenarios. The output env is
`pixue_moral_recursion_sft`, with recursive passes for `sft_prior`,
`metta_moral_graph`, and `trm_projection`.

Run the current storyworld SFT pass:

```powershell
python .\run_pixie_storyworld_sft.py --models 1.7B --skip-bridge
```

Run the moral-recursion adapter lane:

```powershell
python .\run_pixie_moral_recursion_sft.py --models 1.7B --skip-train
python .\run_pixie_moral_recursion_sft.py --models 1.7B --steps 80 --max-len 768
```

Run the local 4GB lane:

```powershell
.\run_pixie_local_4gb.ps1 -Mode smoke
.\run_pixie_local_4gb.ps1 -Mode action-train
.\run_pixie_local_4gb.ps1 -Mode prose-train
.\run_pixie_local_4gb.ps1 -Mode action-train -ModelSize 1.7B
```

Run the overnight local program:

```powershell
python .\run_pixie_overnight_local.py
```

Build faebench and compare adapter behavior:

```powershell
python .\build_faebench_env.py
python .\run_faebench_compare.py --models 1.7B
```

Run and inspect the five-dimensional retail character-editor study:

```powershell
python .\run_godel_globes_study.py launch --participant P01 --round 1
python .\run_godel_globes_study.py status
python .\run_godel_globes_study.py analyze
```

Generate reflective-buddy teacher data and build holdout assets:

```powershell
python .\generate_reflective_buddy_distill.py --examples-per-scenario 1
python .\build_reflective_buddy_experiment.py
```

Run the remote `snacksack` workflow:

```powershell
.\run_pixie_snacksack.ps1 -Mode sync
.\run_pixie_snacksack.ps1 -Mode smoke
```

## Tests

The deterministic builders, portability contract, and Fae Bench metrics use pytest coverage:

```powershell
python -m pytest -q
```

## Notes

- The current product-facing surface is the storyworld, faebench, and reflective-buddy lane.
- The primary fae case study in the current repo is the `1.7B` Josified line; see `run_faebench_compare.py`, `run_pixie_storyworld_sft.py`, and `session_summary_2026-03-27.md`.
- The `0.8B` path under `run_pixie_local_4gb.ps1` is the recommended 4GB local preset.
- The same launcher now supports `-ModelSize 1.7B` as an experimental local path using a `3900 MiB` cap and a forced `single-gpu` load on a 4GB card.
- The overnight local launcher also uses `3900 MiB` for `1.7B`, saves checkpoints earlier, resumes from the latest checkpoint when one exists, and forces the local `1.7B` lane onto `cuda:0` instead of `device_map=auto`.
- Older overnight persona sweep scripts are still present, but they have not been normalized to the same level as the active lane.
