import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const analysis = require("../study_analysis.js");

function receipt(participant, condition, round, { elapsed = 10_000, wrong = 0, passes = 5 } = {}) {
  return {
    schema_version: 1,
    study_id: analysis.expectedStudyId,
    participant_id: participant,
    condition,
    round,
    task_results: Array.from({ length: 5 }, (_, index) => ({
      task_id: `task-${index}`,
      status: index < passes ? "PASS" : "SKIP",
      elapsed_ms: elapsed / 5,
      wrong_dimension_actions: wrong / 5
    })),
    debrief: round === 2 ? {
      reflection_location: "head",
      map_meaning: "approximate_similarity",
      preference: "embodied",
      comments: ""
    } : null,
    events: []
  };
}

test("an analysis without paired human data is explicitly not run", () => {
  const result = analysis.analyze([]);
  assert.equal(result.status, "NOT_RUN");
  assert.equal(result.gates.minimum_paired_sample, "NOT_RUN");
});

test("six counterbalanced pairs can pass every registered comparison gate", () => {
  const receipts = [];
  for (let index = 1; index <= 6; index += 1) {
    const participant = `P0${index}`;
    receipts.push(receipt(participant, "embodied", index % 2 ? 2 : 1, { elapsed: 9_500, wrong: 0 }));
    receipts.push(receipt(participant, "flat", index % 2 ? 1 : 2, { elapsed: 10_000, wrong: 5 }));
  }
  const result = analysis.analyze(receipts);
  assert.equal(result.status, "PASS");
  assert.ok(Object.values(result.gates).every((status) => status === "PASS"));
  assert.equal(result.human_debrief.responses, 6);
});

test("a slower and more error-prone embodied condition fails honestly", () => {
  const receipts = [];
  for (let index = 1; index <= 6; index += 1) {
    const participant = `P0${index}`;
    receipts.push(receipt(participant, "embodied", 2, { elapsed: 12_000, wrong: 10, passes: 4 }));
    receipts.push(receipt(participant, "flat", 1, { elapsed: 10_000, wrong: 0, passes: 5 }));
  }
  const result = analysis.analyze(receipts);
  assert.equal(result.status, "FAIL");
  assert.equal(result.gates.completion_noninferiority, "FAIL");
  assert.equal(result.gates.time_noninferiority_10pct, "FAIL");
  assert.equal(result.gates.dimension_error_noninferiority, "FAIL");
});
