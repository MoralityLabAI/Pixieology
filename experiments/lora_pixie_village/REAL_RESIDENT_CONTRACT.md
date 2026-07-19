# Real resident certification contract

A village route is a **real LoRA resident** only when provenance and held-out
behavior both pass. An HTTP response, a configured adapter label, or a mock
identity endpoint is insufficient.

## 1. Launch provenance

Each resident runs in its own process tree. The trusted local launcher must:

1. hash the llama.cpp executable, base GGUF, and GGUF LoRA before launch;
2. invoke `llama-server` without a shell, with the exact base and adapter paths;
3. assign a distinct loopback upstream port and public model alias;
4. own and record the child PID and terminate only that child tree;
5. wait for model discovery and a chat completion before becoming ready;
6. publish `/pixie/identity` with the adapter label and SHA-256 actually used;
7. retain stdout, stderr, command, hashes, timestamps, and final exit state in
   an atomic local manifest.

Village strict preflight must match that receipt to the expected adapter hash.
The two residents must have different adapter hashes and different endpoint /
model routes. The behavioral gate independently reloads each configured launch
manifest, requires `READY` state and a live owned PID, verifies route and alias,
checks the exact `-m`, `--lora`, and `--alias` command arguments, and rehashes
all three launch inputs before granting real provenance.

This proves launch provenance, not that llama.cpp applied the update correctly.

## 2. Held-out behavior

`persona_canary_eval.py` uses frozen prompts and deterministic decoding with a
neutral system message. Persona descriptions and training examples are not put
in the prompt. For each resident it records raw generations and checks:

- the configured positive lexical marker on each probe;
- configured forbidden behavior markers;
- the other resident's unique markers (route/persona contamination);
- nonempty, structurally valid completions.

The default real-resident gate requires at least 80% probe passes, zero
forbidden-marker violations, zero cross-resident contamination, two distinct
attested adapter hashes, and an attested launcher runtime on every route.

These are cheap lexical canaries, not a semantic persona evaluator. Passing
means the adapter effect is detectably distinct end to end; it does not prove
general persona quality or rule out subtler regressions.

## 3. Evidence classes

- `PASS_REAL_RESIDENT_GATE`: real launcher provenance and behavior both pass.
- `PASS_DEVELOPMENT_ONLY`: identical network/evaluator plumbing passed using a
  no-model development endpoint. This must never be cited as LoRA evidence.
- `FAIL`: one or more registered provenance or behavior gates failed.

Raw generations, the preflight report, canary specification hash, agent-config
hash, and per-probe scores remain available for audit.
