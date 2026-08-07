import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const require = createRequire(import.meta.url);
const data = require(path.join(root, "example_data.js"));
const core = require(path.join(root, "law_lab_core.js"));
const receiptPath = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(root, "example_session_receipt.json");

let state = core.createState(data);
const events = [];
function run(action) {
  state = core.reduce(data, state, action);
  const snapshot = core.agentSnapshot(data, state);
  events.push({ action, snapshot });
  return snapshot;
}

const target = data.families.reduce((best, family) =>
  family.default_complexity > best.default_complexity ? family : best
);
run({ type: "SELECT_FAMILY", familyId: target.task_family_id });
const underfitK = target.complexity_values.find((stateCount) =>
  !target.candidates.base_qwen_derived_1p7b.phase_scan.find(
    (row) => row.state_count === stateCount
  ).qualified
);
assert.notEqual(underfitK, undefined, "example must contain an underfit phase");
const underfit = run({ type: "SET_COMPLEXITY", complexity: underfitK });
assert.equal(underfit.phase_status, "UNDERFIT_AT_K");

const selectedK = target.default_complexity;
const selected = run({ type: "SET_COMPLEXITY", complexity: selectedK });
assert.equal(selected.phase_status, "PROVISIONAL_ISOMORPHISM");
assert.equal(selected.selected_by_protocol, true);
assert.equal(selected.alignment_fidelity, 1);
run({ type: "SELECT_CANDIDATE", candidate: "pixie_rank8" });
const phase = core.phaseAt(target, "pixie_rank8", selectedK);
run({ type: "SELECT_TRANSITION", key: core.transitionKey(phase.transition_table[0]) });
const intervention = target.candidates.pixie_rank8.interventions[0];
const finalSnapshot = run({
  type: "SELECT_INTERVENTION",
  observationId: intervention.observation_id,
});
assert.equal(
  finalSnapshot.selected_intervention.predicted_output_symbol,
  finalSnapshot.selected_intervention.observed_output_symbol
);
assert.equal(finalSnapshot.claim_status, "IMPLEMENTATION_ONLY");

const receipt = {
  schema: "pixieology_mechanism_law_lab_agent_session_v1",
  session_id: `law-lab-smoke-${data.dataset_sha256.slice(0, 12)}`,
  status: "PASS",
  dataset_sha256: data.dataset_sha256,
  evidence_class: data.evidence_class,
  human_or_model_evidence: false,
  agent_contract: {
    actions_exercised: [...new Set(events.map((event) => event.action.type))],
    event_count: events.length,
  },
  events,
  result: {
    family_id: target.task_family_id,
    underfit_snapshot: underfit,
    selected_snapshot: selected,
    final_snapshot: finalSnapshot,
    law_read: `${finalSnapshot.focus_candidate} q${finalSnapshot.selected_transition.state} + ${finalSnapshot.selected_transition.input_symbol} -> q${finalSnapshot.selected_transition.next_state} / ${finalSnapshot.selected_transition.output_symbol}`,
    intervention_read: `${finalSnapshot.selected_intervention.predicted_output_symbol} predicted and observed; random control stayed at ${finalSnapshot.selected_intervention.matched_random_output_symbol}`,
    claim_status: "IMPLEMENTATION_ONLY",
  },
  claim_boundary: data.claim_boundary,
};
fs.writeFileSync(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
console.log(JSON.stringify({
  status: receipt.status,
  session_id: receipt.session_id,
  family_id: receipt.result.family_id,
  underfit_k: receipt.result.underfit_snapshot.complexity_state_count,
  selected_k: receipt.result.selected_snapshot.complexity_state_count,
  phase_status: receipt.result.selected_snapshot.phase_status,
  claim_status: receipt.result.claim_status,
  receipt: receiptPath,
}));
