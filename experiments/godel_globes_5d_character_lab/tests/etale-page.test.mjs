import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(import.meta.url);
const html = fs.readFileSync(path.join(folder, "etale.html"), "utf8");
const app = fs.readFileSync(path.join(folder, "etale.js"), "utf8");
const uxCase = fs.readFileSync(path.join(folder, "ETALE_UX_CASE.md"), "utf8");
const feedbackQueue = require(path.join(folder, "feedback_job_queue_data.js"));

test("the étale application resolves every requested DOM id", () => {
  const ids = Array.from(html.matchAll(/\bid="([^"]+)"/g), (match) => match[1]);
  assert.equal(new Set(ids).size, ids.length);
  const requested = Array.from(app.matchAll(/getElementById\("([^"]+)"\)/g), (match) => match[1]);
  requested.forEach((id) => assert.equal(ids.filter((candidate) => candidate === id).length, 1, `missing ${id}`));
});

test("the page loads only local étale dependencies in order", () => {
  const scripts = Array.from(html.matchAll(/<script src="([^"]+)"/g), (match) => match[1]);
  assert.deepEqual(scripts, [
    "bonsai_mechinterp_data.js", "mechinterp_atlas.js", "mechinterp_manifold.js", "mechinterp_etale.js",
    "motif_catalog_data.js", "feedback_job_queue_data.js", "etale.js"
  ]);
  assert.doesNotMatch(html, /https?:\/\//i);
});

test("the five coordinates, local chart, and evidence controls are explicit", () => {
  assert.match(html, /id="etale-layer"[^>]*type="range"/);
  assert.match(html, /id="etale-module"/);
  assert.match(html, /id="etale-radius"[^>]*type="range"/);
  assert.match(html, /id="etale-epsilon"[^>]*type="range"/);
  assert.match(html, /id="etale-tau"[^>]*type="range"/);
  assert.match(html, /id="etale-q"[^>]*type="range"/);
  assert.match(html, /X · update coord/);
  assert.match(html, /Y · focus/);
  assert.match(html, /Z · rank/);
  assert.match(html, /W · depth/);
  assert.match(html, /S · overlap/);
  assert.match(html, /G · local gluing/);
  assert.match(html, /M · motif catalog/);
  assert.match(html, /id="etale-map"[^>]*role="img"/);
  assert.match(app, /buildGluingAtlas/);
  assert.match(app, /gluing-band/);
});

test("the explorer exposes deterministic state, receipt, event, and URI surfaces for agents", () => {
  assert.match(html, /id="etale-analysis-json" type="application\/json"/);
  ["layer", "module_id", "chart_radius", "glue_tolerance", "lineage_floor", "spin_noise"].forEach((key) => {
    assert.match(html, new RegExp(`data-state-key="${key}"`));
  });
  assert.match(app, /window\.PixieEtaleExplorer = Object\.freeze/);
  assert.match(app, /dom_receipt_id: "etale-analysis-json"/);
  assert.match(app, /state_fields: Object\.freeze/);
  [
    "getContract", "getState", "setState", "setPlaying", "getAnalysis", "getShareUrl",
    "getMotifCatalog", "listCases", "loadCase", "listMotifs", "getMotif",
    "getJobQueue", "listJobs", "getJob", "selectJob", "getSelectedJob"
  ].forEach((method) => {
    assert.match(app, new RegExp(`${method}:`));
  });
  assert.match(app, /pixieology:etale-analysis/);
  assert.match(app, /loadInitialQuery/);
  assert.match(app, /history\.replaceState/);
  assert.match(app, /data-transition-kind/);
  assert.match(app, /direct_glued_partners/);
  assert.match(app, /closure_component/);
  assert.match(app, /direct_neighbor/);
  assert.match(app, /selected_component/);
  assert.match(app, /dendrogram_mst/);
  assert.match(app, /bridge: none/);
  assert.match(app, /activation_conditioned_trained_counterfactual_on_base/);
  assert.match(app, /function pointsForCase/);
  assert.match(app, /coordinate_source: activeCase/);
  assert.match(app, /selected_job_id/);
  assert.match(app, /automatic_authorization/);
  assert.match(app, /selection is inspection state and never authorization/i);
});

test("the feedback tray slots immutable jobs without a browser execution path", () => {
  assert.match(html, /id="feedback-job-rows"/);
  assert.match(html, /Proposed TinyLoRA \/ QLoRA jobs/);
  assert.match(html, /authorization and execution remain outside the browser/i);
  assert.match(app, /pixieology_lora_feedback_queue_v1/);
  assert.match(app, /job_sha256/);
  assert.doesNotMatch(app, /\bauthorizeJob\b|\brunJob\b|\bexecuteJob\b/);
  assert.equal(feedbackQueue.schema, "pixieology_lora_feedback_queue_v1");
  assert.equal(feedbackQueue.status, "STAGED_NOT_AUTHORIZED");
  assert.equal(feedbackQueue.automatic_authorization, false);
  assert.equal(feedbackQueue.training_slot_status, "BLOCKED_NO_CONFIRMED_CATALOG");
  assert.deepEqual(feedbackQueue.jobs.map((job) => job.method), ["base_qwen_derived_1p7b", "pixie_rank8"]);
  feedbackQueue.jobs.forEach((job) => {
    assert.equal(job.authorization.status, "NOT_AUTHORIZED");
    assert.match(job.authorization.job_sha256, /^[a-f0-9]{64}$/);
    assert.deepEqual(job.resources, { cpu_pct: 50, io_mb_s: 50, ram_mb: 2048, timeout_seconds: 1800 });
  });
});

test("the UX case states the decision, alternatives, claim boundary, and agent contract", () => {
  assert.match(uxCase, /complements the globe rather than replacing it/i);
  assert.match(uxCase, /tolerance relation/i);
  assert.match(uxCase, /single-linkage transitive closure/i);
  assert.match(uxCase, /Parallel coordinates/);
  assert.match(uxCase, /window\.PixieEtaleExplorer\.getAnalysis\(\)/);
  assert.match(uxCase, /answer accuracy, time, and unsupported/i);
});
