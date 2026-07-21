import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const html = fs.readFileSync(path.join(folder, "mechinterp.html"), "utf8");
const app = fs.readFileSync(path.join(folder, "mechinterp.js"), "utf8");

test("every atlas DOM id requested by the application exists exactly once", () => {
  const authoredIds = Array.from(html.matchAll(/\bid="([^"]+)"/g), (match) => match[1]);
  assert.equal(new Set(authoredIds).size, authoredIds.length);
  const requestedIds = Array.from(app.matchAll(/getElementById\("([^"]+)"\)/g), (match) => match[1]);
  requestedIds.forEach((id) => assert.equal(authoredIds.filter((candidate) => candidate === id).length, 1, `missing DOM id ${id}`));
});

test("the standalone atlas uses only local scripts in dependency order", () => {
  const scripts = Array.from(html.matchAll(/<script src="([^"]+)"/g), (match) => match[1]);
  assert.deepEqual(scripts, ["bonsai_mechinterp_data.js", "mechinterp_atlas.js", "mechinterp.js"]);
  assert.doesNotMatch(html, /https?:\/\//i);
});

test("the page exposes native playback, metric, and layer controls", () => {
  assert.match(html, /id="atlas-play"[^>]*type="button"/);
  assert.match(html, /id="atlas-layer"[^>]*type="range"/);
  assert.match(html, /id="atlas-metric"/);
  assert.match(html, /id="atlas-heatmap"[^>]*role="grid"/);
});
