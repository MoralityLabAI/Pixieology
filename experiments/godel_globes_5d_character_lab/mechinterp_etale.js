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

  function localDistance(chart, moduleA, moduleB) {
    if (!chart || !Array.isArray(chart.sheets)) throw new Error("chart requires local sheets");
    const first = chart.sheets.find((sheet) => sheet.moduleId === moduleA);
    const second = chart.sheets.find((sheet) => sheet.moduleId === moduleB);
    if (!first || !second) throw new Error(`unknown local sheet pair ${moduleA}:${moduleB}`);
    if (first.points.length !== second.points.length || first.points.length === 0) throw new Error("local sheets must share samples");
    let squared = 0;
    first.points.forEach((point, index) => {
      const peer = second.points[index];
      if (point.layer !== peer.layer) throw new Error("local sheets must share the same base coordinates");
      squared += Math.pow(finite(point.x, "x") - finite(peer.x, "x"), 2);
      squared += Math.pow(finite(point.y, "y") - finite(peer.y, "y"), 2);
      squared += Math.pow(finite(point.z, "z") - finite(peer.z, "z"), 2);
    });
    return Math.sqrt(squared / (first.points.length * 3));
  }

  function buildDistanceCache(map, radius = 2) {
    if (!map || !Array.isArray(map.layers) || !Array.isArray(map.sheets)) throw new Error("invalid étale map");
    const span = Math.max(1, Math.floor(finite(radius, "radius")));
    const pairPrefixes = new Map();
    for (let first = 0; first < map.moduleIds.length; first += 1) {
      for (let second = first + 1; second < map.moduleIds.length; second += 1) {
        const a = map.moduleIds[first];
        const b = map.moduleIds[second];
        const prefix = [0];
        map.layers.forEach((layer) => {
          const left = germAt(map, a, layer);
          const right = germAt(map, b, layer);
          const squared = Math.pow(finite(left.x, "x") - finite(right.x, "x"), 2) +
            Math.pow(finite(left.y, "y") - finite(right.y, "y"), 2) +
            Math.pow(finite(left.z, "z") - finite(right.z, "z"), 2);
          prefix.push(prefix[prefix.length - 1] + squared);
        });
        pairPrefixes.set(`${a}|${b}`, Object.freeze(prefix));
      }
    }
    const samples = new Map();
    map.layers.forEach((layer, center) => {
      const lower = Math.max(0, center - span);
      const upper = Math.min(map.layers.length - 1, center + span);
      const count = upper - lower + 1;
      const distances = new Map();
      pairPrefixes.forEach((prefix, id) => {
        distances.set(id, Math.sqrt(Math.max(0, prefix[upper + 1] - prefix[lower]) / (count * 3)));
      });
      samples.set(layer, Object.freeze({
        layer,
        lowerLayer: map.layers[lower],
        upperLayer: map.layers[upper],
        sampleCount: count,
        distances
      }));
    });
    return Object.freeze({
      radius: span,
      method: "global_normalization_prefix_squared_difference_v1",
      windowDependentNormalization: false,
      pairPrefixes,
      samples
    });
  }

  function connectedComponents(moduleIds, equivalences) {
    const parent = new Map(moduleIds.map((id) => [id, id]));
    function root(id) {
      let value = id;
      while (parent.get(value) !== value) value = parent.get(value);
      while (parent.get(id) !== id) {
        const next = parent.get(id);
        parent.set(id, value);
        id = next;
      }
      return value;
    }
    equivalences.forEach((pair) => {
      const first = root(pair.a);
      const second = root(pair.b);
      if (first !== second) parent.set(first, second);
    });
    const groups = new Map();
    moduleIds.forEach((id) => {
      const key = root(id);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(id);
    });
    return [...groups.values()].map((group) => Object.freeze(group));
  }

  function tarjanDiagnostics(nodes, equivalences) {
    const adjacency = new Map(nodes.map((id) => [id, new Set()]));
    equivalences.forEach((pair) => {
      adjacency.get(pair.a).add(pair.b);
      adjacency.get(pair.b).add(pair.a);
    });
    const discovery = new Map();
    const low = new Map();
    const parent = new Map();
    const bridges = [];
    const articulations = new Set();
    let clock = 0;
    function visit(node) {
      clock += 1;
      discovery.set(node, clock);
      low.set(node, clock);
      let children = 0;
      [...adjacency.get(node)].sort().forEach((neighbor) => {
        if (!discovery.has(neighbor)) {
          parent.set(neighbor, node);
          children += 1;
          visit(neighbor);
          low.set(node, Math.min(low.get(node), low.get(neighbor)));
          if (low.get(neighbor) > discovery.get(node)) bridges.push([node, neighbor].sort().join("|"));
          if (!parent.has(node) && children > 1) articulations.add(node);
          if (parent.has(node) && low.get(neighbor) >= discovery.get(node)) articulations.add(node);
        } else if (neighbor !== parent.get(node)) {
          low.set(node, Math.min(low.get(node), discovery.get(neighbor)));
        }
      });
    }
    [...nodes].sort().forEach((node) => {
      if (!discovery.has(node)) visit(node);
    });
    return Object.freeze({
      bridges: Object.freeze([...new Set(bridges)].sort()),
      articulationVertices: Object.freeze([...articulations].sort()),
      bridgeStatus: bridges.length ? "present" : "none",
      twoEdgeConnected: nodes.length > 1 && bridges.length === 0
    });
  }

  function componentDiagnostics(components, equivalences, pairs, tolerance) {
    const pairById = new Map(pairs.map((pair) => [pair.id, pair]));
    return components.map((members) => {
      const possible = [];
      for (let first = 0; first < members.length; first += 1) {
        for (let second = first + 1; second < members.length; second += 1) {
          const forward = `${members[first]}|${members[second]}`;
          const reverse = `${members[second]}|${members[first]}`;
          possible.push(pairById.get(forward) || pairById.get(reverse));
        }
      }
      const direct = equivalences.filter((pair) => members.includes(pair.a) && members.includes(pair.b));
      const maximumDistance = possible.length ? Math.max(...possible.map((pair) => pair.distance)) : 0;
      return Object.freeze({
        members,
        clique: direct.length === possible.length,
        chainExcess: Math.max(0, maximumDistance - tolerance),
        maximumPairDistance: maximumDistance,
        directEdgeIds: Object.freeze(direct.map((pair) => pair.id)),
        ...tarjanDiagnostics(members, direct)
      });
    });
  }

  function dendrogramMst(moduleIds, pairs) {
    const parent = new Map(moduleIds.map((id) => [id, id]));
    function root(id) {
      while (parent.get(id) !== id) {
        parent.set(id, parent.get(parent.get(id)));
        id = parent.get(id);
      }
      return id;
    }
    const edges = [];
    [...pairs].sort((left, right) => left.distance - right.distance || left.id.localeCompare(right.id)).forEach((pair) => {
      const left = root(pair.a);
      const right = root(pair.b);
      if (left === right) return;
      parent.set(left, right);
      edges.push(Object.freeze({
        id: pair.id,
        a: pair.a,
        b: pair.b,
        birthEpsilon: pair.distance
      }));
    });
    return Object.freeze(edges);
  }

  function localEquivalences(map, layer, radius, tolerance, distanceCache = null) {
    const epsilon = finite(tolerance, "tolerance");
    if (epsilon < 0) throw new Error("tolerance must be non-negative");
    const chart = chartAt(map, layer, radius);
    if (distanceCache && distanceCache.radius !== chart.radius) throw new Error("distance cache radius differs from chart");
    const cached = distanceCache ? distanceCache.samples.get(chart.layer) : null;
    const pairs = [];
    for (let first = 0; first < map.moduleIds.length; first += 1) {
      for (let second = first + 1; second < map.moduleIds.length; second += 1) {
        const a = map.moduleIds[first];
        const b = map.moduleIds[second];
        const distance = cached ? cached.distances.get(`${a}|${b}`) : localDistance(chart, a, b);
        pairs.push(Object.freeze({
          id: `${a}|${b}`,
          a,
          b,
          distance,
          equivalent: distance <= epsilon
        }));
      }
    }
    const equivalences = Object.freeze(pairs.filter((pair) => pair.equivalent));
    const components = Object.freeze(connectedComponents(map.moduleIds, equivalences));
    return Object.freeze({
      layer: chart.layer,
      radius: chart.radius,
      tolerance: epsilon,
      chart,
      pairs: Object.freeze(pairs),
      equivalences,
      components,
      componentDiagnostics: Object.freeze(componentDiagnostics(components, equivalences, pairs, epsilon)),
      dendrogramMst: dendrogramMst(map.moduleIds, pairs)
    });
  }

  function buildGluingAtlas(map, radius, tolerance) {
    const distanceCache = buildDistanceCache(map, radius);
    const samples = Object.freeze(map.layers.map((layer) => localEquivalences(map, layer, radius, tolerance, distanceCache)));
    const pairIds = samples[0].pairs.map((pair) => pair.id);
    const bands = [];
    pairIds.forEach((pairId) => {
      let start = null;
      let members = [];
      samples.forEach((sample, index) => {
        const pair = sample.pairs.find((candidate) => candidate.id === pairId);
        if (pair.equivalent) {
          if (start === null) start = index;
          members.push(pair);
        }
        if (start !== null && (!pair.equivalent || index === samples.length - 1)) {
          const end = pair.equivalent && index === samples.length - 1 ? index : index - 1;
          const [a, b] = pairId.split("|");
          bands.push(Object.freeze({
            id: `${pairId}:${samples[start].layer}-${samples[end].layer}`,
            a,
            b,
            startLayer: samples[start].layer,
            endLayer: samples[end].layer,
            minDistance: Math.min(...members.map((member) => member.distance)),
            maxDistance: Math.max(...members.map((member) => member.distance))
          }));
          start = null;
          members = [];
        }
      });
    });
    const transitions = [];
    for (let index = 1; index < samples.length; index += 1) {
      const previous = samples[index - 1];
      const current = samples[index];
      const before = new Set(previous.equivalences.map((pair) => pair.id));
      const after = new Set(current.equivalences.map((pair) => pair.id));
      const added = [...after].filter((id) => !before.has(id));
      const removed = [...before].filter((id) => !after.has(id));
      if (!added.length && !removed.length) continue;
      const kind = current.components.length < previous.components.length ? "merge" :
        current.components.length > previous.components.length ? "split" :
          added.length && removed.length ? "rewire" : added.length ? "reinforce" : "relax";
      transitions.push(Object.freeze({
        layer: current.layer,
        kind,
        added: Object.freeze(added),
        removed: Object.freeze(removed),
        componentCountBefore: previous.components.length,
        componentCountAfter: current.components.length
      }));
    }
    return Object.freeze({
      radius: samples[0].radius,
      tolerance: samples[0].tolerance,
      samples,
      bands: Object.freeze(bands),
      transitions: Object.freeze(transitions),
      hasNontrivialGluing: bands.length > 0,
      metric: Object.freeze({
        id: "normalized_xyz_rms_v1",
        coordinates: Object.freeze(["x", "y", "z"]),
        normalization: Object.freeze({
          x: "per_module_full_depth_minmax_to_minus1_plus1",
          y: "global_all_module_layer_minmax_to_minus1_plus1",
          z: "global_all_module_layer_minmax_to_minus1_plus1",
          windowDependent: false
        }),
        uncertainty: "not_available_in_source_atlas"
      }),
      distanceCache: Object.freeze({
        method: distanceCache.method,
        radius: distanceCache.radius,
        windowDependentNormalization: distanceCache.windowDependentNormalization
      }),
      monodromy: Object.freeze({
        available: false,
        reason: "ordered depth W is an interval with no closed base path"
      })
    });
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

  return Object.freeze({
    buildMap,
    chartAt,
    sheetAt,
    germAt,
    localDistance,
    buildDistanceCache,
    localEquivalences,
    buildGluingAtlas,
    tarjanDiagnostics,
    dendrogramMst,
    overlapCycles,
    nearestCycle
  });
});
