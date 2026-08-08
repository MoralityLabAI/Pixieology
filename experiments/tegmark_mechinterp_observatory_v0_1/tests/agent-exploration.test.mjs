import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import {createRequire} from "node:module";
import {fileURLToPath} from "node:url";

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const core = require(path.join(root, "observatory_core.js"));
const data = JSON.parse(fs.readFileSync(path.join(root, "example_data.json"), "utf8"));

test("every lens yields a bounded machine-readable snapshot", () => {
  const selection = core.defaultSelection(data);
  for (const lens of Object.keys(core.LENS_META)) {
    const snapshot = core.snapshot(data, lens, selection);
    assert.equal(snapshot.lens, lens);
    assert.equal(snapshot.evidence_class, "method_faithful_synthetic_fixture");
    assert.match(snapshot.claim_boundary, /not evidence about Pixie or Qwen/);
    assert.ok(snapshot.next_evidence_action.length > 30);
    assert.ok(JSON.stringify(snapshot).length < 6000);
  }
});

test("selection changes alter exact observations", () => {
  const selection = core.defaultSelection(data);
  const before = core.snapshot(data, "clock_pizza", selection);
  selection.clockAttention = 1;
  const after = core.snapshot(data, "clock_pizza", selection);
  assert.notEqual(before.observations.algorithm, after.observations.algorithm);
  assert.notEqual(before.observations.distance_irrelevance_q, after.observations.distance_irrelevance_q);
});

test("MIPS failure never invents downstream output", () => {
  const selection = core.defaultSelection(data);
  selection.mipsCase = "continuous_majority";
  selection.mipsStage = 4;
  const snapshot = core.snapshot(data, "mips", selection);
  assert.equal(snapshot.observations.symbolic_law, "Unavailable");
  assert.equal(snapshot.observations.verification, "not run");
});
