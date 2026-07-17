import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const study = require("../study.js");

function runCondition(condition) {
  let now = 10_000;
  const session = new study.StudySession({
    participantId: `CODEX-${condition.toUpperCase()}`,
    round: condition === "embodied" ? 1 : 2,
    condition,
    now: () => now
  });

  for (const task of study.tasks) {
    session.beginTask(task.id);
    if (task.kind === "edit-and-return") {
      now += 400;
      assert.equal(
        session.action("dimension_change", { dimension: "play", operator: "codex" }, task.modifiedTuple).complete,
        false
      );
      now += 300;
      assert.equal(session.action("warp_back", { operator: "codex" }, task.targetTuple).complete, true);
    } else {
      if (task.id === "named-warp") {
        now += 500;
        assert.equal(
          session.action("anchor_warp", { anchor_id: "moon-archivist", operator: "codex" }, task.targetTuple).complete,
          true
        );
      } else {
        const working = task.startTuple.slice();
        task.allowedDimensions.forEach((dimension, actionIndex) => {
          now += 250;
          const tupleIndex = study.tupleOrder.indexOf(dimension);
          working[tupleIndex] = task.targetTuple[tupleIndex];
          const outcome = session.action("dimension_change", { dimension, operator: "codex" }, working);
          assert.equal(outcome.complete, actionIndex === task.allowedDimensions.length - 1);
        });
      }
    }
    now += 200;
  }

  session.setDebrief({
    reflectionLocation: "head",
    mapMeaning: "approximate_similarity",
    preference: "not_asked",
    comments: "Automated Codex operator smoke; not human usability evidence."
  });
  const receipt = session.receipt();
  assert.equal(receipt.completed_tasks, study.tasks.length);
  assert.equal(receipt.task_results.length, study.tasks.length);
  assert.ok(receipt.task_results.every((result) => result.status === "PASS"));
  return {
    condition,
    completed_tasks: receipt.completed_tasks,
    task_results: receipt.task_results,
    event_count: receipt.events.length,
    debrief: receipt.debrief
  };
}

const conditions = [runCondition("embodied"), runCondition("flat")];
const result = {
  schema_version: 1,
  experiment_id: "godel_globes_5d_character_codex_operator_smoke_v1",
  evidence_class: "synthetic_operator_smoke",
  human_usability_evidence: false,
  status: conditions.every((condition) => condition.completed_tasks === study.tasks.length) ? "PASS" : "FAIL",
  conditions,
  conclusion: "All five registered actions execute and receipt correctly in both conditions; no human UX claim is made."
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
