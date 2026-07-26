import assert from "node:assert/strict";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repo = path.resolve(folder, "..", "..");
const require = createRequire(import.meta.url);
const core = require(path.join(folder, "strategy_core.js"));
const tasks = require(path.join(folder, "study_tasks.js"));
const catalog = require(path.join(folder, "sprint_catalog_data.js"));
const scorer = require(path.join(folder, "scorer_manifest.json"));
const data = require(path.join(repo, "experiments", "godel_globes_5d_character_lab", "bonsai_mechinterp_data.js"));
const atlas = require(path.join(repo, "experiments", "godel_globes_5d_character_lab", "mechinterp_atlas.js"));
const manifold = require(path.join(repo, "experiments", "godel_globes_5d_character_lab", "mechinterp_manifold.js"));
const etale = require(path.join(repo, "experiments", "godel_globes_5d_character_lab", "mechinterp_etale.js"));

const parameterPoints = manifold.buildPoints(atlas.validate(data));
const templateById = new Map(parameterPoints.map((point) => [`${point.moduleId}:${point.layer}`, point]));
const caseById = new Map(catalog.cases.map((item) => [item.case_id, item]));

function mapForCase(caseId) {
  const item = caseById.get(caseId);
  const points = item.coordinates.flatMap((stalk, layer) => stalk.map((coordinate, moduleIndex) => {
    const moduleId = item.module_ids[moduleIndex];
    return {
      ...templateById.get(`${moduleId}:${layer}`),
      x: coordinate[0],
      y: coordinate[1],
      z: coordinate[2]
    };
  }));
  return etale.buildMap(points);
}

function structuredAnswer(task) {
  const map = mapForCase(task.case_id);
  const state = task.starting_state;
  const local = etale.localEquivalences(
    map, state.layer, state.chart_radius, state.glue_tolerance
  );
  if (task.task_type === "band") {
    const gluing = etale.buildGluingAtlas(map, state.chart_radius, state.glue_tolerance);
    return gluing.samples.find((sample) => (
      sample.equivalences.some((edge) => edge.id === "q_proj|k_proj")
    )).layer;
  }
  if (task.task_type === "relation") {
    const pair = local.pairs.find((item) => item.id === "q_proj|v_proj");
    if (pair.equivalent) return "direct";
    const component = local.components.find((members) => members.includes("q_proj"));
    return component.includes("v_proj") ? "closure_only" : "none";
  }
  if (task.task_type === "robustness") {
    const component = local.componentDiagnostics.find((item) => item.members.includes("q_proj"));
    if (component.members.length === 1) return "isolated";
    return component.clique && component.bridgeStatus === "none"
      ? "bridge_free_clique"
      : "chained";
  }
  if (task.task_type === "job") {
    return catalog.motif_count === 0
      ? "reference_evaluation_only"
      : "tinylora";
  }
  throw new Error(`unsupported task ${task.task_type}`);
}

const schedule = core.workflowSchedule("AGENT01", tasks);
const outcomes = schedule.map((task) => {
  const answer = structuredAnswer(task);
  const expected = scorer.answers[`${task.case_id}:${task.task_type}`];
  assert.deepEqual(answer, expected);
  return {
    task_id: task.task_id,
    case_id: task.case_id,
    task_type: task.task_type,
    answer,
    expected,
    correct: true,
    source: "structured_etale_fields"
  };
});

const result = {
  schema: "pixieology_mechinterp_ux_agent_smoke_v1",
  experiment_id: "mechinterp_ux_strategy_sprint_v0_1",
  evidence_class: "synthetic_agent_smoke",
  human_usability_evidence: false,
  status: outcomes.every((item) => item.correct) ? "PASS" : "FAIL",
  task_completion: outcomes.length,
  outcomes,
  agent_contract: {
    structured_analysis_used: true,
    svg_parsing_used: false,
    browser_authorization_method_used: false
  },
  conclusion: "The sealed triage tasks are solvable from structured topology fields; this is not human UX or model-motif evidence."
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
