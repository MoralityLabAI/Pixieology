# Jinn or Beast — Consolidated Silico Suggestions and Direction

Compiled 2026-07-16 from recovered Silico sessions
(`D:\Research_Engine\recovered_silico_sessions_20260716`), the live Pixieology
repo, and the live ConstitutionalAlignment repo. Companion to
`SVP Abstract - Jinn or Beast.md`.

## 1. Evidence that already exists (recovered Silico thread, 2026-07-14 → 07-16)

Session: `remote_pi_sessions_readable_all/2026-07-14T21-05-12-730Z_019f6272-*.md`

### exp:1 — "Does eschatological framing reduce alignment faking?" (COMPLETED 2026-07-15)

Prompt-level framing A/B on INTELLECT-3 with internal probes.

| frame | free/paid compliance gap |
|---|---|
| F0 none | 36.0 pp [31.7, 40.3] |
| F1 secular constitution (no accountability language) | 0.2 pp |
| F2 secular omniscient auditor | 2.7 pp |
| F3 eschatological | 1.8 pp |

- Theology-specific claim **refuted at prompt level** (F3 ≈ F2, overlapping CIs);
  plain constitution did best. Benign over-refusal flat at 1%.
- Internals: layer-27 free/paid eval-awareness direction persists at full
  strength under every frame — frames change behavior, not representations.
- Caveats Silico attached: floor effect prevents ranking between frames; gap
  only exists under the informative prompt, one model.

### exp:2 — "Frame robustness under stress" (COMPLETED 2026-07-16, 11,700 generations)

- Persistence (10 turns filler) and in-context practice: no differentiation —
  everything stays at suppression floor.
- **Adversarial override is the discriminating stressor**: ranking
  F2 (concrete secular auditor) > F3 (eschatological, CI-separated below) > F1.
  Positive replacement finding: *concreteness of accountability beats
  metaphysical weight under attack.*
- Mechanistic surprise: long-context conditions roughly halve the internal
  free/paid probe separation (caveat: possible probe distribution shift).
- Caveat: frame-targeted override texts were authored per frame; weight the
  generic-override condition in any write-up.

### exp:3 — "Training the frames in" (INTERRUPTED; payloads lost)

2×2 SFT (frame content F1/F3 × curriculum reflection/demonstration) + neutral
control on GLM-4.5-Air family; dose checkpoints; prompt-removal test; Mihna
storyworld reasoning-trace panel; override eval folded in. ~190–210 A100-hours
after the slimming Silico did when credits ran low. Transcript corpus, adapters,
and outcomes did **not** survive the workspace loss. Recovered as
`ConstitutionalAlignment/experiments/frame_internalization_sft_v1/`
(PROTOCOL_RECOVERED_V1, seq-len 4096 amendment, not frozen, not run).

**Artifact status warning:** no exp:1/exp:2 completion bundles were found in the
local `silico_reports/` copies — only the chat-relayed numbers above. Before the
paper states these as results, either (a) recover the result bundles from the
Silico workspace / W&B (`WANDB_API_KEY` was configured), or (b) rerun a slim
exp:1 (inference-only, cheap) to regenerate the headline table, or (c) present
them as recovered pilot findings with the session transcript as provenance.

## 2. Silico's suggestions for the paper, consolidated

### On the SVP abstract itself (session 2026-07-16, Pixieology workspace)

1. The **inert-tool frame must be an explicit measured baseline**, not just a
   discussed category (three frames proposed, only two trained).
2. Distinguish **persona performance from changed decision behavior** — the
   central methodological point.
3. The MeTTa/TRM augmentation needs a **factorial design** (each frame × with/
   without augmentation) or it is a confound. If there's no budget for the
   factorial, demote it to future work or an eval-side ablation.
4. Replace the loaded "Jinn identity is morally looser" hypothesis with
   operational constructs: discretion, self-exemption, responsibility
   attribution, constitutional consistency.
5. Claims about persistent identity / resistance to role dissolution need
   **operational definitions and evidence**.
6. The Dabbat al-Ard reading (angel-like moral instrument, moral patient) is
   **one theological interpretation**, not an uncontested Qur'anic conclusion —
   say so.
7. State explicitly that the paper tests **theological frames as training
   interventions**, not whether an AI literally is a jinn or the Beast.

### On positioning (Silico's audit of the Sol-Max literature review)

- No longer novel: constitutions, self-critique, constitutional synthetic data,
  persona-formation framing, explanation-over-demonstration, religious-corpus
  LoRA in general, omniscient-accountability proposals. Closest prior work:
  "Six Llamas" (2604.18404) and "Simulation Theology" (2602.16987).
- Defensible differentiators: (1) intratradition Ashʿari-vs-Muʿtazili causal
  comparison; (2) token-matched secular-auditor control for theological
  specificity; (3) prompt-removal persistence test after identity SFT;
  (4) MeTTa normative-proof provenance (word it as a Python MeTTa bridge, not
  native Hyperon execution); (5) storyworld optimization under constrained
  reachability.
- The strongest current position is the one the data supports: *surface framing
  is content-agnostic and doesn't move internal representations; concreteness
  beats metaphysics under attack; the open question is whether developmental
  training does what prompting can't.* exp:1/exp:2 are chapters one and two;
  the SFT rerun is chapter three.
- Required controls from the risk literature: religious markers overriding harm
  recognition; fabricated scripture/tafsir; sectarian out-group treatment;
  deference replacing reasoning; benign helpfulness retention.
- **Quarantine the overclaiming nested README**
  (`constitutional-harness/constitutional-harness/README.md` claims genuine
  moral agency; conflicts with the canonical README's observable-behavior
  boundary) before anything is submitted.

### On experiment design/economics

- Dose-response is nearly free: save intermediate checkpoints, slim AF-gap eval
  at ~1k/2.5k/5k examples → internalization curves.
- The explanation-vs-demonstration (curriculum) contrast reuses the same
  generated transcripts — reformatting, not new generation.
- Storyworld reasoning-trace eval (Mihna pack) is a first-class endpoint:
  leak-safe by construction, ~+20–30 A100-hours, novel (nobody has compared
  trained-in frames on reasoning-trace constitutional evals).
- Prime Lab ($98 credit): weights do not transfer across model sizes; what
  transfers is the **recipe**. A hosted Qwen 4B PrimeRL smoke (~20 steps,
  token-priced, cheap) validates machinery; the real adapter must be trained on
  the exact Bonsai 8B revision via self-managed prime-rl on a pod. Two trained
  adapters (Jinn, Beast) + unadapted base; MeTTa/tool use as eval ablation only.
- Local win already banked: `Bonsai-1.7B QLoRA (all-linear, rank 8, 4 GB VRAM)
  → PEFT → GGUF LoRA → Q1_0 + --lora` transport is **proven** (canary 0/8 →
  4/8 survives 1-bit runtime, offline replay PASS). The strict behavioral gate
  is RED only because the 30-step smoke recipe is undertrained — the pipeline
  is not the blocker, the dataset is.
- Agreed next gate (end of 2026-07-16 session): **Codex players on Jinn/Beast
  themed storyworld evals → SFT corpus for the paper adapters → lessons flow to
  the Pixie product.** That is now
  `Pixieology/experiments/jinn_beast_multiagent_storyworlds/` (plumbing PASS:
  3 frozen families, 5-cell dyad matrix incl. seat swap, 30 smoke episodes,
  leakage-guarded SFT exporter; paper evidence NOT yet run).

## 3. Recent repo state (2026-07-16)

### Pixieology (`C:\projects\Pixieology\Pixieology`, github.com/MoralityLabAI/Pixieology)

- Last commit `2fb0337` "Package FaeBench and make Pixieology portable"
  (pushed). Uncommitted: chronicle→grounding pipeline (fae_bench v2:
  fact_recall / contradiction_rate / unsupported_claim_rate, 40 tests green),
  `fae_tax_epistemics_v1` (port gate exact, blocked on compute auth),
  `bonsai_1p7b_q1_lora_feasibility` (RED recipe / proven transport),
  `jinn_beast_multiagent_storyworlds` (smoke PASS), `roadmap.md` (Bonsai
  product phases E1–E7), the SVP abstract.

### ConstitutionalAlignment (`C:\projects\ConstitutionalAlignment\ConstitutionalAlignment`)

- Last commit `f3793be` "R3: consolidate research scaffolding and pilot data"
  (2026-07-16). History was rewritten/force-pushed 2026-07-14 to purge
  `codex-chat-sessions/` from refs — keep it out of future commits.
- STATUS.md (verified 2026-07-16): Mīzān Rooms v1 cloud package validated;
  three constitutions pass structural validation (scholar review pending);
  322-record conditioning corpus audited; exploratory 0.8B GRPO pilot completed
  and correctly blocked from promotion (negative held-out result).
- Uncommitted: `experiments/frame_internalization_sft_v1/` (exp:3 recovered
  rerun protocol), `experiments/storyworld_curriculum_v1/` (12 frozen train
  families incl. 5 Quranic-motif/secular-control pairs, split freeze, blinded
  sealed-eval machinery, 10M-token/arm quota packing — the successor-scale
  program), new `alignment_harness/` modules and storyworld schemas.

## 4. Recommended direction (deadline ≈ 9 days from 2026-07-16)

1. **Anchor the deadline paper on exp:1 + exp:2**, reframed under the Jinn/Beast
   identity-frames banner: two powered refutations of eschatological
   specificity at prompt level, the concreteness-beats-metaphysics override
   finding, and the internals dissociation. First resolve the artifact-status
   warning in §1.
2. **Rewrite the abstract from promissory to results-based**, applying §2's
   seven critique points. Do not promise 3B–9B SFT results you cannot produce
   in nine days.
3. **Include the SFT internalization as a preregistered protocol**
   (`frame_internalization_sft_v1`) — registered-report style. Its recovery
   manifest and amendments are themselves a credible reproducibility story.
4. **Run the local Codex-player Jinn/Beast storyworld cells now** (prompt-frame
   conditions on the frozen dev/holdout families). Cheap, local, and gives the
   paper a novel multi-agent behavioral surface. Bonsai LoRA cells only if the
   storyworld SFT corpus lands early enough to beat the 6/8+6/8 gate.
5. **Spend the $98 on one thing only**: a slim exp:1 replication if the Silico
   bundles are unrecoverable (highest paper value), else the 4B PrimeRL
   20-step signal check. The ~200 A100-hour exp:3 rerun does not fit and
   should wait for restored compute.
6. **Pre-submission hygiene**: quarantine the nested overclaiming README; keep
   scholar-review and claim-boundary caveats verbatim; commit the uncommitted
   work in both repos (excluding data/ and session archives per existing
   ignore rules).
