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
