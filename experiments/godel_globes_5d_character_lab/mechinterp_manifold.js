(function (root, factory) {
  const value = factory();
  if (typeof module === "object" && module.exports) module.exports = value;
  root.PixieMechinterpManifold = value;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function finite(value, label) {
    const number = Number(value);
    if (!Number.isFinite(number)) throw new Error(`${label} must be finite`);
    return number;
  }

  function extent(values) {
    return [Math.min(...values), Math.max(...values)];
  }

  function normalize(value, range) {
    const [lower, upper] = range;
    return Math.abs(upper - lower) < 1e-12 ? 0 : ((value - lower) / (upper - lower)) * 2 - 1;
  }

  function buildPoints(atlas) {
    if (!atlas || !Array.isArray(atlas.layers) || !Array.isArray(atlas.modules)) throw new Error("invalid atlas");
    const modules = atlas.layers.flatMap((layer) => layer.modules);
    const focusRange = extent(modules.map((module) => finite(module.spectral_focus, "spectral_focus")));
    const rankRange = extent(modules.map((module) => finite(module.effective_rank, "effective_rank")));
    return atlas.layers.flatMap((layer) => layer.modules.map((module, moduleIndex) => Object.freeze({
      layer: finite(layer.layer, "layer"),
      moduleId: String(module.id),
      moduleLabel: String(module.label),
      moduleIndex,
      family: String(module.family),
      x: finite(module.depth_normalized_energy, "depth_normalized_energy") * 2 - 1,
      y: normalize(finite(module.spectral_focus, "spectral_focus"), focusRange),
      z: normalize(finite(module.effective_rank, "effective_rank"), rankRange),
      w: finite(layer.depth, "depth") * 2 - 1,
      energy: finite(module.energy, "energy"),
      spectralFocus: finite(module.spectral_focus, "spectral_focus"),
      effectiveRank: finite(module.effective_rank, "effective_rank")
    })));
  }

  function rotatePlane(vector, first, second, angle) {
    const cosine = Math.cos(angle);
    const sine = Math.sin(angle);
    const a = vector[first];
    const b = vector[second];
    vector[first] = a * cosine - b * sine;
    vector[second] = a * sine + b * cosine;
  }

  function rotate4D(point, angles = {}) {
    const vector = {
      x: finite(point.x, "x"),
      y: finite(point.y, "y"),
      z: finite(point.z, "z"),
      w: finite(point.w, "w")
    };
    rotatePlane(vector, "x", "w", finite(angles.xw || 0, "xw"));
    rotatePlane(vector, "y", "w", finite(angles.yw || 0, "yw"));
    rotatePlane(vector, "z", "w", finite(angles.zw || 0, "zw"));
    return vector;
  }

  function rotate3D(point, yaw, pitch) {
    const cosineYaw = Math.cos(yaw);
    const sineYaw = Math.sin(yaw);
    const cosinePitch = Math.cos(pitch);
    const sinePitch = Math.sin(pitch);
    const x = point.x * cosineYaw - point.z * sineYaw;
    const zYaw = point.x * sineYaw + point.z * cosineYaw;
    return {
      x,
      y: point.y * cosinePitch - zYaw * sinePitch,
      z: point.y * sinePitch + zYaw * cosinePitch,
      w: point.w
    };
  }

  function projectPoint(point, options = {}) {
    const mode = options.mode === "4d" ? "4d" : "3d";
    const spatial = mode === "4d" ? rotate4D(point, options.angles) : point;
    const camera = rotate3D(spatial, finite(options.yaw || 0, "yaw"), finite(options.pitch || 0, "pitch"));
    const distance = 4.2;
    const perspective = distance / Math.max(1.2, distance - camera.z);
    return {
      x: camera.x * perspective,
      y: camera.y * perspective,
      depth: camera.z,
      scale: perspective,
      w: point.w
    };
  }

  function sliceWeight(w, center, width = 0.34) {
    const distance = Math.abs(finite(w, "w") - finite(center, "center"));
    return Math.max(0.08, Math.exp(-Math.pow(distance / Math.max(0.05, width), 2)));
  }

  function vectorNorm(point) {
    return Math.hypot(point.x, point.y, point.z, point.w);
  }

  return Object.freeze({ buildPoints, projectPoint, rotate4D, rotate3D, sliceWeight, vectorNorm });
});
