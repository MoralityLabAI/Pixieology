(function (root, factory) {
  const value = factory(
    typeof module === "object" && module.exports ? require("./space.js") : root.GodelCharacterSpace
  );
  if (typeof module === "object" && module.exports) module.exports = value;
  root.GodelCharacterModel = value;
})(typeof globalThis !== "undefined" ? globalThis : this, function (space) {
  "use strict";

  if (!space) throw new Error("GodelCharacterSpace must load before the model");

  function clamp(value, low = 0, high = 1) {
    return Math.min(high, Math.max(low, Number(value)));
  }

  function clampTuple(tuple) {
    if (!Array.isArray(tuple) || tuple.length !== space.tupleOrder.length) {
      throw new Error(`Expected a ${space.tupleOrder.length}D character tuple`);
    }
    return tuple.map((value) => clamp(value));
  }

  function distance5D(left, right) {
    const a = clampTuple(left);
    const b = clampTuple(right);
    return Math.sqrt(a.reduce((sum, value, index) => sum + (value - b[index]) ** 2, 0));
  }

  function interpolateTuple(start, end, progress) {
    const a = clampTuple(start);
    const b = clampTuple(end);
    const t = clamp(progress);
    return a.map((value, index) => value + (b[index] - value) * t);
  }

  function project(tuple) {
    const point = clampTuple(tuple);
    return space.projection.matrix.map((row) =>
      row.reduce(
        (sum, coefficient, index) => sum + coefficient * (point[index] - space.projection.mean[index]),
        0
      )
    );
  }

  function project3D(tuple) {
    const projected = project(tuple);
    if (projected.length !== 3) throw new Error("The active character-space projection is not three-dimensional");
    return projected;
  }

  function findAnchor(id) {
    return space.anchors.find((anchor) => anchor.id === id) || null;
  }

  function nearestAnchors(tuple, count = 3) {
    return space.anchors
      .map((anchor) => ({ anchor, distance: distance5D(tuple, anchor.tuple) }))
      .sort((left, right) => left.distance - right.distance || left.anchor.id.localeCompare(right.anchor.id))
      .slice(0, Math.max(1, count));
  }

  function averageRanks(values) {
    const indexed = values.map((value, index) => ({ value, index })).sort((a, b) => a.value - b.value);
    const ranks = new Array(values.length);
    let cursor = 0;
    while (cursor < indexed.length) {
      let end = cursor + 1;
      while (end < indexed.length && indexed[end].value === indexed[cursor].value) end += 1;
      const rank = (cursor + end - 1) / 2;
      for (let index = cursor; index < end; index += 1) ranks[indexed[index].index] = rank;
      cursor = end;
    }
    return ranks;
  }

  function pearson(left, right) {
    const meanLeft = left.reduce((sum, value) => sum + value, 0) / left.length;
    const meanRight = right.reduce((sum, value) => sum + value, 0) / right.length;
    let numerator = 0;
    let leftScale = 0;
    let rightScale = 0;
    for (let index = 0; index < left.length; index += 1) {
      const a = left[index] - meanLeft;
      const b = right[index] - meanRight;
      numerator += a * b;
      leftScale += a * a;
      rightScale += b * b;
    }
    return numerator / Math.sqrt(leftScale * rightScale);
  }

  function projectionStats() {
    const distances5D = [];
    const distancesProjected = [];
    for (let left = 0; left < space.anchors.length; left += 1) {
      for (let right = left + 1; right < space.anchors.length; right += 1) {
        distances5D.push(distance5D(space.anchors[left].tuple, space.anchors[right].tuple));
        const a = project3D(space.anchors[left].tuple);
        const b = project3D(space.anchors[right].tuple);
        distancesProjected.push(Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]));
      }
    }
    const stressNumerator = distances5D.reduce(
      (sum, value, index) => sum + (value - distancesProjected[index]) ** 2,
      0
    );
    const stressDenominator = distances5D.reduce((sum, value) => sum + value ** 2, 0);
    return {
      pairs: distances5D.length,
      pearsonDistanceCorrelation: pearson(distances5D, distancesProjected),
      spearmanDistanceCorrelation: pearson(averageRanks(distances5D), averageRanks(distancesProjected)),
      normalizedStress: Math.sqrt(stressNumerator / stressDenominator),
      fittedExplainedVariance: space.projection.fittedExplainedVariance
    };
  }

  function tupleLabel(tuple) {
    return clampTuple(tuple)
      .map((value) => Math.round(value * 100).toString().padStart(2, "0"))
      .join(" · ");
  }

  function characterState(tuple) {
    const normalized = clampTuple(tuple);
    const nearest = nearestAnchors(normalized, 1)[0];
    const projected = project(normalized);
    return {
      schema: "pixieology_character_state_v2",
      schema_version: 2,
      space_id: space.experimentId,
      tuple_order: space.tupleOrder.slice(),
      tuple: normalized,
      values: Object.fromEntries(space.tupleOrder.map((id, index) => [id, normalized[index]])),
      anchor_id: nearest.distance < 0.012 ? nearest.anchor.id : null,
      nearest_anchor: {
        id: nearest.anchor.id,
        distance: Number(nearest.distance.toFixed(12))
      },
      projection: {
        method: space.projection.method,
        x: projected[0],
        y: projected[1],
        z: projected[2],
        semantic_claim: "navigation_only"
      }
    };
  }

  return Object.freeze({
    space,
    clamp,
    clampTuple,
    distance5D,
    interpolateTuple,
    project,
    project3D,
    findAnchor,
    nearestAnchors,
    projectionStats,
    tupleLabel,
    characterState
  });
});
