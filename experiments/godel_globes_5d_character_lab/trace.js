(function (root, factory) {
  const value = factory(
    typeof module === "object" && module.exports ? require("./space.js") : root.GodelCharacterSpace
  );
  if (typeof module === "object" && module.exports) module.exports = value;
  root.GodelManifoldTrace = value;
})(typeof globalThis !== "undefined" ? globalThis : this, function (space) {
  "use strict";

  const schema = "pixieology_manifold_trace_v1";
  const semanticKinds = new Set(["character_tuple", "mechanistic_normalized"]);
  const alignmentStatuses = new Set(["authored", "calibrated", "uncalibrated"]);

  function finiteNumber(value, label) {
    const number = Number(value);
    if (!Number.isFinite(number)) throw new Error(`${label} must be a finite number`);
    return number;
  }

  function normalizedVector(values, label) {
    if (!Array.isArray(values) || values.length !== 5) throw new Error(`${label} must contain exactly five values`);
    return values.map((value, index) => {
      const number = finiteNumber(value, `${label}[${index}]`);
      if (number < 0 || number > 1) throw new Error(`${label}[${index}] must be between 0 and 1`);
      return number;
    });
  }

  function normalizeAxis(axis, index) {
    if (!axis || typeof axis !== "object") throw new Error(`axes[${index}] must be an object`);
    const id = String(axis.id || "").trim();
    const label = String(axis.label || "").trim();
    if (!id || !label) throw new Error(`axes[${index}] requires id and label`);
    const rawRange = axis.raw_range == null
      ? null
      : axis.raw_range.map((value, rangeIndex) => finiteNumber(value, `axes[${index}].raw_range[${rangeIndex}]`));
    if (rawRange && rawRange.length !== 2) throw new Error(`axes[${index}].raw_range must contain two values`);
    return Object.freeze({
      ...axis,
      id,
      label,
      unit: String(axis.unit || "normalized"),
      ...(rawRange ? { raw_range: Object.freeze(rawRange) } : {})
    });
  }

  function normalizeFrame(frame, index, previousTime) {
    if (!frame || typeof frame !== "object") throw new Error(`frames[${index}] must be an object`);
    const t = finiteNumber(frame.t ?? index, `frames[${index}].t`);
    if (t < previousTime) throw new Error("frame time must be monotonic");
    const values = normalizedVector(frame.values ?? frame.tuple, `frames[${index}].values`);
    const raw = frame.raw == null
      ? null
      : frame.raw.map((value, rawIndex) => finiteNumber(value, `frames[${index}].raw[${rawIndex}]`));
    return Object.freeze({
      t,
      values: Object.freeze(values),
      raw: raw ? Object.freeze(raw) : null,
      label: String(frame.label ?? `Step ${index}`),
      metadata: Object.freeze({ ...(frame.metadata || {}) })
    });
  }

  function normalizeTrace(input) {
    if (!input || typeof input !== "object" || Array.isArray(input)) throw new Error("trace must be an object");
    if (input.schema !== schema) throw new Error(`trace schema must be ${schema}`);
    const semantics = String(input.semantics || "");
    if (!semanticKinds.has(semantics)) throw new Error(`unsupported trace semantics: ${semantics}`);
    const alignmentStatus = String(input.alignment?.status || "uncalibrated");
    if (!alignmentStatuses.has(alignmentStatus)) throw new Error(`unsupported alignment status: ${alignmentStatus}`);
    if (!Array.isArray(input.axes) || input.axes.length !== 5) throw new Error("trace requires exactly five axes");
    if (!Array.isArray(input.frames) || input.frames.length < 2) throw new Error("trace requires at least two frames");
    let previousTime = -Infinity;
    const frames = input.frames.map((frame, index) => {
      const normalized = normalizeFrame(frame, index, previousTime);
      previousTime = normalized.t;
      return normalized;
    });
    const syncsToCharacter = semantics === "character_tuple" && alignmentStatus !== "uncalibrated";
    return Object.freeze({
      schema,
      id: String(input.id || "unnamed-trace"),
      title: String(input.title || "Untitled trace"),
      semantics,
      axes: Object.freeze(input.axes.map(normalizeAxis)),
      alignment: Object.freeze({
        status: alignmentStatus,
        character_semantics: syncsToCharacter,
        note: String(input.alignment?.note || "")
      }),
      source: Object.freeze({ ...(input.source || {}) }),
      time: Object.freeze({ unit: String(input.time?.unit || "step") }),
      frames: Object.freeze(frames),
      syncsToCharacter
    });
  }

  function authoredTrace() {
    const order = [
      "seedling", "lantern-scout", "sky-cartographer", "storm-warden", "moon-archivist",
      "root-scholar", "hearthkeeper", "river-mediator", "meadow-friend", "moss-companion",
      "hedge-trickster", "ember-rogue", "seedling"
    ];
    const anchors = new Map(space.anchors.map((anchor) => [anchor.id, anchor]));
    return normalizeTrace({
      schema,
      id: "authored-character-orbit-v1",
      title: "Authored character orbit",
      semantics: "character_tuple",
      axes: space.dimensions.map((dimension) => ({ id: dimension.id, label: dimension.label, unit: "normalized" })),
      alignment: {
        status: "authored",
        note: "Authored retail character coordinates; this is not a model-internals measurement."
      },
      source: { evidence_class: "authored_demo" },
      time: { unit: "scene" },
      frames: order.map((id, index) => ({
        t: index,
        values: anchors.get(id).tuple,
        label: anchors.get(id).name,
        metadata: { anchor_id: id }
      }))
    });
  }

  function parseText(text) {
    const source = String(text || "").trim();
    if (!source) throw new Error("trace file is empty");
    let decoded;
    try {
      decoded = JSON.parse(source);
    } catch (error) {
      if (!source.includes("\n")) throw error;
    }
    if (decoded !== undefined) return normalizeTrace(decoded);
    const rows = source.split(/\r?\n/).filter((line) => line.trim()).map((line) => JSON.parse(line));
    return normalizeTrace({
      schema,
      id: "imported-jsonl-trace",
      title: "Imported JSONL trace",
      semantics: "character_tuple",
      axes: space.dimensions.map((dimension) => ({ id: dimension.id, label: dimension.label })),
      alignment: {
        status: "uncalibrated",
        note: "JSONL imports remain uncalibrated until their character-axis mapping is certified."
      },
      frames: rows.map((row, index) => ({
        t: row.t ?? index,
        values: row.values ?? row.tuple,
        label: row.label ?? `Step ${index}`,
        metadata: row.metadata || {}
      }))
    });
  }

  function interpolate(trace, cursor) {
    const normalized = normalizeTrace(trace);
    const maximum = normalized.frames.length - 1;
    const clamped = Math.max(0, Math.min(maximum, finiteNumber(cursor, "cursor")));
    const leftIndex = Math.floor(clamped);
    const rightIndex = Math.min(maximum, leftIndex + 1);
    const mix = clamped - leftIndex;
    const left = normalized.frames[leftIndex];
    const right = normalized.frames[rightIndex];
    return {
      index: leftIndex,
      progress: mix,
      values: left.values.map((value, index) => value + (right.values[index] - value) * mix),
      label: mix < 0.5 ? left.label : right.label,
      t: left.t + (right.t - left.t) * mix,
      metadata: mix < 0.5 ? left.metadata : right.metadata
    };
  }

  return Object.freeze({ schema, normalizeTrace, authoredTrace, parseText, interpolate });
});
