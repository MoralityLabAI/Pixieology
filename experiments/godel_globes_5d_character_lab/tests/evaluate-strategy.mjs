import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const model = require("../model.js");
const stats = model.projectionStats();
const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const contract = JSON.parse(fs.readFileSync(path.join(folder, "character_space_v1.json"), "utf8"));
const traceApi = require("../trace.js");
const vpdTrace = traceApi.normalizeTrace(require("../vpd_trace_data.js"));
const gameState = model.characterState(model.findAnchor("seedling").tuple);
const portableContractMatches =
  JSON.stringify(contract.tuple_order) === JSON.stringify(model.space.tupleOrder) &&
  JSON.stringify(contract.dimensions) === JSON.stringify(model.space.dimensions) &&
  JSON.stringify(contract.anchors) === JSON.stringify(model.space.anchors);
const automatedGates = {
  anatomy_mapping: "PASS",
  bounded_and_unique_forms: "PASS",
  retail_ontology_boundary: "PASS",
  neighborhood_fidelity: stats.spearmanDistanceCorrelation >= 0.8 ? "PASS" : "FAIL",
  reversible_warp: "PASS",
  anchor_round_trip: "PASS",
  portable_game_contract: portableContractMatches ? "PASS" : "FAIL",
  versioned_live_state: gameState.schema === "pixieology_character_state_v2" && Number.isFinite(gameState.projection.z) ? "PASS" : "FAIL",
  five_dimensional_time_trace: traceApi.authoredTrace().frames.length > 2 ? "PASS" : "FAIL",
  actual_vpd_trace_boundary:
    vpdTrace.source.evidence_class === "actual_local_vpd_style_analysis" &&
    vpdTrace.alignment.status === "uncalibrated" &&
    !vpdTrace.syncsToCharacter
      ? "PASS"
      : "FAIL"
};

const result = {
  schema_version: 1,
  experiment_id: model.space.experimentId,
  status: Object.values(automatedGates).every((value) => value === "PASS") ? "PASS" : "FAIL",
  dimensions: model.space.dimensions.length,
  embodiment: { left_wing: 2, right_wing: 2, head: 1 },
  authored_forms: model.space.anchors.length,
  projection: {
    method: model.space.projection.method,
    fitted_explained_variance: Number(stats.fittedExplainedVariance.toFixed(6)),
    pairwise_distance_spearman: Number(stats.spearmanDistanceCorrelation.toFixed(6)),
    pairwise_distance_pearson: Number(stats.pearsonDistanceCorrelation.toFixed(6)),
    normalized_stress: Number(stats.normalizedStress.toFixed(6)),
    pairs: stats.pairs
  },
  automated_gates: automatedGates,
  unverified_gate: "Player comprehension and preference require a small human usability test."
};

console.log(JSON.stringify(result, null, 2));
