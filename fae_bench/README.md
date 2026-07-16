# Fae Bench v1

`fae_bench` is a model-free persona-switch evaluator for JSONL records with
four required string fields:

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

`fae_bench.judge` documents a provider-neutral structured rubric. It makes no
network calls, reads no environment keys, and raises until the caller injects a
`JudgeProvider` implementation.
