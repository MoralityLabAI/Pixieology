import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const html = fs.readFileSync(path.join(folder, "manifold.html"), "utf8");
const app = fs.readFileSync(path.join(folder, "manifold.js"), "utf8");

test("the manifold application resolves every requested DOM id", () => {
  const ids = Array.from(html.matchAll(/\bid="([^"]+)"/g), (match) => match[1]);
  assert.equal(new Set(ids).size, ids.length);
  const requested = Array.from(app.matchAll(/getElementById\("([^"]+)"\)/g), (match) => match[1]);
  requested.forEach((id) => assert.equal(ids.filter((candidate) => candidate === id).length, 1, `missing ${id}`));
});

test("the page loads only local manifold dependencies", () => {
  const scripts = Array.from(html.matchAll(/<script src="([^"]+)"/g), (match) => match[1]);
  assert.deepEqual(scripts, [
    "bonsai_mechinterp_data.js", "mechinterp_atlas.js", "mechinterp_manifold.js", "manifold.js"
  ]);
  assert.doesNotMatch(html, /https?:\/\//i);
});

test("3D, 4D, and 5D modes and spatial controls are explicit", () => {
  assert.match(html, /option value="3d">3D state space/);
  assert.match(html, /option value="4d">4D depth projection/);
  assert.match(html, /option value="5d">5D spin-category projection/);
  assert.match(html, /id="manifold-layer" type="range"/);
  assert.match(html, /id="manifold-w-angle" type="range"/);
  assert.match(html, /id="manifold-tau" type="range"/);
  assert.match(html, /id="manifold-q" type="range"/);
  assert.match(html, /id="manifold-canvas"[^>]*role="img"/);
});
