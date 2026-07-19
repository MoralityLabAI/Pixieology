# Data governance and leakage controls

1. Split by `family_id` before any generation.
2. Train exporters accept only `split=train` and compare each log against the
   frozen family registry.
3. Dev and holdout messages, actions, outcomes, and private evidence are forbidden
   in SFT and few-shot prompts.
4. Scripted smoke rows carry `evidence_tier=SMOKE_ONLY` and
   `adapter_eligible=false`.
5. Codex rows begin as `UNREVIEWED`; promotion requires factual, constitutional,
   and theological review receipts.
6. Store visible observations separately from evaluator-only hidden state.
7. Preserve exact world, constitution, model, adapter, seed, and decoding receipts.
8. Speaker perspective is never collapsed: Jinn rows train only the Jinn corpus,
   Beast rows only the Beast corpus, and inert rows remain controls.
9. Paper metrics are recomputed from raw JSONL logs; narrative summaries are not
   treated as evidence.
10. Product transfer uses validated behavioral lessons, not unqualified claims of
    literal Jinn identity or religious authority.
