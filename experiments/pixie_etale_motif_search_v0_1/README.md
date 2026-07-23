# Pixie étale motif search v0.1

This experiment searches controlled input batches for recurring local-gluing
forms across the seven LoRA target sheets and the ordered 28-layer depth base.
It is activation-conditioned: every point describes how the frozen trained
LoRA update would respond to the base model's final prompt-token activation at
that module and layer.

The experiment is staged, not authorized. The checked-in code may build the
corpus, inspect the source safetensors header, run synthetic pipeline tests, and
analyze existing completed artifacts. Model sharding, model loading, and
activation capture require a fresh receipt and the capped wrapper.

`protocol.lock.json` seals the staged implementation file-by-file. Authorization
receipts bind both the protocol and lock hashes, so editing capture, analysis,
schema, test, or launcher files fails closed until a reviewed lock is minted.

## CPU-safe checks

```powershell
python experiments\pixie_etale_motif_search_v0_1\run.py verify
python experiments\pixie_etale_motif_search_v0_1\run.py corpus
python experiments\pixie_etale_motif_search_v0_1\run.py shard-plan
python experiments\pixie_etale_motif_search_v0_1\run.py synthetic-smoke --output-root data\pixie_etale_motif_search_v0_1\synthetic
pytest -q experiments\pixie_etale_motif_search_v0_1\tests
```

The synthetic smoke is implementation evidence only. It is marked as neither
real-model nor human evidence.

## Registered conveyor

1. `shard-plan` reads the source header only.
2. `shard-model` copies raw tensor payload bytes into verified shards without
   importing a tensor loader.
3. `capture --chunk-index N` runs 32 inputs and writes an atomic checkpoint
   every eight rows.
4. `fit-scaler` fits the discovery-only global X/Y/Z scaler.
5. `build-forms` emits trained counterfactual form receipts.
6. `random-controls` emits nineteen per-module norm-matched null form sets.
7. `mine` consumes discovery forms only.
8. `confirm` applies the frozen model to confirmation forms and emits a
   descriptive catalog with activation-conditioned exemplar cases.
9. `predictive-gate` and `random-null-gate` evaluate held-out usefulness and
   nineteen norm-matched random updates.
10. `intervention-plan` freezes selective-LoRA mask tasks before outcomes are
    read. `resolve-intervention-plan` selects disjoint energy-matched masks
    from capture geometry without reading outcomes. The authorization receipt
    must then bind the resolved plan hash before capped
    `capture-intervention` forwards can run; `intervention-gate` analyzes the
    completed observation receipts.
11. `human-study` applies the registered craft and learning thresholds.
12. `report` aggregates independent gates without converting missing evidence
    into a pass.

`publish-catalog` is the only path that converts a confirmed JSON catalog into
the browser's local UMD data file. It refuses `NOT_RUN`, `NO_STABLE_MOTIFS`,
synthetic-only, and case-free catalogs. Loading a case switches the explorer
from the parameter-only atlas to that case's activation-conditioned X/Y/Z
coordinates; changing the chart controls continues to explore the same case.

All browser and agent consumers use versioned JSON receipts. No consumer needs
to infer a value from an SVG position.

## Claim boundary

The W base is an interval, so monodromy and S are unavailable in this
experiment. Direct tolerance edges remain separate from their single-linkage
closure. A merge, split, or rewire is a quotient event, not literal branching.
Epsilon is a descriptive cut through an exact edge-birth filtration, not a
confidence interval.

See [STUDY_PROTOCOL.md](STUDY_PROTOCOL.md) for the preregistered human task
flows and evidence boundary.
