import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const runtime = require("../space.js");
const contract = JSON.parse(fs.readFileSync(path.join(folder, "character_space_v1.json"), "utf8"));

test("the portable game contract is explicitly experimental", () => {
  assert.equal(contract.schema, "pixieology_character_space_v1");
  assert.equal(contract.status, "experimental");
  assert.equal(contract.canonical, false);
  assert.equal(contract.projection.semantic_claim, "navigation_only");
});

test("the portable game contract matches the browser runtime exactly", () => {
  assert.equal(contract.experiment_id, runtime.experimentId);
  assert.deepEqual(contract.tuple_order, runtime.tupleOrder);
  assert.deepEqual(contract.dimensions, runtime.dimensions);
  assert.deepEqual(contract.anchors, runtime.anchors);
  assert.equal(contract.projection.method, runtime.projection.method);
  assert.deepEqual(contract.projection.mean, runtime.projection.mean);
  assert.deepEqual(contract.projection.matrix, runtime.projection.matrix);
  assert.equal(contract.projection.fitted_explained_variance, runtime.projection.fittedExplainedVariance);
  assert.deepEqual(contract.ontology_boundary.restricted_anchor_terms, runtime.ontologyBoundary.restrictedAnchorTerms);
});

test("game consumers cannot mistake lore or capability for a trait axis", () => {
  assert.deepEqual(contract.ontology_boundary.excluded_axes, [
    "model_parameter_count",
    "capability_class",
    "theological_entity_class"
  ]);
  assert.equal(contract.ontology_boundary.parameter_count_is_not_character, true);
});
