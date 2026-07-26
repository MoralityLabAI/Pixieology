import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repo = path.resolve(folder, "..", "..");
const require = createRequire(import.meta.url);
const core = require(path.join(folder, "strategy_core.js"));
const tasks = require(path.join(folder, "study_tasks.js"));
const catalog = require(path.join(folder, "sprint_catalog_data.js"));
const data = require(path.join(repo, "experiments", "godel_globes_5d_character_lab", "bonsai_mechinterp_data.js"));
const atlas = require(path.join(repo, "experiments", "godel_globes_5d_character_lab", "mechinterp_atlas.js"));
const manifold = require(path.join(repo, "experiments", "godel_globes_5d_character_lab", "mechinterp_manifold.js"));
const etale = require(path.join(repo, "experiments", "godel_globes_5d_character_lab", "mechinterp_etale.js"));

const parameterPoints = manifold.buildPoints(atlas.validate(data));
const templateById = new Map(parameterPoints.map((point) => [`${point.moduleId}:${point.layer}`, point]));

function pointsForCase(item) {
  return item.coordinates.flatMap((stalk, layer) => stalk.map((coordinate, moduleIndex) => {
    const moduleId = item.module_ids[moduleIndex];
    const template = templateById.get(`${moduleId}:${layer}`);
    return Object.freeze({ ...template, x: coordinate[0], y: coordinate[1], z: coordinate[2] });
  }));
}

function localFor(item, state) {
  const map = etale.buildMap(pointsForCase(item));
  return {
    map,
    atlas: etale.buildGluingAtlas(map, state.chart_radius, state.glue_tolerance),
    local: etale.localEquivalences(map, state.layer, state.chart_radius, state.glue_tolerance)
  };
}

test("workflow schedules are deterministic, paired, and counterbalanced", () => {
  const first = core.workflowSchedule("A1", tasks);
  const repeat = core.workflowSchedule("A1", tasks);
  const opposite = core.workflowSchedule("A2", tasks);
  assert.deepEqual(first, repeat);
  assert.equal(first.length, 8);
  assert.deepEqual(new Set(first.map((item) => item.condition)), new Set(["baseline", "triage_progressive"]));
  assert.notEqual(first[0].condition, opposite[0].condition);
  assert.equal(first.filter((item) => item.condition === "baseline").length, 4);
  assert.equal(first.filter((item) => item.condition === "triage_progressive").length, 4);
});

test("component schedules expose each registered design variant exactly once", () => {
  const schedule = core.componentSchedule("R01", tasks);
  assert.equal(schedule.length, 9);
  assert.deepEqual(
    new Set(schedule.map((item) => `${item.design_question}:${item.variant}`)),
    new Set([
      "orientation:heatmap", "orientation:globe", "orientation:case_first",
      "threshold:slider", "threshold:dendrogram_births",
      "language:technical", "language:dual",
      "jobs:inline", "jobs:gated"
    ])
  );
});

test("sealed fixtures instantiate the band, chain, robust, and null task forms", () => {
  assert.equal(catalog.status, "UX_FIXTURES_ONLY");
  assert.equal(catalog.motif_count, 0);
  assert.equal(catalog.cases.length, 8);
  catalog.cases.forEach((item) => {
    assert.equal(item.coordinate_source, "synthetic_ux_fixture");
    assert.equal(item.coordinates.length, 28);
    assert.equal(item.module_ids.length, 7);
    assert.equal(item.outcome_eligible, false);
  });

  const byId = new Map(catalog.cases.map((item) => [item.case_id, item]));
  const bandState = tasks.workflow.find((item) => item.task_type === "band").state_by_case["ux-band-a"];
  const band = localFor(byId.get("ux-band-a"), bandState);
  const firstQk = band.atlas.samples.find((sample) => (
    sample.equivalences.some((edge) => edge.id === "q_proj|k_proj")
  ));
  assert.equal(firstQk.layer, 7);

  const chainState = tasks.workflow.find((item) => item.task_type === "relation").state_by_case["ux-chain-a"];
  const chain = localFor(byId.get("ux-chain-a"), chainState).local;
  const chainComponent = chain.componentDiagnostics.find((item) => item.members.includes("q_proj"));
  assert.equal(chainComponent.clique, false);
  assert.ok(chainComponent.chainExcess > 0);
  assert.deepEqual(chainComponent.bridges, ["k_proj|q_proj", "k_proj|v_proj"]);

  const robustState = tasks.workflow.find((item) => item.task_type === "robustness").state_by_case["ux-robust-a"];
  const robust = localFor(byId.get("ux-robust-a"), robustState).local;
  const robustComponent = robust.componentDiagnostics.find((item) => item.members.includes("q_proj"));
  assert.equal(robustComponent.clique, true);
  assert.equal(robustComponent.bridgeStatus, "none");
  assert.equal(robustComponent.chainExcess, 0);
});
