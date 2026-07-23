import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const html = fs.readFileSync(path.join(folder, "etale.html"), "utf8");
const app = fs.readFileSync(path.join(folder, "etale.js"), "utf8");
const uxCase = fs.readFileSync(path.join(folder, "ETALE_UX_CASE.md"), "utf8");

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
    "motif_catalog_data.js", "etale.js"
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
    "getMotifCatalog", "listCases", "loadCase", "listMotifs", "getMotif"
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
});

test("the UX case states the decision, alternatives, claim boundary, and agent contract", () => {
  assert.match(uxCase, /complements the globe rather than replacing it/i);
  assert.match(uxCase, /tolerance relation/i);
  assert.match(uxCase, /single-linkage transitive closure/i);
  assert.match(uxCase, /Parallel coordinates/);
  assert.match(uxCase, /window\.PixieEtaleExplorer\.getAnalysis\(\)/);
  assert.match(uxCase, /answer accuracy, time, and unsupported/i);
});
