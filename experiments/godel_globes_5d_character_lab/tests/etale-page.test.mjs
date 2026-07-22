import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const html = fs.readFileSync(path.join(folder, "etale.html"), "utf8");
const app = fs.readFileSync(path.join(folder, "etale.js"), "utf8");

test("the étale application resolves every requested DOM id", () => {
  const ids = Array.from(html.matchAll(/\bid="([^"]+)"/g), (match) => match[1]);
  assert.equal(new Set(ids).size, ids.length);
  const requested = Array.from(app.matchAll(/getElementById\("([^"]+)"\)/g), (match) => match[1]);
  requested.forEach((id) => assert.equal(ids.filter((candidate) => candidate === id).length, 1, `missing ${id}`));
});

test("the page loads only local étale dependencies in order", () => {
  const scripts = Array.from(html.matchAll(/<script src="([^"]+)"/g), (match) => match[1]);
  assert.deepEqual(scripts, [
    "bonsai_mechinterp_data.js", "mechinterp_atlas.js", "mechinterp_manifold.js", "mechinterp_etale.js", "etale.js"
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
  assert.match(html, /id="etale-map"[^>]*role="img"/);
  assert.match(app, /buildGluingAtlas/);
  assert.match(app, /gluing-band/);
});
