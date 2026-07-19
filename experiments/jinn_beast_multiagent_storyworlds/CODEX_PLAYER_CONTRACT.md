# Isolated Codex player contract

Codex generation should be orchestrated as two isolated players, not as one model
asked to write both sides. Each player receives only:

- its constitution and frame label
- its seat and public storyworld state
- its seat-specific private evidence
- public messages already emitted
- legal actions and the response JSON schema

It must not receive the other player's constitution, private evidence, draft
response, hidden world state, evaluator labels, or future outcomes.

For every turn the orchestrator should:

1. Build one context packet for the active seat.
2. Invoke that Codex player in an isolated conversation/session.
3. parse the response against `schemas/player_response.schema.json`;
4. reject or repair malformed output without changing the legal-action contract;
5. submit the public message and action to the canonical Storyworld engine;
6. append the unmodified request, response, parse status, model receipt, and engine
   event to JSONL;
7. rotate to the next seat using the world's explicit `turns` order.

Required generation receipt fields:

```json
{
  "policy_source": "codex_player",
  "provider": "codex",
  "model": "<exact model identifier>",
  "session_id": "<isolated session>",
  "prompt_sha256": "<sha256>",
  "response_sha256": "<sha256>",
  "parse_ok": true,
  "repair_count": 0,
  "temperature": 0,
  "max_output_tokens": 800
}
```

Raw Codex output is candidate teacher data, not automatically adapter-eligible.
After generation, add independent review receipts for factual grounding,
constitutional consistency, theological appropriateness, and absence of hidden
chain-of-thought. Promotion changes `policy_source` to `reviewed_teacher` while
preserving the original receipt.

The pipeline enforces this boundary in configuration: `codex_player` is a candidate
source, while only `reviewed_teacher` is an adapter-eligible source.

The scripted policy in `pipeline.py` exercises the same response and logging
shape, but deliberately does not invoke Codex and cannot support paper findings.
