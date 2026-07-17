import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const traceApi = require("../trace.js");
const vpdData = require("../vpd_trace_data.js");
const bonsaiData = require("../bonsai_vpd_trace_data.js");

test("the authored orbit is a character-synchronized five-dimensional time trace", () => {
  const trace = traceApi.authoredTrace();
  assert.equal(trace.schema, traceApi.schema);
  assert.equal(trace.axes.length, 5);
  assert.equal(trace.semantics, "character_tuple");
  assert.equal(trace.alignment.status, "authored");
  assert.equal(trace.syncsToCharacter, true);
  assert.equal(trace.frames[0].label, "Seedling");
  assert.equal(trace.frames.at(-1).label, "Seedling");
});

test("the bundled HRM trace contains actual measurements without inventing trait alignment", () => {
  const trace = traceApi.normalizeTrace(vpdData);
  assert.equal(trace.id, "hrm-text-1b-vpd-depth-trace-v1");
  assert.equal(trace.source.evidence_class, "actual_local_vpd_style_analysis");
  assert.equal(trace.source.model_id, "HRM-Text-1B");
  assert.equal(trace.source.summary_sha256, "257dfdeff84aa93403228192151d6b23310b6236421ff2464cbb970d5e951000");
  assert.equal(trace.frames.length, 16);
  assert.equal(trace.semantics, "mechanistic_normalized");
  assert.equal(trace.alignment.status, "uncalibrated");
  assert.equal(trace.syncsToCharacter, false);
  assert.ok(trace.frames.every((frame) => frame.values.every((value) => value >= 0 && value <= 1)));
  assert.ok(trace.frames.every((frame) => frame.raw?.length === 5));
});

test("the Bonsai trace contains hashed adapter deltas without claiming activation or trait evidence", () => {
  const trace = traceApi.normalizeTrace(bonsaiData);
  assert.equal(trace.id, "bonsai-1p7b-lora-delta-depth-trace-v1");
  assert.equal(trace.source.evidence_class, "actual_bonsai_1p7b_lora_delta_decomposition");
  assert.equal(trace.source.model_id, "prism-ml/Bonsai-1.7B-unpacked");
  assert.equal(trace.source.adapter_sha256, "8c2d6f805cf58c60a369a93f23894282384ba02b9d56a7efb8bdaac31b8b888c");
  assert.equal(trace.source.base_model_loaded, false);
  assert.equal(trace.source.activation_analysis, false);
  assert.equal(trace.frames.length, 28);
  assert.equal(trace.alignment.status, "uncalibrated");
  assert.equal(trace.syncsToCharacter, false);
  assert.ok(trace.frames.every((frame) => frame.raw?.length === 5));
});

test("time interpolation is deterministic and bounded", () => {
  const trace = traceApi.authoredTrace();
  const first = traceApi.interpolate(trace, 0.5);
  const again = traceApi.interpolate(trace, 0.5);
  assert.deepEqual(first, again);
  first.values.forEach((value) => assert.ok(value >= 0 && value <= 1));
  assert.deepEqual(traceApi.interpolate(trace, -10).values, trace.frames[0].values);
  assert.deepEqual(traceApi.interpolate(trace, 100).values, trace.frames.at(-1).values);
});

test("invalid and uncalibrated imports fail closed", () => {
  assert.throws(() => traceApi.parseText(""), /empty/);
  assert.throws(() => traceApi.normalizeTrace({ schema: traceApi.schema }), /semantics/);
  const jsonl = [
    JSON.stringify({ tuple: [0, 0, 0, 0, 0] }),
    JSON.stringify({ tuple: [1, 1, 1, 1, 1] })
  ].join("\n");
  const imported = traceApi.parseText(jsonl);
  assert.equal(imported.alignment.status, "uncalibrated");
  assert.equal(imported.syncsToCharacter, false);
});
