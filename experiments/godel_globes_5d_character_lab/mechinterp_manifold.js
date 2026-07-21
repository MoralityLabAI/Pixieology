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
      w: finite(point.w, "w"),
      s: finite(point.s || 0, "s")
    };
    rotatePlane(vector, "x", "w", finite(angles.xw || 0, "xw"));
    rotatePlane(vector, "y", "w", finite(angles.yw || 0, "yw"));
    rotatePlane(vector, "z", "w", finite(angles.zw || 0, "zw"));
    return vector;
  }

  function rotate5D(point, angles = {}) {
    const vector = {
      x: finite(point.x, "x"),
      y: finite(point.y, "y"),
      z: finite(point.z, "z"),
      w: finite(point.w, "w"),
      s: finite(point.s || 0, "s")
    };
    rotatePlane(vector, "x", "w", finite(angles.xw || 0, "xw"));
    rotatePlane(vector, "y", "w", finite(angles.yw || 0, "yw"));
    rotatePlane(vector, "z", "w", finite(angles.zw || 0, "zw"));
    rotatePlane(vector, "x", "s", finite(angles.xs || 0, "xs"));
    rotatePlane(vector, "y", "s", finite(angles.ys || 0, "ys"));
    rotatePlane(vector, "z", "s", finite(angles.zs || 0, "zs"));
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
    const mode = options.mode === "5d" ? "5d" : options.mode === "4d" ? "4d" : "3d";
    const spatial = mode === "5d" ? rotate5D(point, options.angles) : mode === "4d" ? rotate4D(point, options.angles) : point;
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
    return Math.hypot(point.x, point.y, point.z, point.w, point.s || 0);
  }

  function hashUnit(text) {
    let hash = 2166136261;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0) / 4294967296;
  }

  function proxyRetention(first, second) {
    const distanceSquared = Math.pow(first.x - second.x, 2) + Math.pow(first.y - second.y, 2) + Math.pow(first.z - second.z, 2);
    return Math.exp(-0.55 * distanceSquared);
  }

  function fundamentalCycles(nodeIds, edges) {
    const parent = new Map(nodeIds.map((id) => [id, id]));
    function find(id) {
      let value = id;
      while (parent.get(value) !== value) value = parent.get(value);
      while (parent.get(id) !== id) {
        const next = parent.get(id);
        parent.set(id, value);
        id = next;
      }
      return value;
    }
    const tree = [];
    const chords = [];
    edges.forEach((edge) => {
      const first = find(edge.a);
      const second = find(edge.b);
      if (first !== second) {
        parent.set(first, second);
        tree.push(edge);
      } else {
        chords.push(edge);
      }
    });
    const adjacency = new Map(nodeIds.map((id) => [id, []]));
    tree.forEach((edge) => {
      adjacency.get(edge.a).push({ node: edge.b, edge });
      adjacency.get(edge.b).push({ node: edge.a, edge });
    });
    return chords.map((chord, cycleIndex) => {
      const queue = [chord.a];
      const previous = new Map([[chord.a, null]]);
      while (queue.length && !previous.has(chord.b)) {
        const node = queue.shift();
        adjacency.get(node).forEach((step) => {
          if (!previous.has(step.node)) {
            previous.set(step.node, { node, edge: step.edge });
            queue.push(step.node);
          }
        });
      }
      const path = [];
      let cursor = chord.b;
      while (cursor !== chord.a) {
        const step = previous.get(cursor);
        if (!step) throw new Error("tree path missing for chord");
        path.push(step.edge);
        cursor = step.node;
      }
      return { id: `cycle-${cycleIndex}`, edges: [...path, chord] };
    });
  }

  function distanceReceipt(cycles, edges) {
    const syndrome = cycles.map((cycle) => cycle.sign < 0 ? 1 : 0);
    if (!syndrome.some(Boolean)) return { mode: "exact", lower: 0, upper: 0, value: 0 };
    if (cycles.length <= 12) {
      const edgeMasks = edges.map((edge) => cycles.reduce((mask, cycle, index) => cycle.edges.some((candidate) => candidate.id === edge.id) ? mask | (1 << index) : mask, 0));
      const target = syndrome.reduce((mask, bit, index) => bit ? mask | (1 << index) : mask, 0);
      const size = 1 << cycles.length;
      let distances = new Array(size).fill(Infinity);
      distances[0] = 0;
      edgeMasks.forEach((edgeMask) => {
        const next = distances.slice();
        for (let mask = 0; mask < size; mask += 1) {
          next[mask ^ edgeMask] = Math.min(next[mask ^ edgeMask], distances[mask] + 1);
        }
        distances = next;
      });
      return { mode: "exact", lower: distances[target], upper: distances[target], value: distances[target] };
    }
    const frustrated = cycles.filter((cycle) => cycle.sign < 0);
    const maximumCoverage = Math.max(...edges.map((edge) => frustrated.filter((cycle) => cycle.edges.some((candidate) => candidate.id === edge.id)).length), 1);
    return {
      mode: "bounds",
      lower: Math.ceil(frustrated.length / maximumCoverage),
      upper: frustrated.length,
      value: null
    };
  }

  function analyzeSpinLadder(points, moduleA, moduleB, lineageFloor, noiseRate) {
    const tau = finite(lineageFloor, "lineageFloor");
    const q = finite(noiseRate, "noiseRate");
    if (tau < 0 || tau > 1 || q < 0 || q > 1) throw new Error("tau and q must lie in [0, 1]");
    if (moduleA === moduleB) throw new Error("spin ladder requires two distinct modules");
    const byNode = new Map(points.map((point) => [`${point.moduleId}:${point.layer}`, point]));
    const layers = [...new Set(points.map((point) => point.layer))].sort((a, b) => a - b);
    const nodeIds = layers.flatMap((layer) => [`${moduleA}:${layer}`, `${moduleB}:${layer}`]);
    nodeIds.forEach((id) => { if (!byNode.has(id)) throw new Error(`missing ladder node ${id}`); });
    function makeEdge(id, a, b, edgeClass) {
      const retention = proxyRetention(byNode.get(a), byNode.get(b));
      return { id, a, b, edgeClass, retention, sign: hashUnit(`pixie-spin-v1:${id}`) < q ? -1 : 1 };
    }
    const edges = [];
    layers.forEach((layer, index) => {
      edges.push(makeEdge(`rung:${layer}`, `${moduleA}:${layer}`, `${moduleB}:${layer}`, "category"));
      if (index < layers.length - 1) {
        const next = layers[index + 1];
        edges.push(makeEdge(`rail:${moduleA}:${layer}`, `${moduleA}:${layer}`, `${moduleA}:${next}`, "depth"));
        edges.push(makeEdge(`rail:${moduleB}:${layer}`, `${moduleB}:${layer}`, `${moduleB}:${next}`, "depth"));
      }
    });
    const admitted = edges.filter((edge) => edge.retention >= tau);
    const parent = new Map(nodeIds.map((id) => [id, id]));
    function root(id) { while (parent.get(id) !== id) id = parent.get(id); return id; }
    admitted.forEach((edge) => {
      const first = root(edge.a);
      const second = root(edge.b);
      if (first !== second) parent.set(first, second);
    });
    const componentCount = new Set(nodeIds.map(root)).size;
    const basis = fundamentalCycles(nodeIds, admitted);
    const cycles = basis.map((cycle) => {
      const sign = cycle.edges.reduce((product, edge) => product * edge.sign, 1);
      const angleBudget = cycle.edges.reduce((sum, edge) => sum + Math.acos(Math.sqrt(edge.retention)), 0);
      const nodeSet = new Set(cycle.edges.flatMap((edge) => [edge.a, edge.b]));
      const members = [...nodeSet].map((id) => byNode.get(id));
      const center = members.reduce((value, point) => ({
        x: value.x + point.x / members.length,
        y: value.y + point.y / members.length,
        z: value.z + point.z / members.length,
        w: value.w + point.w / members.length
      }), { x: 0, y: 0, z: 0, w: 0 });
      const live = angleBudget >= Math.PI;
      const category = sign < 0 ? (live ? "frustrated_live" : "synthetic_negative_below_liveness") : (live ? "live_positive" : "forced_positive");
      const s = category === "frustrated_live" ? 1 : category === "synthetic_negative_below_liveness" ? 0.5 : category === "live_positive" ? -0.05 : -0.7;
      return { ...cycle, sign, angleBudget, frustrationMargin: Math.PI - angleBudget, live, category, center: { ...center, s } };
    });
    const negative = cycles.filter((cycle) => cycle.sign < 0);
    const gaugePhase = componentCount > 1 ? "disconnected" : negative.length ? "frustrated" : "coherent";
    let certificateCategory = componentCount > 1 ? "disconnected" : cycles.length === 0 ? "holonomy_unavailable" : cycles.some((cycle) => cycle.category === "synthetic_negative_below_liveness") ? "synthetic_sign_not_geometrically_live" : cycles.some((cycle) => cycle.category === "frustrated_live") ? "frustrated_live" : cycles.some((cycle) => cycle.category === "live_positive") ? "live_positive" : "forced_positive";
    const distance = distanceReceipt(cycles, admitted);
    return {
      moduleA, moduleB, lineageFloor: tau, noiseRate: q,
      nodeCount: nodeIds.length, admittedEdgeCount: admitted.length,
      componentCount, beta1: admitted.length - nodeIds.length + componentCount,
      gaugePhase, certificateCategory, w1Trivial: negative.length === 0,
      syndrome: cycles.map((cycle) => cycle.sign < 0 ? 1 : 0),
      cycles, distance
    };
  }

  return Object.freeze({ analyzeSpinLadder, buildPoints, projectPoint, rotate4D, rotate5D, rotate3D, sliceWeight, vectorNorm });
});
