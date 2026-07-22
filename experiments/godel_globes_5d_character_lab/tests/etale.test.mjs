import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(import.meta.url);
const data = require(path.join(folder, "bonsai_mechinterp_data.js"));
const atlas = require(path.join(folder, "mechinterp_atlas.js"));
const manifold = require(path.join(folder, "mechinterp_manifold.js"));
const etale = require(path.join(folder, "mechinterp_etale.js"));

const points = manifold.buildPoints(atlas.validate(data));

test("the finite étale map has seven complete sheets over 28 depth stalks", () => {
  const map = etale.buildMap(points);
  assert.equal(map.base.length, 28);
  assert.equal(map.sheets.length, 7);
  map.sheets.forEach((sheet) => assert.equal(sheet.points.length, 28));
  map.base.forEach((entry) => {
    assert.equal(map.sheets.filter((sheet) => sheet.points.some((point) => point.layer === entry.layer)).length, 7);
  });
});

test("a local chart clips at the base boundary and retains every local section", () => {
  const map = etale.buildMap(points);
  const chart = etale.chartAt(map, 0, 3);
  assert.deepEqual(chart.base.map((entry) => entry.layer), [0, 1, 2, 3]);
  assert.equal(chart.stalk.length, 7);
  chart.sheets.forEach((sheet) => assert.equal(sheet.points.length, 4));
  assert.equal(etale.germAt(map, "q_proj", 0).moduleLabel, "Query");
});

test("spin certificates attach to chart overlaps rather than model nodes", () => {
  const map = etale.buildMap(points);
  const chart = etale.chartAt(map, 13, 2);
  const spin = manifold.analyzeSpinLadder(points, "q_proj", "gate_proj", 0.2, 0.15);
  const overlaps = etale.overlapCycles(spin, chart);
  assert.ok(overlaps.length > 0);
  overlaps.forEach((cycle) => {
    assert.ok(cycle.center.w >= chart.base[0].w - 0.08);
    assert.ok(cycle.center.w <= chart.base.at(-1).w + 0.08);
  });
  assert.ok(etale.nearestCycle(spin.cycles, etale.germAt(map, "q_proj", 13).w));
});
