import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const model = require("../model.js");
const { space } = model;

test("the embodiment is exactly two dimensions per wing and one for the head", () => {
  assert.equal(space.dimensions.length, 5);
  const counts = space.dimensions.reduce((result, dimension) => {
    (result[dimension.anatomy] ??= []).push(dimension);
    return result;
  }, {});
  assert.equal(counts["left-wing"].length, 2);
  assert.equal(counts["right-wing"].length, 2);
  assert.equal(counts.head.length, 1);
  assert.deepEqual(space.tupleOrder, space.dimensions.map((dimension) => dimension.id));
});

test("all authored forms are unique, bounded, and retail-safe", () => {
  const ids = new Set();
  const tuples = new Set();
  const restricted = space.ontologyBoundary.restrictedAnchorTerms;
  for (const anchor of space.anchors) {
    assert.ok(!ids.has(anchor.id), `duplicate anchor id ${anchor.id}`);
    ids.add(anchor.id);
    const key = JSON.stringify(anchor.tuple);
    assert.ok(!tuples.has(key), `duplicate tuple ${key}`);
    tuples.add(key);
    assert.deepEqual(model.clampTuple(anchor.tuple), anchor.tuple);
    const searchable = `${anchor.id} ${anchor.name}`.toLowerCase();
    assert.ok(restricted.every((term) => !searchable.includes(term)), `${anchor.name} crossed the ontology boundary`);
  }
});

test("the rotatable 3D navigation projection preserves authored neighborhood structure", () => {
  const stats = model.projectionStats();
  assert.equal(stats.pairs, 66);
  assert.equal(space.projection.matrix.length, 3);
  assert.ok(stats.fittedExplainedVariance >= 0.90, JSON.stringify(stats));
  assert.ok(stats.spearmanDistanceCorrelation >= 0.95, JSON.stringify(stats));
  assert.ok(stats.normalizedStress <= 0.10, JSON.stringify(stats));
});

test("a 5D warp stays in bounds and reverses exactly", () => {
  const start = model.findAnchor("hedge-trickster").tuple;
  const end = model.findAnchor("moon-archivist").tuple;
  let previousDistance = model.distance5D(start, start);
  for (let step = 0; step <= 40; step += 1) {
    const point = model.interpolateTuple(start, end, step / 40);
    assert.deepEqual(model.clampTuple(point), point);
    const travelled = model.distance5D(start, point);
    assert.ok(travelled + 1e-12 >= previousDistance);
    previousDistance = travelled;
    const reverse = model.interpolateTuple(end, start, 1 - step / 40);
    reverse.forEach((value, index) => assert.ok(Math.abs(value - point[index]) < 1e-12));
  }
  const assertTupleNear = (actual, expected) => {
    actual.forEach((value, index) => assert.ok(Math.abs(value - expected[index]) < 1e-12));
  };
  assertTupleNear(model.interpolateTuple(start, end, 0), start);
  assertTupleNear(model.interpolateTuple(start, end, 1), end);
});

test("authored points round-trip through nearest-neighbor selection", () => {
  for (const anchor of space.anchors) {
    const nearest = model.nearestAnchors(anchor.tuple, 1)[0];
    assert.equal(nearest.anchor.id, anchor.id);
    assert.equal(nearest.distance, 0);
  }
});

test("the game-facing state preserves tuple order and navigation semantics", () => {
  const state = model.characterState([0.5, 0.5, 0.5, 0.5, 0.5]);
  assert.equal(state.schema, "pixieology_character_state_v2");
  assert.equal(state.schema_version, 2);
  assert.deepEqual(state.tuple_order, space.tupleOrder);
  assert.deepEqual(state.values, {
    wonder: 0.5,
    play: 0.5,
    care: 0.5,
    resolve: 0.5,
    reflection: 0.5
  });
  assert.equal(state.anchor_id, "seedling");
  assert.equal(typeof state.projection.z, "number");
  assert.equal(state.projection.semantic_claim, "navigation_only");
});
