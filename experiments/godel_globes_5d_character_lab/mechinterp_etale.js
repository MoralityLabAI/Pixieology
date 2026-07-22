(function (root, factory) {
  const value = factory();
  if (typeof module === "object" && module.exports) module.exports = value;
  root.PixieMechinterpEtale = value;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function finite(value, label) {
    const number = Number(value);
    if (!Number.isFinite(number)) throw new Error(`${label} must be finite`);
    return number;
  }

  function buildMap(points) {
    if (!Array.isArray(points) || points.length === 0) throw new Error("étale map requires points");
    const layers = [...new Set(points.map((point) => finite(point.layer, "layer")))].sort((a, b) => a - b);
    const moduleIds = [...new Set(points.map((point) => String(point.moduleId)))];
    const lookup = new Map();
    points.forEach((point) => {
      const key = `${point.moduleId}:${point.layer}`;
      if (lookup.has(key)) throw new Error(`duplicate germ ${key}`);
      lookup.set(key, point);
    });
    const base = layers.map((layer, index) => {
      const layerPoints = points.filter((point) => point.layer === layer);
      if (layerPoints.length !== moduleIds.length) throw new Error(`incomplete stalk at layer ${layer}`);
      const w = finite(layerPoints[0].w, "w");
      layerPoints.forEach((point) => {
        if (Math.abs(finite(point.w, "w") - w) > 1e-12) throw new Error(`inconsistent W coordinate at layer ${layer}`);
      });
      return Object.freeze({ layer, index, w });
    });
    const sheets = moduleIds.map((moduleId) => {
      const section = layers.map((layer) => {
        const point = lookup.get(`${moduleId}:${layer}`);
        if (!point) throw new Error(`missing germ ${moduleId}:${layer}`);
        return point;
      });
      return Object.freeze({
        moduleId,
        moduleLabel: String(section[0].moduleLabel),
        family: String(section[0].family),
        points: Object.freeze(section)
      });
    });
    return Object.freeze({
      base: Object.freeze(base),
      layers: Object.freeze(layers),
      moduleIds: Object.freeze(moduleIds),
      sheets: Object.freeze(sheets),
      lookup
    });
  }

  function chartAt(map, layer, radius = 2) {
    if (!map || !Array.isArray(map.layers) || !Array.isArray(map.sheets)) throw new Error("invalid étale map");
    const center = map.layers.indexOf(finite(layer, "layer"));
    if (center < 0) throw new Error(`unknown layer ${layer}`);
    const span = Math.max(1, Math.floor(finite(radius, "radius")));
    const lowerIndex = Math.max(0, center - span);
    const upperIndex = Math.min(map.layers.length - 1, center + span);
    const base = map.base.slice(lowerIndex, upperIndex + 1);
    const allowed = new Set(base.map((entry) => entry.layer));
    const sheets = map.sheets.map((sheet) => Object.freeze({
      moduleId: sheet.moduleId,
      moduleLabel: sheet.moduleLabel,
      family: sheet.family,
      points: Object.freeze(sheet.points.filter((point) => allowed.has(point.layer)))
    }));
    const stalk = Object.freeze(map.sheets.map((sheet) => map.lookup.get(`${sheet.moduleId}:${layer}`)));
    return Object.freeze({
      layer: map.layers[center],
      radius: span,
      lowerLayer: base[0].layer,
      upperLayer: base[base.length - 1].layer,
      base: Object.freeze(base),
      sheets: Object.freeze(sheets),
      stalk
    });
  }

  function sheetAt(map, moduleId) {
    const sheet = map.sheets.find((candidate) => candidate.moduleId === moduleId);
    if (!sheet) throw new Error(`unknown sheet ${moduleId}`);
    return sheet;
  }

  function germAt(map, moduleId, layer) {
    const germ = map.lookup.get(`${moduleId}:${finite(layer, "layer")}`);
    if (!germ) throw new Error(`unknown germ ${moduleId}:${layer}`);
    return germ;
  }

  function overlapCycles(spinResult, chart) {
    if (!spinResult || !Array.isArray(spinResult.cycles)) throw new Error("spin result requires cycles");
    if (!chart || !Array.isArray(chart.base) || chart.base.length === 0) throw new Error("chart requires base samples");
    const lower = chart.base[0].w;
    const upper = chart.base[chart.base.length - 1].w;
    const epsilon = chart.base.length > 1 ? Math.abs(chart.base[1].w - chart.base[0].w) * 0.51 : 1e-9;
    return spinResult.cycles
      .filter((cycle) => cycle.center.w >= lower - epsilon && cycle.center.w <= upper + epsilon)
      .sort((a, b) => a.center.w - b.center.w);
  }

  function nearestCycle(cycles, w) {
    if (!Array.isArray(cycles) || cycles.length === 0) return null;
    const coordinate = finite(w, "w");
    return cycles.reduce((nearest, cycle) => (
      Math.abs(cycle.center.w - coordinate) < Math.abs(nearest.center.w - coordinate) ? cycle : nearest
    ), cycles[0]);
  }

  return Object.freeze({ buildMap, chartAt, sheetAt, germAt, overlapCycles, nearestCycle });
});
