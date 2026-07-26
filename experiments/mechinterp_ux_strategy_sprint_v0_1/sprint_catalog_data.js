(function (root, factory) {
  const value = factory();
  if (typeof module === "object" && module.exports) module.exports = value;
  root.PixieEtaleMotifCatalogData = value;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const moduleIds = Object.freeze([
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj"
  ]);

  const far = Object.freeze([
    [-0.72, -0.45, 0.10],
    [0.08, 0.72, -0.52],
    [0.68, -0.62, 0.42],
    [-0.88, -0.88, -0.82],
    [0.88, -0.84, 0.82],
    [-0.84, 0.88, 0.84],
    [0.86, 0.84, -0.86]
  ]);

  function cloneCoordinate(value, layer, moduleIndex) {
    return [
      value[0] + Math.sin((layer + moduleIndex) * 0.37) * 0.008,
      value[1] + Math.cos((layer * 0.29) + moduleIndex) * 0.008,
      value[2] + Math.sin((layer * 0.19) - moduleIndex) * 0.006
    ];
  }

  function buildCoordinates(kind, options) {
    const center = options.center;
    const start = options.start;
    const end = options.end;
    return Object.freeze(Array.from({ length: 28 }, (_, layer) => {
      const stalk = far.map((coordinate, moduleIndex) => cloneCoordinate(coordinate, layer, moduleIndex));
      const insideWindow = Math.abs(layer - center) <= 3;
      if (kind === "chain" && insideWindow) {
        stalk[0] = [-0.20, 0, 0];
        stalk[1] = [0, 0, 0];
        stalk[2] = [0.20, 0, 0];
      } else if (kind === "robust" && insideWindow) {
        stalk[0] = [-0.08, 0, 0];
        stalk[1] = [0.02, 0.04, 0];
        stalk[2] = [0.08, -0.02, 0.02];
      } else if (kind === "band" && layer >= start && layer <= end) {
        stalk[0] = [-0.06, 0.04, 0];
        stalk[1] = [0.06, -0.02, 0.02];
      }
      return Object.freeze(stalk.map((coordinate) => Object.freeze(coordinate)));
    }));
  }

  function makeCase(caseId, archetype, options) {
    return Object.freeze({
      schema: "pixieology_mechinterp_ux_case_v1",
      case_id: caseId,
      archetype,
      title: options.title,
      evidence_class: "synthetic_ux_fixture",
      coordinate_source: "synthetic_ux_fixture",
      module_ids: moduleIds,
      coordinates: buildCoordinates(archetype, options),
      motif_ids: Object.freeze([]),
      outcome_eligible: false,
      recommended_next_investigation: null,
      claim_boundary: "Synthetic UX fixture only. It is not model, motif, causal, intervention, or human evidence."
    });
  }

  const cases = Object.freeze([
    makeCase("ux-band-a", "band", { title: "Band onset A", center: 8, start: 6, end: 12 }),
    makeCase("ux-band-b", "band", { title: "Band onset B", center: 19, start: 16, end: 22 }),
    makeCase("ux-chain-a", "chain", { title: "Chained closure A", center: 8 }),
    makeCase("ux-chain-b", "chain", { title: "Chained closure B", center: 19 }),
    makeCase("ux-robust-a", "robust", { title: "Bridge-free convergence A", center: 9 }),
    makeCase("ux-robust-b", "robust", { title: "Bridge-free convergence B", center: 20 }),
    makeCase("ux-null-a", "null", { title: "No eligible motif job A", center: 7 }),
    makeCase("ux-null-b", "null", { title: "No eligible motif job B", center: 21 })
  ]);

  return Object.freeze({
    schema: "pixieology_etale_motif_catalog_v1",
    status: "UX_FIXTURES_ONLY",
    protocol_sha256: null,
    scaler_sha256: null,
    evidence_provenance: "synthetic_ux_fixture",
    motif_count: 0,
    case_count: cases.length,
    motifs: Object.freeze([]),
    cases,
    human_evidence: Object.freeze({
      craft_study: "NOT_RUN",
      learning_study: "NOT_RUN",
      synthetic_agent_smoke_is_human_evidence: false
    }),
    claim_boundary: "These deterministic cases test UX mechanics only and cannot mint a motif or authorize a job."
  });
});
