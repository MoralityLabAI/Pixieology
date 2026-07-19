# Fae Bench v2

`fae_bench` is a model-free evaluator for persona style and factual grounding.
The v1 style metrics accept JSONL records with four required string fields:

```json
{"prompt":"...","response":"...","mode":"fae|plain","condition":"..."}
```

The raw metrics are floats in `0..1`:

- `fae_score_lexical`: response-token coverage by the versioned markers in
  `data/fae_markers_v1.yaml`;
- `echo_rate`: response-token coverage by lexical tokens present in the prompt;
- `plain_drift`: Fae marker coverage on `mode=plain` rows, and zero on Fae rows;
- `toggle_adherence`: one when `mode=fae` matches the presence of the exact
  `[[FAE_TOGGLE]]` token (or plain mode matches its absence), otherwise zero.

`summarize_records` averages style and drift only over their applicable mode.
`fae_bench.taskset` mirrors the `taskset.py` / `scoring.py` Verifiers layout
used by Control-Harness environments. Install the optional Verifiers extra in
the cloud runtime; local deterministic scoring does not import that stack.

## Grounding metrics

The v2 grounding metrics accept a non-empty `narration` (or `response`) and the
ALife `fact_list`; an optional `window` improves ordering and unsupported-entity
checks:

```json
{"episode_id":"episode-1","narration":"...","fact_list":[{"predicate":"born_at_tick","subject":"e00000001","value":2}],"window":[]}
```

- `fact_recall`: fraction of atomic facts lexically entailed by at least one
  narration statement;
- `contradiction_rate`: fraction of statements with a detectable entity,
  number/tick, ordering, cause, or negation conflict;
- `unsupported_claim_rate`: fraction of statements containing an event, cause,
  or constrained entity assertion with no matching fact.

Aliases and exact-by-default numeric tolerances are versioned in
`data/grounding_rules_v1.yaml`. These are lexical matchers, not NLI. They can
miss novel paraphrases and can over-flag figurative uses of registered event
terms. `fae_bench.judge.llm_grounding_judge` is the stronger semantic check and
requires an injected provider; the package makes no network calls and reads no
credentials.

`fae_bench.grounding_taskset` mirrors the v1 Verifiers adapter and consumes the
chronicle env rows without rewriting `episode_id`, `window`, or `fact_list`.
