(function () {
  "use strict";

  const api = window.PixieEtaleExplorer;
  const query = new URLSearchParams(window.location.search);
  const variants = {
    orientation: query.get("orientation") || "heatmap",
    threshold: query.get("threshold") || "dendrogram_births",
    language: query.get("language") || "dual",
    jobs: query.get("jobs") || "gated"
  };
  const heatmap = document.getElementById("orientation-heatmap");
  const globe = document.getElementById("orientation-globe");
  const globeMarks = document.getElementById("orientation-globe-marks");
  const caseFirst = document.getElementById("orientation-case-first");
  const births = document.getElementById("dendrogram-births");
  const thresholdSection = document.getElementById("triage-threshold");
  const epsilonInput = document.getElementById("etale-epsilon");
  const jobs = document.getElementById("triage-jobs");
  const reviewed = document.getElementById("mark-evidence-reviewed");
  let latest = null;

  function words(value) {
    return String(value || "").replaceAll("_", " ");
  }

  function configureVariants() {
    heatmap.hidden = variants.orientation !== "heatmap";
    globe.hidden = variants.orientation !== "globe";
    caseFirst.hidden = variants.orientation !== "case_first";
    thresholdSection.hidden = variants.threshold === "slider";
    document.getElementById("advanced-controls").open = variants.threshold === "slider";
    document.body.classList.toggle("technical-language", variants.language === "technical");
    jobs.hidden = variants.jobs !== "inline";
    reviewed.hidden = variants.jobs === "inline";
  }

  function renderOrientation(analysis) {
    heatmap.replaceChildren();
    analysis.overview.layers.forEach((entry) => {
      const mark = document.createElement("button");
      mark.type = "button";
      mark.className = `orientation-layer${entry.direct_edge_count ? " has-edges" : ""}${entry.layer === analysis.state.layer ? " selected" : ""}`;
      mark.style.height = `${Math.max(8, 8 + entry.direct_edge_count * 6)}px`;
      mark.dataset.layer = String(entry.layer);
      mark.setAttribute("aria-label", `Layer ${entry.layer}: ${entry.direct_edge_count} direct edges, ${entry.component_count} closure components`);
      mark.addEventListener("click", () => api.setState({ layer: entry.layer }));
      heatmap.appendChild(mark);
    });
  }

  function renderBirths(analysis) {
    births.replaceChildren();
    analysis.topology.dendrogram_mst.forEach((edge) => {
      const button = document.createElement("button");
      const cut = Math.max(0.10, Math.min(0.60, edge.birthEpsilon + 0.000001));
      button.type = "button";
      button.textContent = `${edge.a.replace("_proj", "")}–${edge.b.replace("_proj", "")} · ${edge.birthEpsilon.toFixed(3)}`;
      button.setAttribute("aria-pressed", String(Math.abs(analysis.state.glue_tolerance - cut) < 0.006));
      button.setAttribute("aria-label", `Cut epsilon at ${edge.birthEpsilon.toFixed(3)} to include ${edge.a} and ${edge.b}`);
      button.addEventListener("click", () => api.setState({ glue_tolerance: cut }));
      births.appendChild(button);
    });
  }

  function renderGlobe(analysis) {
    globeMarks.replaceChildren();
    const selectedCase = api.getMotifCatalog().cases.find(
      (item) => item.case_id === analysis.state.case_id
    );
    if (!selectedCase || !Array.isArray(selectedCase.coordinates)) return;
    const namespace = "http://www.w3.org/2000/svg";
    selectedCase.module_ids.forEach((moduleId, moduleIndex) => {
      const points = selectedCase.coordinates.map((stalk, layer) => {
        const [x, y, z] = stalk[moduleIndex];
        const depth = layer / Math.max(1, selectedCase.coordinates.length - 1);
        return {
          layer,
          x: 320 + (x * 145) + (z * 42) + ((depth - 0.5) * 92),
          y: 130 - (y * 82) + (z * 30) + (Math.sin(depth * Math.PI * 2) * 13)
        };
      });
      const path = document.createElementNS(namespace, "path");
      path.setAttribute("class", moduleId === analysis.state.module_id
        ? "orientation-globe-sheet selected"
        : "orientation-globe-sheet");
      path.setAttribute("d", points.map((point, index) => (
        `${index ? "L" : "M"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`
      )).join(" "));
      const title = document.createElementNS(namespace, "title");
      title.textContent = `${moduleId} across depth W`;
      path.appendChild(title);
      globeMarks.appendChild(path);
      points.forEach((point) => {
        if (point.layer % 3 !== 0 && point.layer !== analysis.state.layer) return;
        const mark = document.createElementNS(namespace, "circle");
        mark.setAttribute("class", point.layer === analysis.state.layer
          ? "orientation-globe-point selected"
          : "orientation-globe-point");
        mark.setAttribute("cx", point.x.toFixed(2));
        mark.setAttribute("cy", point.y.toFixed(2));
        mark.setAttribute("r", point.layer === analysis.state.layer ? "4" : "2");
        const markTitle = document.createElementNS(namespace, "title");
        markTitle.textContent = `${moduleId}, layer ${point.layer}`;
        mark.appendChild(markTitle);
        globeMarks.appendChild(mark);
      });
    });
  }

  function renderEvidence(analysis) {
    const component = analysis.topology.selected_component;
    const direct = analysis.direct_glued_partners.map((item) => item.label).join(", ") || "none";
    const closure = analysis.closure_component.map((item) => item.label).join(", ");
    const robustness = component.bridgeStatus === "none"
      ? `bridge: none · chain excess ${component.chainExcess.toFixed(3)}`
      : `${component.bridges.length} bridge${component.bridges.length === 1 ? "" : "s"} · chain excess ${component.chainExcess.toFixed(3)}`;
    document.getElementById("triage-epsilon-display").textContent = analysis.state.glue_tolerance.toFixed(3);
    document.getElementById("triage-closure").textContent = closure;
    document.getElementById("triage-robustness-value").textContent = robustness;
    document.getElementById("triage-evidence-summary").textContent =
      `Direct: ${direct}. Closure: ${closure}. ${robustness}. S: ${analysis.spin.available ? words(analysis.spin.certificate_category) : "unavailable"}.`;
    document.getElementById("triage-evidence-badge").textContent =
      `${words(analysis.coordinate_source)} · descriptive only`;
    const selectedCase = api.getMotifCatalog().cases.find((item) => item.case_id === analysis.state.case_id);
    document.getElementById("triage-case-title").textContent = selectedCase
      ? selectedCase.title
      : "Case-to-intervention triage";
  }

  function render(analysis) {
    latest = analysis;
    renderOrientation(analysis);
    renderGlobe(analysis);
    renderBirths(analysis);
    renderEvidence(analysis);
  }

  function decisionState() {
    const analysis = api.getAnalysis();
    if (!analysis) return null;
    return {
      schema: "pixieology_mechinterp_triage_decision_state_v1",
      case_id: analysis.state.case_id,
      evidence_class: analysis.coordinate_source,
      claim_boundary: analysis.claim_boundary,
      state: { ...analysis.state },
      direct_glued_partners: analysis.direct_glued_partners.map((item) => ({ ...item })),
      closure_component: analysis.closure_component.map((item) => ({ ...item })),
      selected_component: { ...analysis.topology.selected_component },
      dendrogram_births: analysis.topology.dendrogram_mst.map((edge) => ({ ...edge })),
      spin: { ...analysis.spin },
      job_gate: {
        evidence_reviewed: reviewed.disabled,
        browser_authorization_available: false,
        browser_execution_available: false
      }
    };
  }

  window.addEventListener("pixieology:etale-analysis", (event) => render(event.detail));
  reviewed.addEventListener("click", () => {
    jobs.hidden = false;
    reviewed.disabled = true;
    reviewed.textContent = "Evidence reviewed";
    jobs.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  document.querySelectorAll("[data-triage-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(`triage-${button.dataset.triageTarget}`);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  epsilonInput.addEventListener("input", () => {
    if (latest) document.getElementById("triage-epsilon-display").textContent = Number(epsilonInput.value).toFixed(2);
  });

  configureVariants();
  const initial = api.getAnalysis();
  if (initial) render(initial);

  window.PixieMechinterpTriage = Object.freeze({
    schema: "pixieology_mechinterp_triage_contract_v1",
    variants: Object.freeze({ ...variants }),
    methods: Object.freeze(["getAnalysis", "getDecisionState", "markEvidenceReviewed"]),
    getAnalysis: () => api.getAnalysis(),
    getDecisionState: decisionState,
    markEvidenceReviewed: () => reviewed.click()
  });
})();
