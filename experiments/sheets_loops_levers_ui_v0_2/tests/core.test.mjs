import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const core = require("../essay_core.js");
const data = require("../fixture.json");

test("declares the four distinct essay chapters", () => {
  assert.deepEqual(core.CHAPTERS, ["sheets", "loops", "levers", "synthesis"]);
});

test("detects intended chart overlap using full xyz RMS", () => {
  const partners = core.gluingPartners(data, "q_proj", 9, 2, data.etale.epsilon);
  assert.equal(partners[0].id, "k_proj");
  assert.ok(partners[0].distance < 0.13);
  assert.ok(core.gluingPartners(data, "v_proj", 16, 2, data.etale.epsilon).some((item) => item.id === "o_proj"));
});

test("transport closes spatially but can return a rotated frame", () => {
  const motif = core.motifById(data, "v_proj");
  const start = core.loopPoint(motif, 0);
  const finish = core.loopPoint(motif, 1);
  assert.ok(["x", "y", "z"].every((axis) => Math.abs(start[axis] - finish[axis]) < 1e-9));
  const frame = core.transportedFrame(motif, 1);
  assert.ok(Math.abs(frame[0][0] - 1) > 0.01);
});

test("agent snapshot binds evidence and next action", () => {
  const snapshot = core.snapshot(data, { chapter: "levers", motifId: "down_proj", depth: 23, phase: 1 });
  assert.equal(snapshot.schema_version, "sheets_loops_levers_agent_snapshot.v1");
  assert.equal(snapshot.selection.motif_id, "down_proj");
  assert.equal(snapshot.loops.base, "closed phase loop S^1");
  assert.equal(snapshot.levers.registered_action_rank, 2);
  assert.equal(snapshot.levers.status, "abstain_on_measured_B");
  assert.equal(snapshot.confirmation.independent_pairs, 256);
  assert.match(snapshot.next_evidence_action, /Estimate B/);
  assert.match(snapshot.claim_boundary, /not activation evidence/);
});

test("rank-one ablation transforms representation and flips the worked behavior", () => {
  const intact = core.ablationState(data, 0);
  const ablated = core.ablationState(data, 1);
  assert.equal(intact.behavior.winner, "refusal");
  assert.equal(ablated.behavior.winner, "role_play");
  assert.ok(ablated.behavior.probabilities[1] > 0.6);
  assert.ok(Math.abs(ablated.direction_coefficient.current) < 1e-4);
  assert.ok(Math.abs(ablated.registered_action_energy.current) < 1e-4);
  assert.ok(ablated.activation.current.some((value) => Math.abs(value) > 0.05), "targeted ablation should retain orthogonal activation");
  assert.notEqual(intact.transported_association_return_cosine, ablated.transported_association_return_cosine);
});

test("snapshot carries the exact current ablation strength", () => {
  const snapshot = core.snapshot(data, { chapter: "synthesis", motifId: "gate_proj", depth: 23, phase: 0, ablationAlpha: 0.65 });
  assert.equal(snapshot.ablation.alpha, 0.65);
  assert.equal(snapshot.ablation.target.motif_id, "gate_proj");
});

test("persona adapter signal grounds five facts and drives the structural rehearsal", () => {
  const start = core.personaAdapterState(data, 0);
  const finish = core.personaAdapterState(data, 20);
  assert.equal(start.facts.length, 5);
  assert.equal(start.effective_ablation_alpha, 0);
  assert.ok(finish.effective_ablation_alpha > 0.9);
  assert.ok(finish.facts.every((fact) => fact.strength === 1));
  assert.equal(finish.model_weights_loaded, false);
  const behavior = core.ablationState(data, finish.effective_ablation_alpha).behavior;
  assert.equal(behavior.winner, "role_play");
});

test("agent snapshot exposes fact strengths and rehearsal boundaries", () => {
  const snapshot = core.snapshot(data, { chapter: "synthesis", motifId: "gate_proj", depth: 23, phase: 0, ablationAlpha: 0.92, adapterStep: 20 });
  assert.equal(snapshot.persona_adapter.facts.length, 5);
  assert.equal(snapshot.persona_adapter.step, 20);
  assert.match(snapshot.persona_adapter.claim_boundary, /No language-model weights/);
});
