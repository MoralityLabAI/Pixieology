import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const study = require("../study.js");

function clock() {
  let value = 1_000;
  return {
    now: () => value,
    advance: (milliseconds) => { value += milliseconds; }
  };
}

test("two rounds counterbalance each participant", () => {
  const firstConditions = [];
  for (let index = 1; index <= 6; index += 1) {
    const participant = `P0${index}`;
    const first = study.conditionFor(participant, 1);
    const second = study.conditionFor(participant, 2);
    firstConditions.push(first);
    assert.notEqual(first, second);
  }
  assert.equal(firstConditions.filter((condition) => condition === "embodied").length, 3);
  assert.equal(firstConditions.filter((condition) => condition === "flat").length, 3);
});

test("a target task records timing and dimension errors", () => {
  const time = clock();
  const session = new study.StudySession({ participantId: "P01", round: 1, now: time.now });
  session.beginTask("left-wing");
  time.advance(250);
  session.action("dimension_change", { dimension: "care" }, [0.5, 0.5, 0.55, 0.5, 0.5]);
  time.advance(750);
  const outcome = session.action("dimension_change", { dimension: "wonder" }, [0.85, 0.25, 0.5, 0.5, 0.5]);
  assert.equal(outcome.complete, true);
  assert.equal(outcome.result.elapsed_ms, 1_000);
  assert.equal(outcome.result.actions, 2);
  assert.equal(outcome.result.wrong_dimension_actions, 1);
  assert.equal(outcome.result.final_l1_error, 0);
});

test("the edit-and-return task cannot pass without the intermediate edit", () => {
  const time = clock();
  const session = new study.StudySession({ participantId: "P02", round: 2, now: time.now });
  const task = session.beginTask("edit-and-return");
  assert.equal(session.check(task.startTuple).complete, false);
  session.action("dimension_change", { dimension: "play" }, task.modifiedTuple);
  time.advance(500);
  const outcome = session.action("warp_back", {}, task.targetTuple);
  assert.equal(outcome.complete, true);
  assert.equal(outcome.result.wrong_dimension_actions, 0);
});

test("receipts contain condition, results, and ordered event evidence", () => {
  const time = clock();
  const session = new study.StudySession({ participantId: "P03", round: 1, condition: "embodied", now: time.now });
  const task = session.beginTask("head");
  time.advance(400);
  session.action("dimension_change", { dimension: "reflection" }, task.targetTuple);
  const receipt = session.receipt();
  assert.equal(receipt.schema_version, 1);
  assert.equal(receipt.study_id, "godel_globes_5d_character_ab_v1");
  assert.equal(receipt.condition, "embodied");
  assert.equal(receipt.completed_tasks, 1);
  assert.deepEqual(receipt.events.map((event) => event.seq), [0, 1, 2, 3]);
  assert.ok(receipt.events.every((event) => event.t_ms >= 0));
});

test("debrief answers are validated and retained", () => {
  const time = clock();
  const session = new study.StudySession({ participantId: "P04", round: 2, now: time.now });
  session.setDebrief({
    reflectionLocation: "head",
    mapMeaning: "approximate_similarity",
    preference: "embodied",
    comments: "The anatomy made the dimensions easier to remember."
  });
  assert.deepEqual(session.receipt().debrief, {
    reflection_location: "head",
    map_meaning: "approximate_similarity",
    preference: "embodied",
    comments: "The anatomy made the dimensions easier to remember."
  });
  assert.throws(() => session.setDebrief({
    reflectionLocation: "halo",
    mapMeaning: "approximate_similarity"
  }), /reflection_location/);
});

test("a saved receipt resumes with monotonic events and completed tasks", () => {
  const firstClock = clock();
  const first = new study.StudySession({ participantId: "P05", round: 1, now: firstClock.now });
  const task = first.beginTask("head");
  firstClock.advance(600);
  first.action("dimension_change", { dimension: "reflection" }, task.targetTuple);
  const saved = first.receipt();

  const secondClock = clock();
  const resumed = study.StudySession.fromReceipt(saved, { now: secondClock.now });
  assert.equal(resumed.results.length, 1);
  assert.equal(resumed.events.at(-1).type, "session_resume");
  assert.ok(resumed.events.at(-1).t_ms >= saved.events.at(-1).t_ms);
  const next = resumed.beginTask("named-warp");
  secondClock.advance(400);
  resumed.action("anchor_warp", { anchor_id: "moon-archivist" }, next.targetTuple);
  assert.equal(resumed.receipt().completed_tasks, 2);
  assert.deepEqual(
    resumed.events.map((event) => event.seq),
    Array.from({ length: resumed.events.length }, (_, index) => index)
  );
});
