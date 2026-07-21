import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(import.meta.url);
const data = require(path.join(folder, "bonsai_mechinterp_data.js"));
const atlas = require(path.join(folder, "mechinterp_atlas.js"));

test("the generated atlas retains all layers, targets, and evidence boundaries", () => {
  assert.equal(atlas.validate(data), data);
  assert.equal(data.layers.length, 28);
  assert.deepEqual(data.modules.map((module) => module.id), [
    "q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"
  ]);
  assert.equal(data.source.activation_vpd, false);
  assert.equal(data.source.base_model_loaded, false);
  assert.match(data.claim_boundary, /does not identify semantic features, activations, or causal circuits/i);
});

test("energy shares and effective ranks remain physically bounded", () => {
  data.layers.forEach((layer) => {
    const energyShare = layer.modules.reduce((sum, module) => sum + module.layer_energy_share, 0);
    assert.ok(Math.abs(energyShare - 1) < 1e-9);
    layer.modules.forEach((module) => {
      assert.ok(module.effective_rank >= 1 && module.effective_rank <= 8);
      assert.ok(Math.abs(module.singular_energy_share.reduce((sum, value) => sum + value, 0) - 1) < 1e-9);
    });
  });
});

test("module trajectories expose every layer and preserve raw metric values", () => {
  const series = atlas.moduleSeries(data, "q_proj", "effective_rank");
  assert.equal(series.length, 28);
  assert.deepEqual(series.map((row) => row.layer), Array.from({ length: 28 }, (_, index) => index));
  series.forEach((row) => assert.equal(row.value, row.raw / 8));
});
