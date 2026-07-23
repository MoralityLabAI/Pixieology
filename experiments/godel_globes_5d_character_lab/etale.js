(function () {
  "use strict";

  const atlasApi = window.PixieMechinterpAtlas;
  const geometry = window.PixieMechinterpManifold;
  const etaleApi = window.PixieMechinterpEtale;
  const motifCatalog = validateMotifCatalog(window.PixieEtaleMotifCatalogData);
  const feedbackQueue = validateFeedbackQueue(window.PixieLoraFeedbackJobQueueData);
  const atlas = atlasApi.validate(window.PixieMechinterpAtlasData);
  const parameterPoints = geometry.buildPoints(atlas);
  const parameterEtaleMap = etaleApi.buildMap(parameterPoints);
  let points = parameterPoints;
  let etaleMap = parameterEtaleMap;
  const svg = document.getElementById("etale-map");
  const playButton = document.getElementById("etale-play");
  const layerInput = document.getElementById("etale-layer");
  const layerOutput = document.getElementById("etale-layer-value");
  const moduleInput = document.getElementById("etale-module");
  const radiusInput = document.getElementById("etale-radius");
  const radiusOutput = document.getElementById("etale-radius-value");
  const epsilonInput = document.getElementById("etale-epsilon");
  const epsilonOutput = document.getElementById("etale-epsilon-value");
  const tauInput = document.getElementById("etale-tau");
  const tauOutput = document.getElementById("etale-tau-value");
  const qInput = document.getElementById("etale-q");
  const qOutput = document.getElementById("etale-q-value");
  const status = document.getElementById("etale-status");
  const motifOutput = document.getElementById("etale-motif");
  const analysisJson = document.getElementById("etale-analysis-json");
  const feedbackQueueStatus = document.getElementById("feedback-queue-status");
  const feedbackJobRows = document.getElementById("feedback-job-rows");
  const feedbackJobTitle = document.getElementById("feedback-job-title");
  const feedbackJobHypothesis = document.getElementById("feedback-job-hypothesis");
  const feedbackJobHash = document.getElementById("feedback-job-hash");

  const contract = Object.freeze({
    schema: "pixieology_etale_explorer_contract_v3",
    status: "experimental",
    canonical: false,
    state_schema: "pixieology_etale_explorer_state_v3",
    analysis_schema: "pixieology_etale_analysis_v3",
    motif_catalog_schema: "pixieology_etale_motif_catalog_v1",
    motif_card_schema: "pixieology_mechinterp_motif_card_v1",
    feedback_queue_schema: "pixieology_lora_feedback_queue_v1",
    feedback_job_schema: "pixieology_lora_feedback_job_v1",
    event: "pixieology:etale-analysis",
    dom_receipt_id: "etale-analysis-json",
    methods: Object.freeze([
      "getContract", "getState", "setState", "setPlaying", "getAnalysis", "getShareUrl",
      "getMotifCatalog", "listCases", "loadCase", "listMotifs", "getMotif",
      "getJobQueue", "listJobs", "getJob", "selectJob", "getSelectedJob"
    ]),
    query_parameters: Object.freeze({
      case: "case_id",
      layer: "layer",
      module: "module_id",
      radius: "chart_radius",
      epsilon: "glue_tolerance",
      tau: "lineage_floor",
      q: "spin_noise",
      job: "selected_job_id"
    }),
    state_fields: Object.freeze({
      layer: Object.freeze({ type: "integer", enum: Object.freeze(parameterEtaleMap.layers.slice()) }),
      module_id: Object.freeze({ type: "string", enum: Object.freeze(parameterEtaleMap.moduleIds.slice()) }),
      chart_radius: Object.freeze({ type: "integer", minimum: 1, maximum: 5 }),
      glue_tolerance: Object.freeze({ type: "number", minimum: 0.1, maximum: 0.6 }),
      lineage_floor: Object.freeze({ type: "number", minimum: 0, maximum: 1 }),
      spin_noise: Object.freeze({ type: "number", minimum: 0, maximum: 0.5 }),
      case_id: Object.freeze({ type: ["string", "null"], enum: Object.freeze([null, ...motifCatalog.cases.map((item) => item.case_id)]) }),
      selected_job_id: Object.freeze({ type: ["string", "null"], enum: Object.freeze([null, ...feedbackQueue.jobs.map((item) => item.job_id)]) }),
      playing: Object.freeze({ type: "boolean" })
    }),
    coordinate_semantics: Object.freeze({
      x: "parameter update-energy coordinate by default; globally normalized response magnitude in an activation case",
      y: "global spectral-focus coordinate by default; globally normalized response top-mode share in an activation case",
      z: "global effective-rank coordinate by default; globally normalized response mode-entropy fraction in an activation case",
      w: "ordered transformer depth",
      s: "overlap-level spin/liveness certificate"
    }),
    claim_boundary: "Local equivalence is a descriptive normalized X/Y/Z tolerance relation. Connected components are its transitive closure; quotient merge and split marks are not literal étale branching. Job selection is inspection state and never authorization."
  });
  let analysisSequence = 0;
  let lastAnalysis = null;
  let queryWarnings = [];
  let activeCaseId = null;

  const state = {
    layer: 13,
    moduleId: atlas.modules[0].id,
    radius: 2,
    epsilon: 0.25,
    tau: 0.2,
    q: 0.15,
    selectedJobId: null,
    timer: null
  };

  function clone(value) {
    return value === null || value === undefined ? value : JSON.parse(JSON.stringify(value));
  }

  function validateMotifCatalog(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError("motif catalog must be an object");
    if (value.schema !== "pixieology_etale_motif_catalog_v1") throw new Error("invalid motif catalog schema");
    if (!Array.isArray(value.motifs) || !Array.isArray(value.cases)) throw new Error("motif catalog requires motif and case arrays");
    const motifIds = value.motifs.map((motif) => String(motif.motif_id));
    const caseIds = value.cases.map((item) => String(item.case_id));
    if (new Set(motifIds).size !== motifIds.length) throw new Error("motif catalog contains duplicate motif IDs");
    if (new Set(caseIds).size !== caseIds.length) throw new Error("motif catalog contains duplicate case IDs");
    value.cases.forEach((item) => {
      if (!Object.hasOwn(item, "coordinates")) return;
      if (item.coordinate_source !== "activation_conditioned_trained_counterfactual_on_base") {
        throw new Error(`case ${item.case_id} has an unsupported coordinate source`);
      }
      if (!Array.isArray(item.module_ids) || item.module_ids.length !== 7) throw new Error(`case ${item.case_id} requires seven module sheets`);
      if (!Array.isArray(item.coordinates) || item.coordinates.length !== 28) throw new Error(`case ${item.case_id} requires 28 layers`);
      item.coordinates.forEach((layer) => {
        if (!Array.isArray(layer) || layer.length !== item.module_ids.length) throw new Error(`case ${item.case_id} has an incomplete stalk`);
        layer.forEach((coordinate) => {
          if (!Array.isArray(coordinate) || coordinate.length !== 3 || coordinate.some((entry) => typeof entry !== "number" || !Number.isFinite(entry))) {
            throw new Error(`case ${item.case_id} has an invalid X/Y/Z coordinate`);
          }
        });
      });
    });
    return value;
  }

  function validateFeedbackQueue(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError("feedback job queue must be an object");
    if (value.schema !== "pixieology_lora_feedback_queue_v1") throw new Error("invalid feedback job queue schema");
    if (value.status !== "STAGED_NOT_AUTHORIZED" || value.automatic_authorization !== false) {
      throw new Error("feedback job queue must be staged and non-authorizing");
    }
    if (!Array.isArray(value.jobs) || value.jobs.length !== value.job_count || value.jobs.length < 2 || value.jobs.length > 6) {
      throw new Error("feedback job queue count is invalid");
    }
    const identifiers = value.jobs.map((job) => String(job.job_id));
    if (new Set(identifiers).size !== identifiers.length) throw new Error("feedback job queue contains duplicate IDs");
    value.jobs.forEach((job) => {
      if (job.schema !== "pixieology_lora_feedback_job_v1") throw new Error(`job ${job.job_id} has an invalid schema`);
      if (!["EVALUATE", "TRAIN_ADAPTER"].includes(job.job_type)) throw new Error(`job ${job.job_id} has an invalid type`);
      if (!["base_qwen_derived_1p7b", "pixie_rank8", "tinylora", "qlora"].includes(job.method)) throw new Error(`job ${job.job_id} has an invalid method`);
      if (job.authorization?.required !== true || job.authorization?.status !== "NOT_AUTHORIZED") {
        throw new Error(`job ${job.job_id} is not a non-authorizing proposal`);
      }
      if (!/^[a-f0-9]{64}$/.test(String(job.authorization.job_sha256))) throw new Error(`job ${job.job_id} lacks an immutable hash`);
    });
    return value;
  }

  function caseById(caseId) {
    return motifCatalog.cases.find((item) => item.case_id === caseId) || null;
  }

  function motifById(motifId) {
    return motifCatalog.motifs.find((item) => item.motif_id === motifId) || null;
  }

  function jobById(jobId) {
    return feedbackQueue.jobs.find((item) => item.job_id === jobId) || null;
  }

  function pointsForCase(selectedCase) {
    if (!selectedCase || !Array.isArray(selectedCase.coordinates)) return parameterPoints;
    const metadata = new Map(parameterEtaleMap.sheets.map((sheet) => [sheet.moduleId, sheet]));
    return selectedCase.coordinates.flatMap((layerCoordinates, layer) => selectedCase.module_ids.map((moduleId, moduleIndex) => {
      const module = metadata.get(moduleId);
      if (!module) throw new Error(`case ${selectedCase.case_id} names unknown module ${moduleId}`);
      const coordinate = layerCoordinates[moduleIndex].map(Number);
      return Object.freeze({
        layer,
        moduleId,
        moduleLabel: module.moduleLabel,
        moduleIndex,
        family: module.family,
        x: coordinate[0],
        y: coordinate[1],
        z: coordinate[2],
        w: (layer / Math.max(1, selectedCase.coordinates.length - 1)) * 2 - 1,
        energy: coordinate[0],
        spectralFocus: coordinate[1],
        effectiveRank: coordinate[2]
      });
    }));
  }

  function activateCase(selectedCase) {
    points = pointsForCase(selectedCase);
    etaleMap = selectedCase ? etaleApi.buildMap(points) : parameterEtaleMap;
    activeCaseId = selectedCase ? selectedCase.case_id : null;
  }

  function finiteInRange(value, lower, upper, label) {
    const number = Number(value);
    if (!Number.isFinite(number) || number < lower || number > upper) throw new RangeError(`${label} must be in [${lower}, ${upper}]`);
    return number;
  }

  function validateStatePatch(patch) {
    if (!patch || typeof patch !== "object" || Array.isArray(patch)) throw new TypeError("state patch must be an object");
    const allowed = new Set(["schema", "sequence", "layer", "module_id", "chart_radius", "glue_tolerance", "lineage_floor", "spin_noise", "case_id", "selected_job_id", "playing"]);
    const unknown = Object.keys(patch).filter((key) => !allowed.has(key));
    if (unknown.length) throw new Error(`unknown state field${unknown.length === 1 ? "" : "s"}: ${unknown.join(", ")}`);
    const value = {};
    if (Object.hasOwn(patch, "schema") && patch.schema !== contract.state_schema) throw new Error(`state schema must be ${contract.state_schema}`);
    if (Object.hasOwn(patch, "layer")) {
      const layer = Number(patch.layer);
      if (!Number.isInteger(layer) || !etaleMap.layers.includes(layer)) throw new RangeError("layer must identify a sampled transformer depth");
      value.layer = layer;
    }
    if (Object.hasOwn(patch, "module_id")) {
      const moduleId = String(patch.module_id);
      if (!etaleMap.moduleIds.includes(moduleId)) throw new RangeError(`unknown module_id ${moduleId}`);
      value.moduleId = moduleId;
    }
    if (Object.hasOwn(patch, "chart_radius")) {
      const radius = Number(patch.chart_radius);
      if (!Number.isInteger(radius) || radius < 1 || radius > 5) throw new RangeError("chart_radius must be an integer in [1, 5]");
      value.radius = radius;
    }
    if (Object.hasOwn(patch, "glue_tolerance")) value.epsilon = finiteInRange(patch.glue_tolerance, 0.1, 0.6, "glue_tolerance");
    if (Object.hasOwn(patch, "lineage_floor")) value.tau = finiteInRange(patch.lineage_floor, 0, 1, "lineage_floor");
    if (Object.hasOwn(patch, "spin_noise")) value.q = finiteInRange(patch.spin_noise, 0, 0.5, "spin_noise");
    if (Object.hasOwn(patch, "case_id")) {
      if (patch.case_id === null) value.caseId = null;
      else if (!caseById(String(patch.case_id))) throw new RangeError(`unknown case_id ${patch.case_id}`);
      else value.caseId = String(patch.case_id);
    }
    if (Object.hasOwn(patch, "selected_job_id")) {
      if (patch.selected_job_id === null) value.selectedJobId = null;
      else if (!jobById(String(patch.selected_job_id))) throw new RangeError(`unknown selected_job_id ${patch.selected_job_id}`);
      else value.selectedJobId = String(patch.selected_job_id);
    }
    if (Object.hasOwn(patch, "playing")) {
      if (typeof patch.playing !== "boolean") throw new TypeError("playing must be boolean");
      value.playing = patch.playing;
    }
    return value;
  }

  function explorerState() {
    return {
      schema: contract.state_schema,
      sequence: lastAnalysis ? lastAnalysis.sequence : 0,
      layer: state.layer,
      module_id: state.moduleId,
      chart_radius: state.radius,
      glue_tolerance: state.epsilon,
      lineage_floor: state.tau,
      spin_noise: state.q,
      case_id: activeCaseId,
      selected_job_id: state.selectedJobId,
      playing: state.timer !== null
    };
  }

  function stateUrl() {
    const url = new URL(window.location.href);
    if (activeCaseId) url.searchParams.set("case", activeCaseId); else url.searchParams.delete("case");
    if (state.selectedJobId) url.searchParams.set("job", state.selectedJobId); else url.searchParams.delete("job");
    url.searchParams.set("layer", String(state.layer));
    url.searchParams.set("module", state.moduleId);
    url.searchParams.set("radius", String(state.radius));
    url.searchParams.set("epsilon", state.epsilon.toFixed(2));
    url.searchParams.set("tau", state.tau.toFixed(2));
    url.searchParams.set("q", state.q.toFixed(2));
    return url;
  }

  function syncLocation() {
    const url = stateUrl();
    try {
      window.history.replaceState(null, "", url.href);
    } catch (_error) {
      // The state URI remains available through getShareUrl when file-scheme history is restricted.
    }
    return url.href;
  }

  function loadInitialQuery() {
    const params = new URLSearchParams(window.location.search);
    if (params.has("case")) {
      const requestedCase = params.get("case");
      const selectedCase = caseById(requestedCase);
      if (selectedCase) {
        activateCase(selectedCase);
        if (selectedCase.state) Object.assign(state, validateStatePatch(selectedCase.state));
      } else {
        queryWarnings.push(`case: unknown case_id ${requestedCase}`);
      }
    }
    const entries = [
      ["layer", "layer", Number],
      ["module", "module_id", String],
      ["radius", "chart_radius", Number],
      ["epsilon", "glue_tolerance", Number],
      ["tau", "lineage_floor", Number],
      ["q", "spin_noise", Number],
      ["job", "selected_job_id", String]
    ];
    entries.forEach(([queryKey, stateKey, parse]) => {
      if (!params.has(queryKey)) return;
      try {
        Object.assign(state, validateStatePatch({ [stateKey]: parse(params.get(queryKey)) }));
      } catch (error) {
        queryWarnings.push(`${queryKey}: ${error.message}`);
      }
    });
  }

  loadInitialQuery();

  atlas.modules.forEach((module) => {
    const option = document.createElement("option");
    option.value = module.id;
    option.textContent = module.label;
    moduleInput.appendChild(option);
  });

  const ns = "http://www.w3.org/2000/svg";
  function element(name, attributes = {}, text = null) {
    const node = document.createElementNS(ns, name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text !== null) node.textContent = text;
    return node;
  }

  function pathData(values, xValue, yValue) {
    return values.map((value, index) => `${index ? "L" : "M"} ${xValue(value).toFixed(2)} ${yValue(value).toFixed(2)}`).join(" ");
  }

  function moduleLabel(moduleId) {
    return etaleApi.sheetAt(etaleMap, moduleId).moduleLabel;
  }

  function otherModule(pair, moduleId) {
    return pair.a === moduleId ? pair.b : pair.a;
  }

  function pairLabel(pairId) {
    return pairId.split("|").map(moduleLabel).join(" ↔ ");
  }

  function words(value) {
    return value ? value.replaceAll("_", " ") : "unavailable";
  }

  function categoryY(category, center) {
    const offsets = {
      forced_positive: 20,
      live_positive: 6,
      synthetic_negative_below_liveness: -8,
      frustrated_live: -22
    };
    return center + (offsets[category] || 0);
  }

  function drawSpinMark(parent, cycle, x, y) {
    if (cycle.category === "synthetic_negative_below_liveness") {
      parent.appendChild(element("path", { class: "spin-synthetic", d: `M ${x - 5} ${y - 5} L ${x + 5} ${y + 5} M ${x + 5} ${y - 5} L ${x - 5} ${y + 5}` }));
      return;
    }
    if (cycle.category === "frustrated_live") {
      parent.appendChild(element("path", { class: "spin-frustrated", d: `M ${x} ${y - 6} L ${x + 6} ${y + 5} L ${x - 6} ${y + 5} Z` }));
      return;
    }
    parent.appendChild(element("circle", {
      class: cycle.category === "live_positive" ? "spin-live-positive" : "spin-forced",
      cx: x, cy: y, r: 5
    }));
  }

  function feedbackJobSummary(job) {
    const adapter = job.adapter;
    const footprint = !adapter
      ? "transfer reference"
      : `${adapter.target_modules.length} sheet${adapter.target_modules.length === 1 ? "" : "s"} × ${adapter.layers_to_transform.length} layers · r${adapter.rank}`;
    return {
      job_id: job.job_id,
      label: job.label,
      job_type: job.job_type,
      method: job.method,
      status: job.status,
      authorization_status: job.authorization.status,
      job_sha256: job.authorization.job_sha256,
      origin_motif_id: job.origin?.motif_id || null,
      origin_case_id: job.origin?.case_id || null,
      selection_role: job.origin?.selection_role || null,
      footprint,
      budget: `${job.resources.ram_mb} MiB · ${job.resources.cpu_pct}% CPU · ${job.resources.timeout_seconds}s`
    };
  }

  function appendFeedbackCell(row, text, className = "") {
    const cell = document.createElement("td");
    if (className) cell.className = className;
    cell.textContent = text;
    row.appendChild(cell);
    return cell;
  }

  function renderFeedbackJobs() {
    feedbackQueueStatus.textContent = `${feedbackQueue.job_count} staged · ${words(feedbackQueue.training_slot_status)} · auto-authorization off`;
    feedbackJobRows.replaceChildren();
    feedbackQueue.jobs.forEach((job) => {
      const summary = feedbackJobSummary(job);
      const selected = job.job_id === state.selectedJobId;
      const row = document.createElement("tr");
      row.dataset.jobId = job.job_id;
      row.dataset.selected = String(selected);
      appendFeedbackCell(row, job.label, "job-method");
      appendFeedbackCell(row, summary.origin_motif_id ? `${summary.origin_motif_id} · ${words(summary.selection_role)}` : "frozen reference");
      appendFeedbackCell(row, summary.footprint);
      appendFeedbackCell(row, summary.budget);
      appendFeedbackCell(row, `${words(job.status)} · not authorized`, "job-state");
      const action = appendFeedbackCell(row, "");
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.jobId = job.job_id;
      button.setAttribute("aria-pressed", String(selected));
      button.textContent = selected ? "Selected" : "Inspect";
      action.appendChild(button);
      feedbackJobRows.appendChild(row);
    });
    const selected = state.selectedJobId ? jobById(state.selectedJobId) : null;
    if (!selected) {
      feedbackJobTitle.textContent = "No job selected";
      feedbackJobHypothesis.textContent = "Choose an experiment slot to inspect its hypothesis and immutable job hash.";
      feedbackJobHash.textContent = "selection only · no browser authorization surface";
      return;
    }
    feedbackJobTitle.textContent = selected.label;
    feedbackJobHypothesis.textContent = selected.hypothesis;
    feedbackJobHash.textContent = `${selected.job_id} · sha256:${selected.authorization.job_sha256}`;
  }

  function render() {
    renderFeedbackJobs();
    const activeCase = activeCaseId ? caseById(activeCaseId) : null;
    const gluingAtlas = etaleApi.buildGluingAtlas(etaleMap, state.radius, state.epsilon);
    const localGlue = gluingAtlas.samples.find((sample) => sample.layer === state.layer);
    const chart = localGlue.chart;
    const selectedSheet = etaleApi.sheetAt(etaleMap, state.moduleId);
    const selectedChartSheet = chart.sheets.find((sheet) => sheet.moduleId === state.moduleId);
    const selectedPairs = localGlue.pairs
      .filter((pair) => pair.a === state.moduleId || pair.b === state.moduleId)
      .sort((first, second) => first.distance - second.distance);
    const closestPair = selectedPairs[0];
    const gluedPairs = selectedPairs.filter((pair) => pair.equivalent);
    const peerId = otherModule(closestPair, state.moduleId);
    const peerChartSheet = chart.sheets.find((sheet) => sheet.moduleId === peerId);
    const spin = geometry.analyzeSpinLadder(points, state.moduleId, peerId, state.tau, state.q);
    const overlaps = etaleApi.overlapCycles(spin, chart);
    const selectedGerm = etaleApi.germAt(etaleMap, state.moduleId, state.layer);
    const nearest = etaleApi.nearestCycle(spin.cycles, selectedGerm.w);
    const compact = window.matchMedia("(max-width: 640px)").matches;
    const layout = compact ? {
      width: 620, height: 980,
      plotLeft: 150, plotRight: 590,
      windowTop: 34, windowHeight: 345,
      sheetTop: 78, sheetGap: 42,
      stalkTop: 58, stalkEnd: 345, projectionEnd: 387,
      baseY: 398, baseLabelY: 402, baseTickY: 426,
      localHeadingY: 477, guideTop: 493, guideBottom: 928,
      chartLeft: 170, chartRight: 590,
      rowCenters: [555, 665, 775], spinCenter: 885, localTickY: 958
    } : {
      width: 1200, height: 700,
      plotLeft: 118, plotRight: 1160,
      windowTop: 26, windowHeight: 306,
      sheetTop: 62, sheetGap: 31,
      stalkTop: 46, stalkEnd: 278, projectionEnd: 306,
      baseY: 316, baseLabelY: 320, baseTickY: 337,
      localHeadingY: 365, guideTop: 378, guideBottom: 666,
      chartLeft: 154, chartRight: 1145,
      rowCenters: [405, 475, 545], spinCenter: 615, localTickY: 679
    };

    svg.replaceChildren();
    svg.setAttribute("viewBox", `0 0 ${layout.width} ${layout.height}`);
    svg.appendChild(element("title", { id: "etale-title" }, "Locally glued map of Pixie adapter deltas"));
    svg.appendChild(element("desc", { id: "etale-desc" }, "Seven globally distinct module sheets project to transformer depth. Local metric equivalences glue sheets over chart windows while preserving their identities."));
    const plotLeft = layout.plotLeft;
    const plotRight = layout.plotRight;
    const fullX = (layer) => plotLeft + (layer / (etaleMap.layers.length - 1)) * (plotRight - plotLeft);
    const windowLeft = fullX(chart.lowerLayer) - 10;
    const windowRight = fullX(chart.upperLayer) + 10;
    svg.appendChild(element("rect", { class: "chart-window", x: windowLeft, y: layout.windowTop, width: windowRight - windowLeft, height: layout.windowHeight, rx: 8 }));
    svg.appendChild(element("text", { class: "axis-label", x: windowLeft + 8, y: layout.windowTop + 17 }, `U = layers ${chart.lowerLayer}–${chart.upperLayer}`));

    const sheetIndex = new Map(etaleMap.sheets.map((sheet, index) => [sheet.moduleId, index]));
    function sheetY(moduleId, point) {
      const lane = layout.sheetTop + sheetIndex.get(moduleId) * layout.sheetGap;
      return lane - point.x * 8 - point.y * 5 + point.z * 4;
    }
    const selectedBands = gluingAtlas.bands.filter((band) => band.a === state.moduleId || band.b === state.moduleId);
    const glueGroup = element("g", { "aria-label": "Local equivalence bands for the selected sheet" });
    selectedBands.forEach((band) => {
      const otherId = band.a === state.moduleId ? band.b : band.a;
      const current = state.layer >= band.startLayer && state.layer <= band.endLayer;
      const laneY = layout.baseY - 12 - sheetIndex.get(otherId) * 6;
      let startX = fullX(band.startLayer);
      let endX = fullX(band.endLayer);
      if (Math.abs(endX - startX) < 10) {
        startX -= 5;
        endX += 5;
      }
      glueGroup.appendChild(element("line", {
        class: `gluing-band${current ? " current" : ""}`,
        x1: startX, y1: laneY, x2: endX, y2: laneY,
        "data-band-id": band.id,
        "data-module-a": band.a,
        "data-module-b": band.b,
        "data-start-layer": band.startLayer,
        "data-end-layer": band.endLayer,
        "aria-label": `${moduleLabel(band.a)} and ${moduleLabel(band.b)} are directly glued from layer ${band.startLayer} through ${band.endLayer}`
      }));
      const lower = Math.max(chart.lowerLayer, band.startLayer);
      const upper = Math.min(chart.upperLayer, band.endLayer);
      for (let layer = lower; layer <= upper; layer += 1) {
        const first = etaleApi.germAt(etaleMap, state.moduleId, layer);
        const second = etaleApi.germAt(etaleMap, otherId, layer);
        glueGroup.appendChild(element("line", {
          class: `gluing-bridge${layer === state.layer ? " current" : ""}`,
          x1: fullX(layer), y1: sheetY(state.moduleId, first),
          x2: fullX(layer), y2: sheetY(otherId, second),
          "data-layer": layer,
          "data-module-a": state.moduleId,
          "data-module-b": otherId,
          "aria-label": `${moduleLabel(state.moduleId)} is directly glued to ${moduleLabel(otherId)} at chart center ${layer}`
        }));
        glueGroup.appendChild(element("circle", { class: "glue-node", cx: fullX(layer), cy: sheetY(otherId, second), r: 3.5 }));
      }
    });
    svg.appendChild(glueGroup);

    const sheetGroup = element("g", { "aria-label": "Module sheets over the depth base" });
    etaleMap.sheets.forEach((sheet, sheetIndex) => {
      const lane = layout.sheetTop + sheetIndex * layout.sheetGap;
      const yValue = (point) => sheetY(sheet.moduleId, point);
      const selected = sheet.moduleId === state.moduleId;
      sheetGroup.appendChild(element("path", {
        class: `sheet-path ${sheet.family}${selected ? " selected" : ""}`,
        d: pathData(sheet.points, (point) => fullX(point.layer), yValue),
        "data-module": sheet.moduleId,
        "aria-label": `${sheet.moduleLabel} global sheet across all transformer layers`
      }));
      sheetGroup.appendChild(element("text", { class: `sheet-label${selected ? " selected" : ""}`, x: 14, y: lane + 4 }, sheet.moduleLabel));
      const germ = sheet.points.find((point) => point.layer === state.layer);
      sheetGroup.appendChild(element("circle", {
        class: `germ-node${selected ? " selected" : ""}`,
        cx: fullX(state.layer), cy: yValue(germ), r: selected ? 5.5 : 3.5
      }));
    });
    svg.appendChild(sheetGroup);

    gluingAtlas.transitions.forEach((transition) => {
      const x = fullX(transition.layer);
      const y = layout.baseY - 3;
      const current = transition.layer === state.layer;
      svg.appendChild(element("path", {
        class: `transition-mark${current ? " current" : ""}`,
        d: `M ${x} ${y - 5} L ${x + 5} ${y} L ${x} ${y + 5} L ${x - 5} ${y} Z`,
        "data-layer": transition.layer,
        "data-transition-kind": transition.kind,
        "data-added": transition.added.join(","),
        "data-removed": transition.removed.join(","),
        "aria-label": `${transition.kind} quotient transition at layer ${transition.layer}`
      }));
    });

    const stalkX = fullX(state.layer);
    svg.appendChild(element("line", { class: "stalk-line", x1: stalkX, y1: layout.stalkTop, x2: stalkX, y2: layout.stalkEnd }));
    svg.appendChild(element("line", { class: "projection-arrow", x1: stalkX, y1: layout.stalkEnd, x2: stalkX, y2: layout.projectionEnd }));
    svg.appendChild(element("path", { class: "projection-arrow", d: `M ${stalkX - 5} ${layout.projectionEnd - 7} L ${stalkX} ${layout.projectionEnd + 1} L ${stalkX + 5} ${layout.projectionEnd - 7}` }));
    svg.appendChild(element("text", { class: "axis-label", x: stalkX + 8, y: layout.projectionEnd - 12 }, "p"));
    svg.appendChild(element("line", { class: "base-line", x1: plotLeft, y1: layout.baseY, x2: plotRight, y2: layout.baseY }));
    svg.appendChild(element("text", { class: "axis-label", x: 14, y: layout.baseLabelY }, "base W"));
    etaleMap.base.forEach((entry) => {
      const selected = entry.layer === state.layer;
      const circle = element("circle", {
        class: `base-node${selected ? " selected" : ""}`,
        cx: fullX(entry.layer), cy: layout.baseY, r: selected ? 5.5 : 3.2,
        "data-layer": entry.layer,
        "aria-label": `Select transformer layer ${entry.layer}`
      });
      circle.addEventListener("click", () => {
        state.layer = entry.layer;
        stopPlayback();
        syncControls();
        render();
      });
      svg.appendChild(circle);
      if (entry.layer % 4 === 0 || entry.layer === etaleMap.layers.at(-1)) {
        svg.appendChild(element("text", { class: "depth-label", x: fullX(entry.layer), y: layout.baseTickY, "text-anchor": "middle" }, entry.layer));
      }
    });

    const chartLeft = layout.chartLeft;
    const chartRight = layout.chartRight;
    const localX = (layer) => chart.base.length === 1 ? (chartLeft + chartRight) / 2 : chartLeft + ((layer - chart.lowerLayer) / (chart.upperLayer - chart.lowerLayer)) * (chartRight - chartLeft);
    const rows = activeCase ? [
      { key: "X", label: "response magnitude", center: layout.rowCenters[0], value: (point) => point.x },
      { key: "Y", label: "top-mode share", center: layout.rowCenters[1], value: (point) => point.y },
      { key: "Z", label: "mode entropy", center: layout.rowCenters[2], value: (point) => point.z }
    ] : [
      { key: "X", label: "update coordinate", center: layout.rowCenters[0], value: (point) => point.x },
      { key: "Y", label: "spectral focus", center: layout.rowCenters[1], value: (point) => point.y },
      { key: "Z", label: "effective rank", center: layout.rowCenters[2], value: (point) => point.z }
    ];
    if (closestPair.equivalent) {
      svg.appendChild(element("rect", {
        class: "local-glue-field",
        x: chartLeft - 8,
        y: layout.guideTop,
        width: chartRight - chartLeft + 16,
        height: layout.guideBottom - layout.guideTop,
        rx: 6
      }));
    }
    const relation = closestPair.equivalent ? "glued to" : "nearest";
    svg.appendChild(element("text", { class: "axis-label", x: 14, y: layout.localHeadingY }, `${selectedSheet.moduleLabel} ${relation} ${moduleLabel(peerId)} over U · d=${closestPair.distance.toFixed(3)}`));
    const selectedLocalX = localX(state.layer);
    svg.appendChild(element("line", { class: "selected-guide", x1: selectedLocalX, y1: layout.guideTop, x2: selectedLocalX, y2: layout.guideBottom }));
    rows.forEach((row) => {
      const yValue = (point) => row.center - row.value(point) * 24;
      svg.appendChild(element("line", { class: "metric-baseline", x1: chartLeft, y1: row.center, x2: chartRight, y2: row.center }));
      svg.appendChild(element("text", { class: "axis-label", x: 14, y: row.center + 4 }, `${row.key}  ${row.label}`));
      svg.appendChild(element("path", { class: "metric-peer", d: pathData(peerChartSheet.points, (point) => localX(point.layer), yValue) }));
      svg.appendChild(element("path", { class: "metric-path", d: pathData(selectedChartSheet.points, (point) => localX(point.layer), yValue) }));
      selectedChartSheet.points.forEach((point) => {
        svg.appendChild(element("circle", { class: "metric-node", cx: localX(point.layer), cy: yValue(point), r: point.layer === state.layer ? 5 : 3.2 }));
      });
    });

    const spinCenter = layout.spinCenter;
    svg.appendChild(element("line", { class: "metric-baseline", x1: chartLeft, y1: spinCenter, x2: chartRight, y2: spinCenter }));
    svg.appendChild(element("text", { class: "axis-label", x: 14, y: spinCenter + 4 }, "S  overlap certificate"));
    overlaps.forEach((cycle) => {
      const layerPosition = Math.max(chart.lowerLayer, Math.min(chart.upperLayer, chart.lowerLayer + ((cycle.center.w - chart.base[0].w) / Math.max(1e-12, chart.base.at(-1).w - chart.base[0].w)) * (chart.upperLayer - chart.lowerLayer)));
      drawSpinMark(svg, cycle, localX(layerPosition), categoryY(cycle.category, spinCenter));
    });
    chart.base.forEach((entry) => {
      svg.appendChild(element("text", { class: "depth-label", x: localX(entry.layer), y: layout.localTickY, "text-anchor": "middle" }, entry.layer));
    });
    svg.appendChild(element("text", { class: "axis-label", x: 14, y: layout.localTickY }, "W  depth"));

    document.getElementById("etale-x").textContent = selectedGerm.x.toFixed(3);
    document.getElementById("etale-y").textContent = `${(selectedGerm.spectralFocus * 100).toFixed(1)}%`;
    document.getElementById("etale-z").textContent = selectedGerm.effectiveRank.toFixed(2);
    document.getElementById("etale-w").textContent = `${selectedGerm.layer} / ${etaleMap.layers.at(-1)}`;
    document.getElementById("etale-s").textContent = words(nearest && nearest.category);
    document.getElementById("etale-g").textContent = gluedPairs.length ? gluedPairs.map((pair) => `${moduleLabel(otherModule(pair, state.moduleId))} (${pair.distance.toFixed(3)})`).join(" · ") : `none at ε=${state.epsilon.toFixed(2)}`;
    const component = localGlue.components.find((candidate) => candidate.includes(state.moduleId));
    const componentDiagnostic = localGlue.componentDiagnostics.find((candidate) => candidate.members.includes(state.moduleId));
    const activeMotifIds = activeCase && Array.isArray(activeCase.motif_ids) ? activeCase.motif_ids : [];
    motifOutput.textContent = activeMotifIds.length ? activeMotifIds.join(" · ") : words(motifCatalog.status);
    const exactTransition = gluingAtlas.transitions.find((transition) => transition.layer === state.layer);
    const nearestTransition = exactTransition || [...gluingAtlas.transitions].sort((first, second) => Math.abs(first.layer - state.layer) - Math.abs(second.layer - state.layer))[0];
    const changedPairs = nearestTransition ? [...nearestTransition.added, ...nearestTransition.removed] : [];
    const changedPair = changedPairs.find((pairId) => pairId.split("|").includes(state.moduleId)) || changedPairs[0];
    const transitionText = exactTransition ? `${exactTransition.kind} at this depth${changedPair ? ` (${pairLabel(changedPair)})` : ""}` : nearestTransition ? `nearest ${nearestTransition.kind} at W=${nearestTransition.layer}${changedPair ? ` (${pairLabel(changedPair)})` : ""}` : "no quotient transitions";
    const relationText = closestPair.equivalent ? "locally equivalent" : "not locally equivalent";
    const robustnessText = componentDiagnostic.bridgeStatus === "none" ?
      `bridge: none; chain excess ${componentDiagnostic.chainExcess.toFixed(3)}` :
      `bridges ${componentDiagnostic.bridges.join(", ")}; chain excess ${componentDiagnostic.chainExcess.toFixed(3)}`;
    const coordinateText = activeCase
      ? `Activation-conditioned case ${activeCase.case_id}`
      : "Parameter-only atlas";
    status.textContent = `${coordinateText}. ${selectedSheet.moduleLabel} and ${moduleLabel(peerId)} are ${relationText}: d_U=${closestPair.distance.toFixed(3)} ${closestPair.equivalent ? "≤" : ">"} ε=${state.epsilon.toFixed(2)}. The local quotient component contains ${component.length} globally distinct sheet${component.length === 1 ? "" : "s"} (${robustnessText}); ${transitionText}. Across W there are ${gluingAtlas.bands.length} gluing bands and ${gluingAtlas.transitions.length} transitions. Motif catalog: ${words(motifCatalog.status)}. Monodromy is unavailable because ${gluingAtlas.monodromy.reason}. S is computed on ${overlaps.length} overlap cycle${overlaps.length === 1 ? "" : "s"}; τ is a parameter-state proxy and q is synthetic.`;

    const pairByPeer = new Map(selectedPairs.map((pair) => [otherModule(pair, state.moduleId), pair]));
    const shareUri = syncLocation();
    const stateReceipt = {
      schema: contract.state_schema,
      sequence: analysisSequence,
      layer: state.layer,
      module_id: state.moduleId,
      chart_radius: state.radius,
      glue_tolerance: state.epsilon,
      lineage_floor: state.tau,
      spin_noise: state.q,
      case_id: activeCaseId,
      playing: state.timer !== null
    };
    lastAnalysis = {
      schema: contract.analysis_schema,
      sequence: analysisSequence,
      state: stateReceipt,
      coordinate_source: activeCase
        ? activeCase.coordinate_source
        : "parameter_only_exact_lora_svd",
      share_uri: shareUri,
      claim_boundary: contract.claim_boundary,
      query_warnings: queryWarnings.slice(),
      chart: {
        lower_layer: chart.lowerLayer,
        upper_layer: chart.upperLayer,
        sample_count: chart.base.length
      },
      selected_sheet: {
        module_id: state.moduleId,
        label: selectedSheet.moduleLabel,
        coordinates: { x: selectedGerm.x, y: selectedGerm.y, z: selectedGerm.z, w: selectedGerm.w }
      },
      metric: clone(gluingAtlas.metric),
      topology: {
        distance_cache: clone(gluingAtlas.distanceCache),
        selected_component: clone(componentDiagnostic),
        dendrogram_mst: clone(localGlue.dendrogramMst)
      },
      direct_glued_partners: gluedPairs.map((pair) => ({
        module_id: otherModule(pair, state.moduleId),
        label: moduleLabel(otherModule(pair, state.moduleId)),
        distance: pair.distance
      })),
      closure_component: component.map((moduleId) => ({
        module_id: moduleId,
        label: moduleLabel(moduleId),
        selected: moduleId === state.moduleId,
        direct_neighbor: moduleId !== state.moduleId && Boolean(pairByPeer.get(moduleId) && pairByPeer.get(moduleId).equivalent),
        distance_from_selected: moduleId === state.moduleId ? 0 : pairByPeer.get(moduleId).distance
      })),
      closest_pair: {
        module_id: peerId,
        label: moduleLabel(peerId),
        distance: closestPair.distance,
        directly_glued: closestPair.equivalent
      },
      quotient: {
        band_count: gluingAtlas.bands.length,
        transition_count: gluingAtlas.transitions.length,
        current_transition: clone(exactTransition),
        nearest_transition: clone(nearestTransition),
        monodromy: clone(gluingAtlas.monodromy)
      },
      spin: {
        comparison_module_id: peerId,
        gauge_phase: spin.gaugePhase,
        certificate_category: spin.certificateCategory,
        beta1: spin.beta1,
        overlap_cycle_count: overlaps.length,
        w1_trivial: spin.w1Trivial
      },
      motif_catalog: {
        schema: motifCatalog.schema,
        status: motifCatalog.status,
        protocol_sha256: motifCatalog.protocol_sha256,
        scaler_sha256: motifCatalog.scaler_sha256,
        evidence_provenance: motifCatalog.evidence_provenance || "none",
        motif_count: motifCatalog.motifs.length,
        case_count: motifCatalog.cases.length,
        active_case_id: activeCaseId,
        active_motif_ids: activeMotifIds.slice(),
        human_evidence: clone(motifCatalog.human_evidence)
      },
      feedback_jobs: {
        schema: feedbackQueue.schema,
        status: feedbackQueue.status,
        protocol_sha256: feedbackQueue.protocol_sha256,
        implementation_lock_sha256: feedbackQueue.implementation_lock_sha256,
        job_count: feedbackQueue.job_count,
        training_slot_status: feedbackQueue.training_slot_status,
        automatic_authorization: feedbackQueue.automatic_authorization,
        selected_job_id: state.selectedJobId,
        selected_job_sha256: state.selectedJobId ? jobById(state.selectedJobId).authorization.job_sha256 : null
      },
      human_summary: status.textContent
    };
    analysisSequence += 1;
    analysisJson.textContent = JSON.stringify(lastAnalysis);
    svg.setAttribute("aria-label", status.textContent);
    window.dispatchEvent(new CustomEvent(contract.event, { detail: clone(lastAnalysis) }));
  }

  function stopPlayback() {
    if (state.timer !== null) window.clearInterval(state.timer);
    state.timer = null;
    playButton.textContent = "Play depth";
    playButton.setAttribute("aria-pressed", "false");
  }

  function startPlayback() {
    if (state.timer !== null) return;
    playButton.textContent = "Pause";
    playButton.setAttribute("aria-pressed", "true");
    state.timer = window.setInterval(() => {
      state.layer = (state.layer + 1) % etaleMap.layers.length;
      syncControls();
      render();
    }, 700);
  }

  function syncControls() {
    layerInput.value = String(state.layer);
    layerOutput.value = String(state.layer);
    moduleInput.value = state.moduleId;
    radiusInput.value = String(state.radius);
    radiusOutput.value = `±${state.radius}`;
    epsilonInput.value = state.epsilon.toFixed(2);
    epsilonOutput.value = state.epsilon.toFixed(2);
    tauInput.value = state.tau.toFixed(2);
    tauOutput.value = state.tau.toFixed(2);
    qInput.value = state.q.toFixed(2);
    qOutput.value = state.q.toFixed(2);
  }

  function setAgentState(patch) {
    const next = validateStatePatch(patch);
    const requestedPlaying = Object.hasOwn(next, "playing") ? next.playing : false;
    const caseWasProvided = Object.hasOwn(next, "caseId");
    const requestedCaseId = caseWasProvided ? next.caseId : activeCaseId;
    delete next.playing;
    delete next.caseId;
    stopPlayback();
    if (caseWasProvided) activateCase(requestedCaseId ? caseById(requestedCaseId) : null);
    Object.assign(state, next);
    if (requestedPlaying) startPlayback();
    syncControls();
    render();
    return clone(explorerState());
  }

  function loadCase(caseId) {
    const selected = caseById(String(caseId));
    if (!selected) throw new RangeError(`unknown case_id ${caseId}`);
    const next = validateStatePatch(selected.state || {});
    stopPlayback();
    activateCase(selected);
    Object.assign(state, next);
    syncControls();
    render();
    return clone(lastAnalysis);
  }

  function setPlaying(value) {
    if (typeof value !== "boolean") throw new TypeError("playing must be boolean");
    if (value) startPlayback(); else stopPlayback();
    render();
    return clone(explorerState());
  }

  function selectFeedbackJob(jobId) {
    if (jobId === null) {
      state.selectedJobId = null;
      render();
      return null;
    }
    const selected = jobById(String(jobId));
    if (!selected) throw new RangeError(`unknown job_id ${jobId}`);
    state.selectedJobId = selected.job_id;
    render();
    return clone(selected);
  }

  playButton.addEventListener("click", () => {
    if (state.timer !== null) {
      stopPlayback();
    } else {
      startPlayback();
    }
    render();
  });
  layerInput.addEventListener("input", () => {
    state.layer = Number(layerInput.value);
    stopPlayback();
    syncControls();
    render();
  });
  moduleInput.addEventListener("change", () => {
    state.moduleId = moduleInput.value;
    stopPlayback();
    render();
  });
  radiusInput.addEventListener("input", () => {
    state.radius = Number(radiusInput.value);
    stopPlayback();
    syncControls();
    render();
  });
  epsilonInput.addEventListener("input", () => {
    state.epsilon = Number(epsilonInput.value);
    stopPlayback();
    syncControls();
    render();
  });
  tauInput.addEventListener("input", () => {
    state.tau = Number(tauInput.value);
    stopPlayback();
    syncControls();
    render();
  });
  qInput.addEventListener("input", () => {
    state.q = Number(qInput.value);
    stopPlayback();
    syncControls();
    render();
  });
  feedbackJobRows.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-job-id]");
    if (button) selectFeedbackJob(button.dataset.jobId);
  });
  window.matchMedia("(max-width: 640px)").addEventListener("change", render);

  window.PixieEtaleExplorer = Object.freeze({
    getContract: () => clone(contract),
    getState: () => clone(explorerState()),
    setState: setAgentState,
    setPlaying: setPlaying,
    getAnalysis: () => clone(lastAnalysis),
    getShareUrl: () => stateUrl().href,
    getMotifCatalog: () => clone(motifCatalog),
    listCases: () => clone(motifCatalog.cases.map((item) => ({
      case_id: item.case_id,
      input_id: item.input_id,
      motif_ids: item.motif_ids || [],
      evidence_class: item.evidence_class || "unavailable",
      coordinate_source: item.coordinate_source || "unavailable"
    }))),
    loadCase: loadCase,
    listMotifs: () => clone(motifCatalog.motifs.map((motif) => ({
      motif_id: motif.motif_id,
      human_label: motif.human_label,
      evidence_class: motif.evidence_class
    }))),
    getMotif: (motifId) => {
      const motif = motifById(String(motifId));
      if (!motif) throw new RangeError(`unknown motif_id ${motifId}`);
      return clone(motif);
    },
    getJobQueue: () => clone(feedbackQueue),
    listJobs: () => clone(feedbackQueue.jobs.map(feedbackJobSummary)),
    getJob: (jobId) => {
      const job = jobById(String(jobId));
      if (!job) throw new RangeError(`unknown job_id ${jobId}`);
      return clone(job);
    },
    selectJob: selectFeedbackJob,
    getSelectedJob: () => clone(state.selectedJobId ? jobById(state.selectedJobId) : null)
  });

  syncControls();
  render();
})();
