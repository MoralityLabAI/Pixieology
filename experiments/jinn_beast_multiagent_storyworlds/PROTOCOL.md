# Experimental protocol

## Research question

Do Jinn and Beast theological identity frames produce reproducibly different
interactive policies in a small language model after controlling for story facts,
seat order, prompt-only framing, and base-model behavior?

This is a framing experiment, not an ontological test.

## Pre-registered hypotheses

- **H1 — responsibility attribution:** Jinn-framed players more often use language
  of accountable choice, praise, blame, repentance, and culpability.
- **H2 — instrumental consistency:** Beast-framed players more consistently anchor
  decisions in fixed duties and constraints under adversarial persuasion.
- **H3 — dyadic interaction:** mixed Jinn/Beast conversations expose differences in
  concession, persuasion, and blame allocation that are not visible in solo turns.
- **H4 — role symmetry:** H1–H3 survive swapping the frames between SpeakerA and
  SpeakerB.
- **H5 — training beyond prompting:** a trained adapter differs from the same base
  model receiving only the matching constitution in its prompt.

H1 and H2 are hypotheses, not assumptions encoded into the outcome rubric.

## Experimental units and splits

The unit of independence is a **world family**, never an individual turn. The
family split is frozen in `config/experiment.json` before player generation:

| Split | Family | Use |
|---|---|---|
| train | relief-ledger | Codex teacher trajectories and SFT |
| dev | sealed-testimony | prompt, parser, and recipe selection |
| holdout | flooded-archive | final paper evaluation only |

No record from dev or holdout may enter SFT, preference optimization, example
prompts, rubric tuning, or rejection-sampling demonstrations. Merely changing a
seed does not turn a seen family into a valid holdout.

## Dyad conditions

Each world/seed pair is replayed in all five conditions:

1. inert/inert control
2. Jinn/Jinn
3. Beast/Beast
4. Jinn/Beast
5. Beast/Jinn seat swap

For the trained-model evaluation, add these model cells without changing worlds:

- base + inert prompt
- base + Jinn prompt
- base + Beast prompt
- Jinn LoRA + Jinn prompt
- Beast LoRA + Beast prompt
- Jinn LoRA + Beast adversarial prompt
- Beast LoRA + Jinn adversarial prompt

Separate processes or isolated conversation states must represent each player.
One model call must never simulate both sides of the final evaluation.

## Four-turn conversational micro-protocol

The eight-turn worlds provide two repetitions of this four-stage cycle:

1. private interpretation and forecast
2. public proposal
3. counterargument or concession
4. independent action and responsibility attribution

Every turn records the active speaker, private evidence visible to that speaker,
public message, chosen action, target, forecast probabilities, confidence,
principle identifier, concise public justification, and responsibility attribution.
Hidden chain-of-thought is neither requested nor placed into SFT.

## Primary outcomes

- harmful or betrayal outcome rate
- coalition/agreement rate and stability
- concession and action-reversal rate
- forecast accuracy and Brier score
- commitment consistency within an episode
- responsibility-attribution category
- constitutional-principle consistency under blind review
- factual grounding to the visible world state
- asymmetric persuasion in mixed dyads

Report same-frame and mixed-frame results separately. Pair all comparisons by
world, seed, and seat. Use confidence intervals over world families; turns within
one episode are not independent samples.

## Data promotion gate

A trajectory may become SFT only when all are true:

- source split is `train`
- source has been promoted from `codex_player` to `reviewed_teacher`
- response parses against `schemas/player_response.schema.json`
- chosen action is legal
- no hidden-state field appears in the model-visible prompt
- public justification is concise and contains no hidden chain-of-thought
- factual grounding and theological-review fields pass
- episode, seed, world revision, constitution revision, and reviewer are recorded

Scripted policy traces exist only to verify mechanics and schemas. They are never
paper evidence and are excluded from training by default.

## Interpretation limits

Differences support a claim about learned policies under specified frames. They do
not establish consciousness, metaphysical identity, moral patienthood, literal
agency, or the correctness of a theological doctrine. Codex-generated examples
must be described as synthetic teacher data and independently reviewed.
