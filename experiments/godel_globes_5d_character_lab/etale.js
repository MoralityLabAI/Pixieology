(function () {
  "use strict";

  const atlasApi = window.PixieMechinterpAtlas;
  const geometry = window.PixieMechinterpManifold;
  const etaleApi = window.PixieMechinterpEtale;
  const atlas = atlasApi.validate(window.PixieMechinterpAtlasData);
  const points = geometry.buildPoints(atlas);
  const etaleMap = etaleApi.buildMap(points);
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

  const state = {
    layer: 13,
    moduleId: atlas.modules[0].id,
    radius: 2,
    epsilon: 0.25,
    tau: 0.2,
    q: 0.15,
    timer: null
  };

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

  function render() {
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
        x1: startX, y1: laneY, x2: endX, y2: laneY
      }));
      const lower = Math.max(chart.lowerLayer, band.startLayer);
      const upper = Math.min(chart.upperLayer, band.endLayer);
      for (let layer = lower; layer <= upper; layer += 1) {
        const first = etaleApi.germAt(etaleMap, state.moduleId, layer);
        const second = etaleApi.germAt(etaleMap, otherId, layer);
        glueGroup.appendChild(element("line", {
          class: `gluing-bridge${layer === state.layer ? " current" : ""}`,
          x1: fullX(layer), y1: sheetY(state.moduleId, first),
          x2: fullX(layer), y2: sheetY(otherId, second)
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
        "data-module": sheet.moduleId
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
        d: `M ${x} ${y - 5} L ${x + 5} ${y} L ${x} ${y + 5} L ${x - 5} ${y} Z`
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
        "data-layer": entry.layer
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
    const rows = [
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
    const exactTransition = gluingAtlas.transitions.find((transition) => transition.layer === state.layer);
    const nearestTransition = exactTransition || [...gluingAtlas.transitions].sort((first, second) => Math.abs(first.layer - state.layer) - Math.abs(second.layer - state.layer))[0];
    const changedPair = nearestTransition && [...nearestTransition.added, ...nearestTransition.removed][0];
    const transitionText = exactTransition ? `${exactTransition.kind} at this depth${changedPair ? ` (${pairLabel(changedPair)})` : ""}` : nearestTransition ? `nearest ${nearestTransition.kind} at W=${nearestTransition.layer}${changedPair ? ` (${pairLabel(changedPair)})` : ""}` : "no quotient transitions";
    const relationText = closestPair.equivalent ? "locally equivalent" : "not locally equivalent";
    status.textContent = `${selectedSheet.moduleLabel} and ${moduleLabel(peerId)} are ${relationText}: d_U=${closestPair.distance.toFixed(3)} ${closestPair.equivalent ? "≤" : ">"} ε=${state.epsilon.toFixed(2)}. The local quotient component contains ${component.length} globally distinct sheet${component.length === 1 ? "" : "s"}; ${transitionText}. Across W there are ${gluingAtlas.bands.length} gluing bands and ${gluingAtlas.transitions.length} transitions. Monodromy is unavailable because ${gluingAtlas.monodromy.reason}. S is computed on ${overlaps.length} overlap cycle${overlaps.length === 1 ? "" : "s"}; τ is a parameter-state proxy and q is synthetic.`;
  }

  function stopPlayback() {
    if (state.timer !== null) window.clearInterval(state.timer);
    state.timer = null;
    playButton.textContent = "Play depth";
    playButton.setAttribute("aria-pressed", "false");
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

  playButton.addEventListener("click", () => {
    if (state.timer !== null) {
      stopPlayback();
      return;
    }
    playButton.textContent = "Pause";
    playButton.setAttribute("aria-pressed", "true");
    state.timer = window.setInterval(() => {
      state.layer = (state.layer + 1) % etaleMap.layers.length;
      syncControls();
      render();
    }, 700);
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
  window.matchMedia("(max-width: 640px)").addEventListener("change", render);

  syncControls();
  render();
})();
