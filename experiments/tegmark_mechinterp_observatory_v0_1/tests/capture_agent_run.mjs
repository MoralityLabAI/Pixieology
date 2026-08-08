import fs from "node:fs";
import path from "node:path";
import {createRequire} from "node:module";
import {fileURLToPath} from "node:url";

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const core = require(path.join(root, "observatory_core.js"));
const data = JSON.parse(fs.readFileSync(path.join(root, "example_data.json"), "utf8"));
const selection = core.defaultSelection(data);

const steps = [
  ["bimt", {bimtMethod: "bimt", bimtEdge: 0}],
  ["clock_pizza", {clockWidth: 64, clockAttention: 1}],
  ["hypernetwork", {hyperBeta: 0.0001, hyperStep: 3200, hyperView: "phase"}],
  ["mips", {mipsCase: "binary_addition", mipsStage: 5}],
  ["sid", {sidSystem: "harmonic_oscillator", sidView: "trajectories"}],
  ["open_problems", {claimGoal: "control"}]
];

const snapshots = steps.map(([lens, patch]) => {
  Object.assign(selection, patch);
  return core.snapshot(data, lens, selection);
});

const receipt = {
  schema_version: "tegmark_mechinterp_observatory.example_exploration.v1",
  run_kind: "deterministic_agent_contract_test",
  fixture_sha256: data.fixture_sha256,
  evidence_class: data.evidence_class,
  steps: snapshots,
  conclusion: {
    useful_chain: "training geometry → algorithm phase → program compiler → invariant → validation route",
    empirical_claim: false,
    next_gate: "Replace exactly one synthetic lens with registered model evidence before making a mechanism claim."
  }
};

if (process.argv.includes("--capture")) {
  fs.writeFileSync(path.join(root, "example_exploration_receipt.json"), JSON.stringify(receipt, null, 2) + "\n");
}

if (snapshots.length !== 6 || snapshots.some(s => !s.next_evidence_action)) process.exitCode = 1;
else console.log(JSON.stringify({steps: snapshots.length, fixture_sha256: data.fixture_sha256, capture: process.argv.includes("--capture")}));
