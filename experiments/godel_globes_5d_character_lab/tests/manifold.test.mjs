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

test("the manifold contains one state for every layer and target module", () => {
  const points = manifold.buildPoints(atlas.validate(data));
  assert.equal(points.length, 28 * 7);
  assert.equal(Math.min(...points.map((point) => point.w)), -1);
  assert.equal(Math.max(...points.map((point) => point.w)), 1);
  points.forEach((point) => {
    assert.ok(point.x >= -1 && point.x <= 1);
    assert.ok(point.y >= -1 && point.y <= 1);
    assert.ok(point.z >= -1 && point.z <= 1);
  });
});

test("four-dimensional rotations preserve Euclidean norm", () => {
  const point = { x: 0.2, y: -0.7, z: 0.5, w: 0.9 };
  const rotated = manifold.rotate4D(point, { xw: 0.4, yw: -0.9, zw: 1.2 });
  assert.ok(Math.abs(manifold.vectorNorm(point) - manifold.vectorNorm(rotated)) < 1e-12);
});

test("3D and 4D projection paths are finite and observably distinct", () => {
  const point = { x: 0.2, y: -0.7, z: 0.5, w: 0.9 };
  const three = manifold.projectPoint(point, { mode: "3d", yaw: 0.2, pitch: 0.1 });
  const four = manifold.projectPoint(point, {
    mode: "4d", yaw: 0.2, pitch: 0.1, angles: { xw: 0.8, yw: -0.3, zw: 0.2 }
  });
  [three, four].forEach((projection) => Object.values(projection).forEach((value) => assert.ok(Number.isFinite(value))));
  assert.notEqual(three.x, four.x);
  assert.notEqual(three.y, four.y);
});

test("the 4D depth slice is strongest at its selected W coordinate", () => {
  assert.equal(manifold.sliceWeight(0.25, 0.25), 1);
  assert.ok(manifold.sliceWeight(-1, 1) < manifold.sliceWeight(0.5, 1));
});
