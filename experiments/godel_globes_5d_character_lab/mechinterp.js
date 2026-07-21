(function () {
  "use strict";

  const api = window.PixieMechinterpAtlas;
  const atlas = api.validate(window.PixieMechinterpAtlasData);
  const svgNs = "http://www.w3.org/2000/svg";
  const layerInput = document.getElementById("atlas-layer");
  const layerOutput = document.getElementById("atlas-layer-value");
  const metricSelect = document.getElementById("atlas-metric");
  const playButton = document.getElementById("atlas-play");
  const heatmap = document.getElementById("atlas-heatmap");
  const circuitSvg = document.getElementById("circuit-svg");
  const spectrumSvg = document.getElementById("spectrum-svg");
  const trajectorySvg = document.getElementById("trajectory-svg");
  const selectedName = document.getElementById("selected-name");
  const selectedEnergy = document.getElementById("selected-energy");
  const selectedShare = document.getElementById("selected-share");
  const metricReadout = document.getElementById("metric-readout");
  const rankReadout = document.getElementById("rank-readout");
  const layerRatio = document.getElementById("layer-ratio");
  const peakReadout = document.getElementById("peak-readout");
  const status = document.getElementById("atlas-status");

  let selectedLayer = 0;
  let selectedModule = atlas.modules[0].id;
  let metricId = metricSelect.value;
  let timer = null;

  document.getElementById("claim-boundary").textContent = atlas.claim_boundary;
  layerInput.max = String(atlas.layers.length - 1);

  function svg(name, attributes = {}, text = "") {
    const node = document.createElementNS(svgNs, name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text) node.textContent = text;
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function normalizedMetric(module) {
    return Math.max(0, Math.min(1, api.metricValue(module, metricId)));
  }

  function setSelection(layer, moduleId, announce = true) {
    selectedLayer = Math.max(0, Math.min(atlas.layers.length - 1, Number(layer)));
    selectedModule = moduleId;
    layerInput.value = String(selectedLayer);
    if (announce) stopPlayback();
    render();
  }

  function buildHeatmap() {
    clear(heatmap);
    const corner = document.createElement("span");
    corner.className = "heat-corner";
    corner.textContent = "module / layer";
    heatmap.appendChild(corner);
    atlas.layers.forEach((layer) => {
      const label = document.createElement("span");
      label.className = "heat-layer";
      label.textContent = String(layer.layer);
      heatmap.appendChild(label);
    });
    atlas.modules.forEach((moduleMeta, moduleIndex) => {
      const label = document.createElement("span");
      label.className = "heat-label";
      label.textContent = moduleMeta.label;
      heatmap.appendChild(label);
      atlas.layers.forEach((layer) => {
        const module = layer.modules[moduleIndex];
        const button = document.createElement("button");
        const value = normalizedMetric(module);
        button.type = "button";
        button.className = "heat-cell";
        button.dataset.layer = String(layer.layer);
        button.dataset.module = module.id;
        button.dataset.family = module.family;
        button.style.setProperty("--intensity", String(0.12 + value * 0.88));
        button.setAttribute("aria-pressed", String(layer.layer === selectedLayer && module.id === selectedModule));
        button.setAttribute("aria-label", `Layer ${layer.layer}, ${module.label}, ${api.metrics[metricId].label}: ${api.metrics[metricId].format(module[metricId])}`);
        button.addEventListener("click", () => setSelection(layer.layer, module.id));
        heatmap.appendChild(button);
      });
    });
  }

  function renderCircuit() {
    clear(circuitSvg);
    const layer = atlas.layers[selectedLayer];
    const positions = {
      q_proj: [90, 54], k_proj: [90, 112], v_proj: [90, 170], o_proj: [310, 112],
      gate_proj: [470, 62], up_proj: [470, 162], down_proj: [650, 112]
    };
    const edges = [["q_proj", "o_proj"], ["k_proj", "o_proj"], ["v_proj", "o_proj"], ["o_proj", "gate_proj"], ["o_proj", "up_proj"], ["gate_proj", "down_proj"], ["up_proj", "down_proj"]];
    edges.forEach(([from, to]) => {
      const a = positions[from];
      const b = positions[to];
      circuitSvg.appendChild(svg("path", { class: "flow-edge", d: `M${a[0] + 35},${a[1]} C${(a[0] + b[0]) / 2},${a[1]} ${(a[0] + b[0]) / 2},${b[1]} ${b[0] - 35},${b[1]}` }));
    });
    layer.modules.forEach((module) => {
      const [x, y] = positions[module.id];
      const radius = 18 + Math.sqrt(module.layer_energy_share) * 34;
      circuitSvg.appendChild(svg("circle", { class: `flow-node ${module.family}`, cx: x, cy: y, r: radius, opacity: 0.38 + module.spectral_focus * 0.62 }));
      circuitSvg.appendChild(svg("text", { class: "flow-label", x, y: y - 4, "text-anchor": "middle" }, module.label));
      circuitSvg.appendChild(svg("text", { class: "flow-value", x, y: y + 13, "text-anchor": "middle" }, `${(module.layer_energy_share * 100).toFixed(1)}%`));
    });
    layerRatio.textContent = `MLP / attention ΔW energy ${layer.mlp_attention_ratio.toFixed(2)}×`;
  }

  function renderSpectrum(module) {
    clear(spectrumSvg);
    const left = 42;
    const bottom = 235;
    const width = 440;
    const height = 185;
    spectrumSvg.appendChild(svg("line", { class: "spectrum-baseline", x1: left, y1: bottom, x2: left + width, y2: bottom }));
    module.singular_energy_share.forEach((share, index) => {
      const barWidth = width / 8 - 10;
      const x = left + index * (width / 8) + 5;
      const barHeight = share * height;
      spectrumSvg.appendChild(svg("rect", { class: "spectrum-bar", x, y: bottom - barHeight, width: barWidth, height: barHeight, opacity: index === 0 ? 1 : 0.58 }));
      spectrumSvg.appendChild(svg("text", { class: "axis-label", x: x + barWidth / 2, y: bottom + 20, "text-anchor": "middle" }, String(index + 1)));
      spectrumSvg.appendChild(svg("text", { class: "flow-value", x: x + barWidth / 2, y: bottom - barHeight - 7, "text-anchor": "middle" }, `${(share * 100).toFixed(0)}%`));
    });
    rankReadout.textContent = `effective rank ${module.effective_rank.toFixed(2)} / 8`;
  }

  function renderTrajectory(module) {
    clear(trajectorySvg);
    const series = api.moduleSeries(atlas, module.id, metricId);
    const left = 52;
    const right = 1070;
    const top = 22;
    const bottom = 196;
    trajectorySvg.appendChild(svg("line", { class: "trajectory-axis", x1: left, y1: bottom, x2: right, y2: bottom }));
    trajectorySvg.appendChild(svg("line", { class: "trajectory-axis", x1: left, y1: top, x2: left, y2: bottom }));
    const points = series.map((item, index) => {
      const x = left + (index / (series.length - 1)) * (right - left);
      const y = bottom - item.value * (bottom - top);
      return [x, y, item];
    });
    trajectorySvg.appendChild(svg("path", { class: "trajectory-path", d: points.map((point, index) => `${index ? "L" : "M"}${point[0]},${point[1]}`).join(" ") }));
    points.forEach(([x, y, item]) => {
      const dot = svg("circle", { class: `trajectory-dot${item.layer === selectedLayer ? " selected" : ""}`, cx: x, cy: y, r: item.layer === selectedLayer ? 5 : 3 });
      dot.addEventListener("click", () => setSelection(item.layer, module.id));
      trajectorySvg.appendChild(dot);
      if (item.layer % 3 === 0 || item.layer === series.length - 1) trajectorySvg.appendChild(svg("text", { class: "axis-label", x, y: bottom + 20, "text-anchor": "middle" }, String(item.layer)));
    });
    trajectorySvg.appendChild(svg("text", { class: "axis-label", x: 12, y: 17 }, "high"));
    trajectorySvg.appendChild(svg("text", { class: "axis-label", x: 14, y: bottom + 4 }, "low"));
    const peak = series.reduce((best, item) => item.value > best.value ? item : best);
    peakReadout.textContent = `${api.metrics[metricId].label} peaks at layer ${peak.layer}`;
  }

  function render() {
    const module = api.moduleAt(atlas, selectedLayer, selectedModule);
    const summary = api.layerSummary(atlas, selectedLayer);
    layerOutput.value = String(selectedLayer);
    selectedName.textContent = `Layer ${selectedLayer} · ${module.label}`;
    selectedEnergy.textContent = module.energy.toFixed(4);
    selectedShare.textContent = `${(module.layer_energy_share * 100).toFixed(1)}%`;
    metricReadout.value = `${api.metrics[metricId].label}: ${api.metrics[metricId].format(module[metricId])}`;
    buildHeatmap();
    renderCircuit();
    renderSpectrum(module);
    renderTrajectory(module);
    status.textContent = `Layer ${selectedLayer}: strongest update target is ${summary.strongest.label}; selected ${module.label} uses ${module.effective_rank.toFixed(2)} effective modes.`;
  }

  function stopPlayback() {
    if (timer !== null) window.clearInterval(timer);
    timer = null;
    playButton.textContent = "Play depth";
    playButton.setAttribute("aria-pressed", "false");
  }

  playButton.addEventListener("click", () => {
    if (timer !== null) {
      stopPlayback();
      return;
    }
    playButton.textContent = "Pause";
    playButton.setAttribute("aria-pressed", "true");
    timer = window.setInterval(() => setSelection((selectedLayer + 1) % atlas.layers.length, selectedModule, false), 850);
  });
  layerInput.addEventListener("input", () => setSelection(Number(layerInput.value), selectedModule));
  metricSelect.addEventListener("change", () => {
    metricId = metricSelect.value;
    stopPlayback();
    render();
  });
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) stopPlayback();
  render();
})();
