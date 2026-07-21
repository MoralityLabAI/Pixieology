(function (root, factory) {
  const value = factory();
  if (typeof module === "object" && module.exports) module.exports = value;
  root.PixieMechinterpAtlas = value;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const schema = "pixieology_mechinterp_atlas_v1";
  const metrics = Object.freeze({
    depth_normalized_energy: Object.freeze({ label: "Update energy across depth", format: (value) => value.toFixed(3) }),
    layer_energy_share: Object.freeze({ label: "Share of layer update energy", format: (value) => `${(value * 100).toFixed(1)}%` }),
    spectral_focus: Object.freeze({ label: "Top-mode energy share", format: (value) => `${(value * 100).toFixed(1)}%` }),
    effective_rank: Object.freeze({ label: "Effective rank", format: (value) => value.toFixed(2) })
  });

  function finite(value, label) {
    const number = Number(value);
    if (!Number.isFinite(number)) throw new Error(`${label} must be finite`);
    return number;
  }

  function validate(input) {
    if (!input || input.schema !== schema) throw new Error(`atlas schema must be ${schema}`);
    if (!Array.isArray(input.modules) || input.modules.length !== 7) throw new Error("atlas requires seven target modules");
    if (!Array.isArray(input.layers) || input.layers.length < 2) throw new Error("atlas requires at least two layers");
    const moduleIds = input.modules.map((module) => String(module.id));
    input.layers.forEach((layer, layerIndex) => {
      if (finite(layer.layer, `layers[${layerIndex}].layer`) !== layerIndex) throw new Error("layers must be contiguous");
      if (!Array.isArray(layer.modules) || layer.modules.length !== moduleIds.length) throw new Error("layer module count mismatch");
      layer.modules.forEach((module, moduleIndex) => {
        if (module.id !== moduleIds[moduleIndex]) throw new Error("module order changed across layers");
        ["energy", "depth_normalized_energy", "layer_energy_share", "spectral_focus", "effective_rank"].forEach((key) => finite(module[key], `${module.id}.${key}`));
        if (!Array.isArray(module.singular_energy_share) || module.singular_energy_share.length !== 8) throw new Error("module spectrum must contain eight modes");
      });
    });
    return input;
  }

  function moduleAt(atlas, layerIndex, moduleId) {
    const normalized = validate(atlas);
    const layer = normalized.layers[Math.max(0, Math.min(normalized.layers.length - 1, Number(layerIndex)))];
    const module = layer.modules.find((candidate) => candidate.id === moduleId);
    if (!module) throw new Error(`unknown module: ${moduleId}`);
    return module;
  }

  function metricValue(module, metricId) {
    if (!metrics[metricId]) throw new Error(`unknown metric: ${metricId}`);
    const value = finite(module[metricId], `${module.id}.${metricId}`);
    return metricId === "effective_rank" ? value / 8 : value;
  }

  function moduleSeries(atlas, moduleId, metricId) {
    return validate(atlas).layers.map((layer) => ({
      layer: layer.layer,
      value: metricValue(layer.modules.find((module) => module.id === moduleId), metricId),
      raw: layer.modules.find((module) => module.id === moduleId)[metricId]
    }));
  }

  function layerSummary(atlas, layerIndex) {
    const normalized = validate(atlas);
    const layer = normalized.layers[Math.max(0, Math.min(normalized.layers.length - 1, Number(layerIndex)))];
    const strongest = layer.modules.reduce((best, module) => module.layer_energy_share > best.layer_energy_share ? module : best);
    return Object.freeze({
      layer: layer.layer,
      totalEnergy: layer.total_energy,
      attentionEnergy: layer.attention_energy,
      mlpEnergy: layer.mlp_energy,
      ratio: layer.mlp_attention_ratio,
      strongest
    });
  }

  return Object.freeze({ schema, metrics, validate, moduleAt, metricValue, moduleSeries, layerSummary });
});
