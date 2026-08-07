import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const require = createRequire(import.meta.url);
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const browserSource = fs.readFileSync(path.join(root, "law_lab.js"), "utf8");
const coreSource = fs.readFileSync(path.join(root, "law_lab_core.js"), "utf8");
const data = require(path.join(root, "example_data.js"));
const jsonData = JSON.parse(fs.readFileSync(path.join(root, "example_data.json"), "utf8"));
const core = require(path.join(root, "law_lab_core.js"));

new vm.Script(browserSource, { filename: "law_lab.js" });
new vm.Script(coreSource, { filename: "law_lab_core.js" });
assert.deepEqual(data, jsonData, "file-safe JS and JSON payloads must agree");

const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]);
assert.equal(ids.length, new Set(ids).size, "HTML ids must be unique");
for (const id of [
  "family-select",
  "complexity-range",
  "phase-chart",
  "base-law-table",
  "pixie-law-table",
  "alignment-map",
  "intervention-list",
  "agent-status",
]) {
  assert(ids.includes(id), `missing required element #${id}`);
}
const scripts = [...html.matchAll(/<script\s+src="([^"]+)"/g)].map((match) => match[1]);
assert.deepEqual(scripts, ["example_data.js", "law_lab_core.js", "law_lab.js"]);
assert(!html.includes("http://") && !html.includes("https://"), "UI must work offline");
assert(!browserSource.includes("fetch("), "browser runtime must use the sealed local payload");
assert(browserSource.includes("window.PixieMechanismLawLab"), "agent API must be exposed");

const state = core.createState(data);
const snapshot = core.agentSnapshot(data, state);
assert.equal(snapshot.claim_status, "IMPLEMENTATION_ONLY");
assert.equal(snapshot.evidence_class, "synthetic_implementation_fixture");
assert.equal(snapshot.dataset_sha256, data.dataset_sha256);

console.log(JSON.stringify({
  status: "PASS",
  contract: "pixie_mechanism_law_lab_page_v1",
  ids: ids.length,
  family_count: data.families.length,
  dataset_sha256: data.dataset_sha256,
}));
