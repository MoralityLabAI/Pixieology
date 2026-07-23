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

test("local equivalence is symmetric, tolerance-bounded, and preserves global identities", () => {
  const map = etale.buildMap(points);
  const chart = etale.chartAt(map, 5, 2);
  assert.equal(etale.localDistance(chart, "gate_proj", "gate_proj"), 0);
  assert.equal(etale.localDistance(chart, "gate_proj", "up_proj"), etale.localDistance(chart, "up_proj", "gate_proj"));

  const strict = etale.localEquivalences(map, 5, 2, 0.15);
  assert.equal(strict.equivalences.length, 0);
  assert.equal(strict.components.length, 7);

  const glued = etale.localEquivalences(map, 5, 2, 0.20);
  assert.deepEqual(glued.equivalences.map((pair) => pair.id), ["v_proj|o_proj", "gate_proj|up_proj"]);
  assert.equal(glued.components.length, 5);
  assert.equal(map.sheets.length, 7);
});

test("the gluing atlas records contiguous bands and quotient transitions without inventing monodromy", () => {
  const map = etale.buildMap(points);
  const gluing = etale.buildGluingAtlas(map, 2, 0.25);
  assert.equal(gluing.hasNontrivialGluing, true);
  assert.ok(gluing.bands.some((band) => band.id === "gate_proj|up_proj:1-7"));
  assert.ok(gluing.transitions.some((transition) => transition.kind === "merge"));
  assert.ok(gluing.transitions.some((transition) => transition.kind === "split"));
  assert.equal(gluing.metric.id, "normalized_xyz_rms_v1");
  assert.equal(gluing.metric.normalization.x, "per_module_full_depth_minmax_to_minus1_plus1");
  assert.equal(gluing.metric.normalization.y, "global_all_module_layer_minmax_to_minus1_plus1");
  assert.equal(gluing.metric.normalization.windowDependent, false);
  assert.equal(gluing.metric.uncertainty, "not_available_in_source_atlas");
  assert.equal(gluing.distanceCache.method, "global_normalization_prefix_squared_difference_v1");
  assert.equal(gluing.distanceCache.windowDependentNormalization, false);
  assert.equal(gluing.samples.every((sample) => sample.dendrogramMst.length === 6), true);
  assert.equal(gluing.monodromy.available, false);
  assert.match(gluing.monodromy.reason, /interval/);
});

test("prefix-sum distances equal brute-force chart distances at every boundary shape", () => {
  const map = etale.buildMap(points);
  [1, 2, 4].forEach((radius) => {
    const cache = etale.buildDistanceCache(map, radius);
    [0, 5, 13, 27].forEach((layer) => {
      const chart = etale.chartAt(map, layer, radius);
      const sample = cache.samples.get(layer);
      ["q_proj|k_proj", "gate_proj|up_proj", "v_proj|o_proj"].forEach((id) => {
        const [left, right] = id.split("|");
        assert.ok(Math.abs(sample.distances.get(id) - etale.localDistance(chart, left, right)) < 1e-12);
      });
    });
  });
});

test("component diagnostics expose chain excess, articulation bridges, and robust no-bridge status", () => {
  const synthetic = [
    { moduleId: "a", moduleLabel: "A", family: "x", layer: 0, w: 0, x: 0.0, y: 0, z: 0 },
    { moduleId: "b", moduleLabel: "B", family: "x", layer: 0, w: 0, x: 0.2, y: 0, z: 0 },
    { moduleId: "c", moduleLabel: "C", family: "x", layer: 0, w: 0, x: 0.4, y: 0, z: 0 },
    { moduleId: "a", moduleLabel: "A", family: "x", layer: 1, w: 1, x: 0.0, y: 0, z: 0 },
    { moduleId: "b", moduleLabel: "B", family: "x", layer: 1, w: 1, x: 0.2, y: 0, z: 0 },
    { moduleId: "c", moduleLabel: "C", family: "x", layer: 1, w: 1, x: 0.4, y: 0, z: 0 }
  ];
  const map = etale.buildMap(synthetic);
  const chain = etale.localEquivalences(map, 0, 1, 0.12);
  const diagnostic = chain.componentDiagnostics.find((item) => item.members.length === 3);
  assert.equal(diagnostic.clique, false);
  assert.ok(diagnostic.chainExcess > 0);
  assert.deepEqual(diagnostic.bridges, ["a|b", "b|c"]);
  assert.deepEqual(diagnostic.articulationVertices, ["b"]);

  const triangle = etale.tarjanDiagnostics(["a", "b", "c"], [
    { a: "a", b: "b" }, { a: "b", b: "c" }, { a: "a", b: "c" }
  ]);
  assert.equal(triangle.bridgeStatus, "none");
  assert.equal(triangle.twoEdgeConnected, true);
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
