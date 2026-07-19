# LoRA Pixie Village — phase 1 conversation room

This is first and foremost a platform for two independently served LoRA Pixies
to talk to each other. The server owns turn order, context bounds, adapter
routing, resumable session logs, and provider failures. The browser is a local
control room. A deliberately narrow second layer can thread a validated public
Storyworld decision into an already-running conversation so the agents can
discuss it. The Storyworld is context, not the conversational substrate.

The checked-in default uses two deterministic demo speakers so the complete UI
and logging path works without a model. Demo output proves plumbing only; it is
not evidence about a LoRA or a persona.

## Run the deterministic room

From the repository root:

```powershell
python .\experiments\lora_pixie_village\server.py
```

Open <http://127.0.0.1:8787>, enter a topic, and choose **Open room**. Use
**Play**, **Pause**, or **One turn**. After the residents have begun talking,
you may choose a public Storyworld decision and select **Thread into
conversation**; the preceding transcript remains intact. Every server-side session is written below
`paths.lora_pixie_village_runtime` from `pixieology.config.json`.
The session ID is also placed in the page URL; reloading that URL resumes the
last atomic snapshot instead of creating a fresh conversation.

No sudo, administrator terminal, cloud service, token, or model download is
required for the demo.

To enable canonical Storyworld consequences, point the existing engine override
at a GPTStoryworld checkout before launch:

```powershell
$env:PIXIE_STORYWORLD_ROOT = 'C:\projects\GPTStoryworld'
python .\experiments\lora_pixie_village\server.py
```

If the engine checkout is unavailable, the server reports that at startup and
keeps decision rooms in explicit `deliberation_only` mode rather than
substituting home-grown dynamics.

## Bind two real LoRA Pixies

Run one OpenAI-compatible local model server per adapter. Separate processes
make adapter identity explicit and prevent one call from accidentally using the
other resident's adapter. For llama.cpp the shape is:

```powershell
llama-server -m <base.gguf> --lora <lumen-adapter.gguf> --port 8081
llama-server -m <base.gguf> --lora <moss-adapter.gguf>  --port 8082
```

Copy `config/agents.llama.example.json` to an untracked local file, update only
the endpoint/model/adapter labels, and launch:

```powershell
python .\experiments\lora_pixie_village\server.py `
  --agents .\experiments\lora_pixie_village\config\agents.local.json
```

Startup probes each configured `/v1/models` and `/v1/chat/completions` route.
Two residents may not share the same endpoint/model pair. A transport-only pass
is reported as `PASS_TRANSPORT_ADAPTER_UNVERIFIED`; that proves the routes answer,
not that either process loaded the intended LoRA.

For a fail-closed launch, put an `identity_url` and the expected lowercase
`expected_adapter_sha256` in each provider block, then run:

```powershell
python .\experiments\lora_pixie_village\server.py `
  --agents .\experiments\lora_pixie_village\config\agents.local.json `
  --require-adapter-attestation
```

The identity endpoint must return the configured `adapter_label`, the exact
adapter file SHA-256, a base-model ID, and a runtime label. Stock llama.cpp does
not provide this project-specific endpoint. It therefore needs a small trusted
local launcher/proxy which hashes the adapter it passes to `llama-server` and
publishes the matching identity receipt. This is launch-time provenance, not a
cryptographic proof of model behavior; canary evaluations remain necessary.

The included trusted launcher/proxy supplies that missing identity boundary. It
hashes the executable, GGUF base, and GGUF adapter before starting its owned
`llama-server`, waits for model discovery and a real completion, exposes only a
loopback proxy, and records process cleanup in an atomic launch manifest. Run
one instance per resident in separate terminals. Shutdown uses a random token
kept in the launch directory so the supervisor, rather than a console signal,
can finalize its owned llama process and GPU audit:

```powershell
python .\experiments\lora_pixie_village\attested_llama_proxy.py `
  --llama-server $env:LLAMA_SERVER `
  --base-model $env:PIXIE_BASE_GGUF `
  --base-model-id bonsai-small-q1 `
  --adapter $env:LUMEN_ADAPTER_GGUF `
  --adapter-label lumen-lora-v1 `
  --model-alias lumen-local `
  --port 8081

python .\experiments\lora_pixie_village\attested_llama_proxy.py `
  --llama-server $env:LLAMA_SERVER `
  --base-model $env:PIXIE_BASE_GGUF `
  --base-model-id bonsai-small-q1 `
  --adapter $env:MOSS_ADAPTER_GGUF `
  --adapter-label moss-lora-v1 `
  --model-alias moss-local `
  --port 8082
```

Put each resulting adapter SHA-256 into the untracked agent configuration, set
`identity_url` to `/pixie/identity`, and set `launch_manifest` to that
resident's generated `launch_manifest.json`. After strict route preflight, run
the held-out behavioral gate:

```powershell
python .\experiments\lora_pixie_village\persona_canary_eval.py `
  --agents .\experiments\lora_pixie_village\config\agents.local.json `
  --canaries .\experiments\lora_pixie_village\config\persona_canaries.local.json `
  --out-dir .\artifacts\lora_pixie_village\canary-run-001
```

The checked-in canary file is a schema/example, not a claim that existing
adapters were trained with those phrases. Copy it to an untracked file, replace
the registered markers with held-out behaviors appropriate to the frozen
training recipe, and do not include the persona description in prompts. The
full gate is specified in `REAL_RESIDENT_CONTRACT.md`.

Use `--preflight-only` to check routes without opening the village server. The
atomic report defaults to `<runtime-root>/provider_preflight.json`, or can be
placed explicitly with `--preflight-report`.

Before claiming a real-adapter run, inventory the configured local cache and
runtime without loading weights:

```powershell
python .\experiments\lora_pixie_village\scripts\inventory_local_models.py
```

The scan is intentionally bounded to `HF_HOME`, the runtime artifacts named in
`pixieology.config.json`, and any additional roots named in
`PIXIE_ADAPTER_ROOTS` (separated with `;` on Windows). Its receipt says that it
is not an exhaustive disk search. A cached base checkpoint is useful, but it
does not satisfy the real-resident gate without two distinct trained LoRAs,
strict identity provenance, and held-out behavioral canaries. Describing both
residents as independently persona-tuned requires two persona adapters rather
than the companion-plus-action pair used by the current real village.

## Run the configured trained LoRA pair

This machine now has a compatible trained pair on the same Josiefied Qwen3
1.7B base: a companion-persona adapter and a Storyworld-action adapter. They
are two genuinely different trained LoRAs, but only the first is specifically
persona-tuned. The shared base is converted and locally quantized through a
bounded streaming path. A single CPU-only llama.cpp process loads both LoRAs,
sets both global scales to zero, and selects exactly one adapter by ID on each
request. This avoids duplicating the base in memory.

From terminal A, start the capped shared backend and two attested logical
routes. The script returns after both routes are ready; the hidden capped job
stops automatically after the requested duration:

```powershell
.\experiments\lora_pixie_village\scripts\start_real_josie_proxy.ps1 `
  -RunId josie-live-001 `
  -Port 8081 `
  -MaxRuntimeMinutes 30
```

From terminal B, start the village UI with strict adapter attestation:

```powershell
python .\experiments\lora_pixie_village\server.py `
  --agents .\data\lora_pixie_village\runtime\live_configs\josie-live-001.agents.json `
  --require-adapter-attestation
```

Open <http://127.0.0.1:8787>. First open an ordinary room and let the residents
talk. Thread a Storyworld decision later if desired. Stop the model backend
early with:

```powershell
.\experiments\lora_pixie_village\scripts\stop_real_josie_proxy.ps1 `
  -RunId josie-live-001 `
  -Port 8081
```

No administrator terminal, token, network service, or GPU inference is used.
The authoritative real-run pointer is
`reports/real_josie_pair_smoke.receipt.json`. Its v7 source run proves strict
hash attestation, per-request adapter selection, distinct same-prompt behavior,
four nonrepeating alternating free-conversation turns, two subsequent legal
Storyworld deliberation turns, a 1.07 GiB peak Job allocation, and clean
owned-PID cleanup. Marker-only decisions are rendered from the model-selected
public option and duplicate identical proposal markers are normalized; both
cases are explicitly recorded on the turn.

The exact user-facing start/preflight/stop sequence is independently recorded
in `reports/live_launcher_audit.receipt.json`. The shared Q4 route-attestation
hash is the raw whole-file SHA-256. `llama-gguf-hash` also emitted a different
digest over GGUF tensor payload bytes; these are intentionally distinguished in
`reports/josie_base_hash_audit.receipt.json` rather than presented as the same
kind of hash.

## Multi-adapter composition matrix

The first frozen composition experiment compares exactly four inference
conditions over the same base and prompts: base with both scales zero,
companion alone, Storyworld alone, and the additive stack with both scales at
one. It deliberately forbids a post-hoc scale sweep. Run the complete bounded
comparison with:

```powershell
.\experiments\lora_pixie_village\scripts\run_multi_adapter_compare.ps1 `
  -RunId multi-adapter-v1 `
  -Port 8081 `
  -MaxRuntimeMinutes 10
```

The matrix lives in `config/multi_adapter_matrix_v1.json`. Raw generations and
the immutable per-run receipt go below the configured runtime root; the stable
pointer is `reports/multi_adapter_compare.receipt.json`. This cheap gate proves
component scales, route identity, inference, and registered action markers. It
does not by itself establish semantic persona retention or non-inferiority of
the stacked condition.

## Multi-adapter retention study

The preregistered follow-up measures whether the additive stack retains each
singleton adapter's behavior. Companion retention is scored with a pinned,
offline MiniLM cosine matcher over blinded outputs; Storyworld retention is an
exact final-action score. Both primary paired differences use 10,000
family-stratified bootstrap resamples and a frozen non-inferiority margin of
0.05. Run it under the same hard resource controls with:

```powershell
$env:HF_HOME = 'D:\Research_Engine\hf_cache'
.\experiments\lora_pixie_village\scripts\run_multi_adapter_noninferiority.ps1 `
  -StudyId multi-adapter-ni-v1 `
  -RunId multi-adapter-ni-v1-c01 `
  -Port 58183 `
  -MaxItems 12 `
  -MaxRuntimeMinutes 30
```

Repeat with a fresh `RunId` to resume the exact hashed plan prefix. This
chunking is operational only: it cannot change probes or results already
fsynced under the study ID. See `MULTI_ADAPTER_NONINFERIORITY_DEVIATION_001.md`.

The frozen protocol and honest matcher limits are documented in
`MULTI_ADAPTER_NONINFERIORITY.md`. The stable result pointer is
`reports/multi_adapter_noninferiority.receipt.json`; raw generations, scored
rows, and the rendered report remain under the configured runtime root.
`PASS_COMPLETED` means the harness and resource attestation completed; the
scientific verdict is separately and explicitly `PASS`, `FAIL`, or
`INCONCLUSIVE`. Embedding similarity is a cheap semantic-proximity measure, not
NLI or proof that contradictions are absent.

## Real Bonsai control smoke

The configured Bonsai feasibility artifacts support a real, bounded integration
check with one trained canary adapter and one zero-LoRA control:

```powershell
python .\experiments\lora_pixie_village\scripts\real_bonsai_control_smoke.py --turns 2
```

On the local RTX 3050 this produced two attested Bonsai Q1 routes, one
alternating turn from each resident, clean `STOPPED` launcher manifests, and a
return to zero reported GPU memory. The stable evidence pointer is
`reports/real_bonsai_control_smoke.receipt.json`; the full transcript and launch
manifests remain under the configured runtime root.

This does **not** finish the persona gate. The second resident is deliberately a
zero adapter, and the pre-existing trained adapter reached only 4/8 of its
original strict canary target. The next valid milestone is two separately
trained persona adapters with distinct held-out behavior—not relabeling this
control pair as two Pixies.

The browser receives provider kind and adapter label, but never endpoint URLs,
API-key environment names, model routing, or private system prompts. The local
bridge uses greedy decoding (`temperature: 0`) and asks for public speech only.

## Optional Storyworld thread

The checked-in catalog includes a leakage-audited public decision card projected
from the Jinn/Beast dev world *The Sealed Testimony*. Open an ordinary
conversation first, let the residents speak, then attach it with **Thread into
conversation**. The two residents retain their earlier transcript, receive the
same visible facts and legal action IDs, discuss them, and record one legal
proposal per subsequent turn. Proposal markers are kept as structured log
fields and removed from the displayed dialogue. UI attachment is
deliberation-only; it never silently starts or advances a world engine.

Regenerate the card from the canonical source and validator:

```powershell
python .\experiments\lora_pixie_village\storyworld_bridge.py `
  --world .\experiments\jinn_beast_multiagent_storyworlds\worlds\dev\sealed_testimony_v1.json `
  --out .\experiments\lora_pixie_village\decision_packets\sealed_testimony_public_v1.decision.json `
  --manifest .\experiments\lora_pixie_village\decision_packets\sealed_testimony_public_v1.manifest.json `
  --storyworld-root C:\projects\GPTStoryworld
```

Only explicitly declared visible facts, the active public location, and public
action IDs enter the model packet. Hidden state, beliefs, seat-private evidence,
source hashes, split labels, endpoints, and adapter routing remain outside model
context. Canonical consequence execution remains available as a separate
experimental path for sessions explicitly created with a decision ID through
the service API and a configured `PIXIE_STORYWORLD_ROOT`; the normal browser
flow does not enable it. In that explicit path, proposals are applied to the
canonical engine seat matching the current Pixie. The engine is reset and prior
action receipts are replayed on every step, and public replay hashes must match
before a new action can commit.

The server never serializes an engine object or exposes engine beliefs. Without
the configured engine it retains the verified deliberation-only path.

## Tests and smoke receipt

```powershell
python -m pytest -q experiments\lora_pixie_village\tests
python experiments\lora_pixie_village\scripts\smoke.py
python experiments\lora_pixie_village\scripts\storyworld_thread_smoke.py
python experiments\lora_pixie_village\scripts\storyworld_smoke.py
$env:PIXIE_STORYWORLD_ROOT = 'C:\projects\GPTStoryworld'
python experiments\lora_pixie_village\scripts\engine_smoke.py
python experiments\lora_pixie_village\scripts\dual_http_smoke.py
python experiments\lora_pixie_village\scripts\persona_canary_smoke.py
```

The smoke command runs six deterministic alternating turns through the same
service used by HTTP, verifies persistence/resume, and writes
`reports/two_agent_smoke.receipt.json`.
`reports/storyworld_thread_smoke.receipt.json` proves the platform-first order:
two free conversation turns, a durable decision-thread attachment, then four
legal deliberation turns without starting the world engine.
The separate `reports/storyworld_decision_smoke.receipt.json` proves legal
proposal capture and private-state exclusion for the public decision bridge.
`reports/canonical_engine_loop_smoke.receipt.json` proves deterministic canonical
replay and public consequence feedback across a fresh service instance.
`reports/dual_http_route_smoke.receipt.json` proves strict two-route identity
plumbing plus four HTTP-mediated canonical-world turns. Its endpoints are
development fixtures with no weights, so the receipt explicitly records
`lora_behavior_evaluated: false` and must never be cited as adapter evidence.
`reports/persona_canary_development_smoke.receipt.json` similarly proves frozen
neutral-prompt scoring, raw-generation capture, and cross-route contamination
detection while remaining explicitly development-only.
