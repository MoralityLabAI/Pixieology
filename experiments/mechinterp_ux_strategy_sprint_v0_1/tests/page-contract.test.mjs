import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const baseline = fs.readFileSync(path.join(folder, "baseline.html"), "utf8");
const triage = fs.readFileSync(path.join(folder, "triage.html"), "utf8");
const triageApp = fs.readFileSync(path.join(folder, "triage.js"), "utf8");
const study = fs.readFileSync(path.join(folder, "index.html"), "utf8");
const studyApp = fs.readFileSync(path.join(folder, "study.js"), "utf8");

function assertDomContract(html, app, dynamicIds = []) {
  const ids = Array.from(html.matchAll(/\bid="([^"]+)"/g), (match) => match[1]);
  assert.equal(ids.length, new Set(ids).size);
  const requested = Array.from(app.matchAll(/getElementById\("([^"]+)"\)/g), (match) => match[1]);
  requested.forEach((id) => assert.ok(ids.includes(id) || dynamicIds.includes(id), `missing DOM id ${id}`));
}

test("study and triage applications resolve their DOM contracts", () => {
  assertDomContract(study, studyApp, ["task-answer"]);
  assertDomContract(triage, triageApp);
});

test("both workspaces load only local deterministic dependencies", () => {
  [baseline, triage, study].forEach((html) => assert.doesNotMatch(html, /<script[^>]+src="https?:/i));
  assert.match(baseline, /sprint_catalog_data\.js/);
  assert.match(triage, /sprint_catalog_data\.js/);
  assert.match(triage, /etale\.js/);
  assert.match(study, /strategy_core\.js/);
});

test("the progressive surface exposes structured decisions without SVG parsing", () => {
  assert.match(triageApp, /birthEpsilon/);
  assert.doesNotMatch(triageApp, /edge\.distance/);
  assert.match(triageApp, /getDecisionState/);
  assert.match(triageApp, /function renderGlobe/);
  assert.match(triage, /S is unavailable/);
  assert.doesNotMatch(triage, /manifold\.html/);
  assert.match(triageApp, /browser_authorization_available:\s*false/);
  assert.match(triageApp, /browser_execution_available:\s*false/);
  assert.match(triage, /Descriptive local topology only/);
  assert.match(triage, /S is unavailable/);
});

test("the study API preserves sealed order and has no authorization method", () => {
  assert.match(studyApp, /only the next sealed task may be loaded/);
  assert.match(studyApp, /getCurrentTask/);
  assert.match(studyApp, /getWorkspaceAnalysis/);
  assert.match(studyApp, /network_telemetry:\s*false/);
  assert.doesNotMatch(studyApp, /\bauthorizeJob\b|\brunJob\b|\bexecuteJob\b/);
});
