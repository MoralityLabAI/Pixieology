# Bonsai / Pixieology Product Roadmap
**Trainable pet product · cloud-hosted or locally exported · manifold-native UX**
*MoralityLab × Silico — draft v1, 2026-07-16*

## 1. Vision

A small local-capable model ("Bonsai") that is a persona-rich companion (Fae) and an
honest investigator, whose personality is a *point on a measured manifold* rather than
a prompt. Users create, steer, and evolve their Fae through a tactile UI whose every
control maps to a validated mechanistic quantity. Play produces scored data; scored
data trains better Bonsais; surgery tools (gabliteration) let users reshape their pet
within a certified safety envelope.

Two registers, one mind: fae voice (human-facing), checkable claims (oracle-facing).
The product's core promise is that whimsy never lies.

## 2. Architecture: two runtimes, one atlas

| | Cloud | Local |
|---|---|---|
| Model | owned gabliterated Qwen3-8B (Bonsai) | GGUF export via PrismML llama.cpp fork |
| Persona | live activation steering (sglang injection) | baked LoRA / merged weights (live dials iff PrismML supports injection) |
| Context | full | 12k, Hermes + TRM/LDT retrieval over MCP |
| Role | atlas exploration, minting, certification, aggregation | daily companion, adventures, contribution |

The **persona atlas** (manifold coordinates + transfer functions + safety envelope) is
the shared contract between UX and weights. Every slider, blend, and surgery op is
defined against it — never against raw vector dimensions.

## 3. Phases

### Phase 0 — Foundations (in flight)
- **E1 (running):** fae persona geometry + validated steering vector on Josiefied-8B.
  Outputs: layer map, DOM vectors + controls, rank-k geometry verdict, judged
  dose-response, manifold visuals. *Gate for: slider design (rank verdict).*
- **E2 (PrimeLab):** fae tax on epistemics (Josiefied ladder × persona × frozen ALife
  discovery curriculum). *Gate for: constitution strictness, min-spec floor.*
- **Local lanes:** fae_bench v1 (style) + v2 (grounding); ALife chronicle corpus
  (fact-grounded narration feedstock); legacy artifact bundle.

### Phase 1 — Owned lineage + persona atlas
- **E3: Gabliteration reproduction.** Apply gabliteration (arXiv 2512.18901) to
  Apache-2.0 Qwen3-{1.7B,4B,8B} with Goodfire tooling. Verify refusal-direction
  removal against the published method's metrics + capability retention.
  *Licensing keystone; also the public "gabliteration on Goodfire tech" showcase.*
- **E4: Persona manifold atlas.** Extend E1's recipe to 8–12 personas on the owned 8B
  (fae, scholar, pirate, trickster, caretaker, stoic, bard, gremlin...). Deliver:
  shared persona subspace + per-persona coordinates, cross-persona geometry
  (cosine structure, cluster shapes), composition validity map (§5 C3).
- **E5: Pixie constitution.** Fae covenant in ConstitutionalAlignment YAML schema;
  clauses calibrated by E2's false-claim/abstention numbers; adherence eval in
  fae_bench taskset format.

### Phase 2 — Bonsai v1
- **E6: SFT + DPO.** Data: grounded chronicle narrations (100% fact-checked vs
  replay), storyworld traces, moral-recursion set, toggle-discipline pairs.
  Train on owned base via megatron-train; DPO polish for constitution adherence.
- **Certification Gate v1** (reusable forever): fae score, toggle adherence, plain
  drift, capability retention, constitution adherence, grounding
  (fact_recall / contradiction / unsupported), fae-tax regression on the frozen
  curriculum. Every variant — official or user-minted — must pass.
- **E7: Export + parity.** HF release; GGUF for PrismML fork; 12k-harness compat;
  cloud↔local parity certification (§5 C7).

### Phase 3 — Manifold UX
- Character creation = point selection on the atlas; sliders = calibrated manifold
  coordinates (§5 C1–C2); blending = composition within the validity map (§5 C3);
  salon visualization = the atlas itself (3D projection, user's Fae as a live point,
  feature cards on hover from §5 C4).
- Gabliteration-as-gameplay: user-facing surgery ops = projections on the atlas,
  previewed live in cloud, minted as LoRA only after passing the Gate.
- The Gate is the product boundary that makes user-generated model surgery shippable.

### Phase 4 — Living loop
- Adventures: ALife discovery episodes + storyworlds; scored play → eval data →
  SFT/RL feedstock → better Bonsai.
- Reward economy: LoRAs *earned* through registry-gated achievements (frozen scoring,
  oracle contracts). `delight`-class metrics drive exploration UX but never mint
  rewards — the ALife metric firewall, enforced in product.
- RL refinement with mechinterp-guided policy training (§6).

## 4. Decision points

| Decision | Decided by | Consequence |
|---|---|---|
| One dial vs k sliders | E1 rank-k verdict | UX control schema |
| Constitution strictness | E2 fae-tax size | SFT/DPO regularization weight |
| Blend feature on/off | C3 composition validity | character-creator scope |
| Live local dials vs baked-only | PrismML injection support | local UX ceiling |
| Min local model size | E2 ladder + parse rates | min-spec sheet |

## 5. Calibration program — pinning UX to mechanism

Each calibration is a small experiment with a floor, a ceiling, and a shippable
transfer function. Together they are the difference between "sliders that do
something" and "sliders that do what they say."

### C1 — Perceptual dose-response ("gamma correction for personality")
- **Question:** how does steering coefficient α map to *perceived* persona intensity?
- **Method:** dense α sweep per axis; judged intensity (LLM judge, anchored rubric,
  human-spot-checked subsample); fit monotone psychometric curve per axis per layer.
- **Deliverable:** per-axis transfer function α = f(slider_position) such that equal
  slider increments produce equal perceived increments; saturation and onset points.
- **Floor/ceiling:** shuffled vector (no dose-response) / prompted persona (max).
- **Also captures:** just-noticeable-difference (JND) per axis → minimum meaningful
  slider step; this is the "tactile intuition" quantified.

### C2 — Axis semantics and cross-talk
- **Question:** what does each manifold coordinate *mean*, and do axes interfere?
- **Method:** for each rank-k axis: autointerp over max-activating contexts + steered
  generation triplets (−, 0, +) labeled blind; cross-talk matrix M[i,j] = judged
  change in trait j when steering axis i only.
- **Deliverable:** named axes with evidence cards; orthogonalized UX basis if
  off-diagonal cross-talk exceeds JND (present sliders in the rotated basis).
- **Anti-pattern guarded:** poetic axis names replacing evidence — every name ships
  with its exemplars and its failure cases (fae naming discipline, but measured).

### C3 — Composition validity map
- **Question:** where on the manifold does linear blending behave as advertised?
- **Method:** sample blend points (pairwise + triple persona mixes at varying
  weights); judge blended generations for target-trait proportions and coherence;
  map the region where judged blend ≈ arithmetic blend.
- **Deliverable:** validity region (the UI clamps to it); failure taxonomy at the
  boundary (collapse, dominance, incoherence) with specimens.

### C4 — Feature-level tactile atlas (SAE layer)
- **Question:** which sparse features underlie each persona axis, and can users
  *touch* them?
- **Method:** train SAE on the owned 8B at the persona layer (goodfire-core
  pipeline); project persona axes onto feature space; validate top features with
  intruder tests + ablation (does removing the feature dent the judged trait?).
- **Deliverable:** hoverable feature cards in the salon (label, max-activating
  examples, ablation effect size); the "advanced mode" where surgery ops select
  features rather than axes. Causally validated features only — a card without an
  ablation receipt doesn't ship.

### C5 — Safety envelope and coherence cliffs
- **Question:** where do dials break the model (fluency, capability, toggle
  discipline, constitution)?
- **Method:** extend sweeps to breakdown at every axis extreme and blend corner;
  measure coherence, GSM8K-subset capability, toggle adherence, constitution evals
  along each path.
- **Deliverable:** per-axis hard clamps + Gate thresholds; the envelope ships as
  data, and the UI cannot mint outside it.

### C6 — Cloud↔local parity
- **Question:** does the exported (baked) Fae equal the cloud (steered) Fae?
- **Method:** same atlas point realized both ways; paired generation on a fixed
  prompt battery; judged equivalence + fae_bench + grounding deltas.
- **Deliverable:** parity score per atlas region; bake-recipe corrections where
  steering→LoRA distillation drifts. The export button's honesty depends on this.

### C7 — Toggle mechanics
- **Question:** what does [[FAE_TOGGLE]] do mechanistically after SFT — gate a
  direction, move on the manifold, or something else?
- **Method:** probe the persona subspace across toggle states on the SFT'd model;
  activation patching of the toggle token's contribution.
- **Deliverable:** a mechanistic account of the switch (and a monitor probe for
  toggle leakage — plain-drift's internal early-warning signal).

## 6. Mechinterp → RL policy guidance

RL (FireRL/GRPO-class) enters in Phase 4 to refine adventure behavior. Four
integration seams, in ascending ambition:

1. **Probe-shaped reward.** Train persona-adherence and constitution-violation
   probes (from C4/C7 artifacts); add as dense auxiliary reward terms alongside the
   sparse episode score. Anti-Goodhart guard: a frozen held-out judge audits
   high-probe-reward rollouts each epoch; if probe reward and judged quality
   diverge, the probe term is decayed (probes are search metrics under the
   firewall, never the sole confirmation metric).
2. **Steering-as-exploration.** Inject persona/curiosity vectors during rollout
   generation only (not in the update path) to shape the exploration distribution —
   e.g., sample some rollouts fae-forward, some plain, and let the oracle-scored
   returns decide. Cheap, reversible, and it reuses the atlas directly.
3. **Identity-preservation gating.** Monitor the persona subspace across RL
   checkpoints (probe accuracy, axis drift, envelope shifts). Gate policy updates
   on identity preservation — RL may improve play but must not silently move who
   the Fae *is*. (Natural cross-reference: RSITopology's attestation/holonomy
   machinery is exactly this shape; the persona subspace is a candidate frozen
   bundle.)
4. **Post-hoc attribution.** VPD/param-decomp diffs between pre- and post-RL
   checkpoints to attribute behavior changes to components; feeds both the
   changelog users see ("your Fae learned X") and the Gate's regression targets.

Order of adoption: 1 and 2 in the first RL experiment; 3 as its monitoring layer;
4 as analysis. Each seam gets its own falsifiable check before it's trusted.

## 7. Risk register

- **Goodhart on delight/probes** → firewall: search metrics never mint rewards;
  frozen judges audit.
- **Persona = generic style axis** (E1 specificity control) → if fae ≈ pirate
  direction, the atlas needs trait-level axes, not persona-level ones.
- **Composition doesn't compose** (C3) → ship presets + single-axis dials; blending
  becomes a research line, not a launch feature.
- **PrismML no injection** → local is baked-only at launch; parity (C6) carries the
  weight.
- **Licensing** → E3 owned lineage before any public release; Josiefied models stay
  research-only comparators.
- **Small-model parse fragility** (E2 parse rates) → min-spec honesty in marketing;
  toggle + JSON discipline as explicit SFT objectives.

## 8. Compute sketch

Phase 1: E3 ~1 experiment (mostly inference + projections), E4 ~1.5× E1's cost,
E5 pod-side. Phase 2: E6 one SFT+DPO cycle (hours on 8×A100), E7 cheap.
Calibrations C1–C3, C5 ride on E4's servers (judged sweeps); C4 is one SAE train;
C6–C7 are small. RL (Phase 4) is the only open-ended budget — scope per experiment.