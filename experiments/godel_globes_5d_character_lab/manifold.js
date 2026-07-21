(function () {
  "use strict";

  const atlasApi = window.PixieMechinterpAtlas;
  const geometry = window.PixieMechinterpManifold;
  const atlas = atlasApi.validate(window.PixieMechinterpAtlasData);
  const points = geometry.buildPoints(atlas);
  const canvas = document.getElementById("manifold-canvas");
  const context = canvas.getContext("2d");
  const modeInput = document.getElementById("manifold-mode");
  const playButton = document.getElementById("manifold-play");
  const layerInput = document.getElementById("manifold-layer");
  const layerOutput = document.getElementById("manifold-layer-value");
  const angleInput = document.getElementById("manifold-w-angle");
  const angleOutput = document.getElementById("manifold-w-value");
  const moduleInput = document.getElementById("manifold-module");
  const tauInput = document.getElementById("manifold-tau");
  const tauOutput = document.getElementById("manifold-tau-value");
  const qInput = document.getElementById("manifold-q");
  const qOutput = document.getElementById("manifold-q-value");
  const status = document.getElementById("manifold-status");
  const wKey = document.getElementById("w-key");
  const sKey = document.getElementById("s-key");
  const spinCategoryKey = document.getElementById("spin-category-key");

  const state = {
    mode: ["4d", "5d"].includes(new URLSearchParams(window.location.search).get("mode")) ? new URLSearchParams(window.location.search).get("mode") : "3d",
    layer: 13,
    moduleId: atlas.modules[0].id,
    wAngle: 55,
    tau: 0.2,
    q: 0.15,
    yaw: -0.58,
    pitch: 0.34,
    zoom: 0.88,
    dragging: false,
    pointerX: 0,
    pointerY: 0,
    hover: null,
    timer: null,
    spinResult: null
  };
  let drawWidth = 0;
  let drawHeight = 0;
  let projected = [];

  atlas.modules.forEach((module) => {
    const option = document.createElement("option");
    option.value = module.id;
    option.textContent = module.label;
    moduleInput.appendChild(option);
  });
  modeInput.value = state.mode;

  function css(name) {
    return getComputedStyle(document.body).getPropertyValue(name).trim();
  }

  function rgba(color, opacity) {
    context.globalAlpha = Math.max(0, Math.min(1, opacity));
    context.strokeStyle = color;
    context.fillStyle = color;
  }

  function projectionOptions() {
    const radians = state.wAngle * Math.PI / 180;
    return {
      mode: state.mode,
      yaw: state.yaw,
      pitch: state.pitch,
      angles: {
        xw: radians, yw: -radians * 0.58, zw: radians * 0.31,
        xs: radians * 0.74, ys: -radians * 0.43, zs: radians * 0.55
      }
    };
  }

  function canvasPoint(point, options = projectionOptions()) {
    const value = geometry.projectPoint(point, options);
    const radius = Math.min(drawWidth, drawHeight) * 0.27 * state.zoom;
    return {
      ...value,
      screenX: drawWidth / 2 + value.x * radius,
      screenY: drawHeight / 2 - value.y * radius
    };
  }

  function resizeCanvas() {
    const rectangle = canvas.getBoundingClientRect();
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    drawWidth = Math.max(320, rectangle.width);
    drawHeight = Math.max(300, rectangle.height);
    canvas.width = Math.round(drawWidth * ratio);
    canvas.height = Math.round(drawHeight * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    render();
  }

  function drawAxes() {
    const colors = [css("--series-1"), css("--series-2"), css("--series-3"), css("--series-4"), css("--series-5")];
    const axes = [
      { key: "X", end: { x: 1.25, y: 0, z: 0, w: 0 } },
      { key: "Y", end: { x: 0, y: 1.25, z: 0, w: 0 } },
      { key: "Z", end: { x: 0, y: 0, z: 1.25, w: 0 } }
    ];
    if (state.mode !== "3d") axes.push({ key: "W", end: { x: 0, y: 0, z: 0, w: 1.25, s: 0 } });
    if (state.mode === "5d") axes.push({ key: "S", end: { x: 0, y: 0, z: 0, w: 0, s: 1.25 } });
    const origin = canvasPoint({ x: 0, y: 0, z: 0, w: 0 });
    context.font = "12px ui-sans-serif, system-ui, sans-serif";
    axes.forEach((axis, index) => {
      const end = canvasPoint(axis.end);
      context.beginPath();
      context.moveTo(origin.screenX, origin.screenY);
      context.lineTo(end.screenX, end.screenY);
      rgba(colors[index], 0.72);
      context.lineWidth = 1.4;
      if (axis.key === "W" || axis.key === "S") context.setLineDash([5, 5]);
      context.stroke();
      context.setLineDash([]);
      context.fillText(axis.key, end.screenX + 6, end.screenY - 5);
    });
  }

  function weightFor(point) {
    if (state.mode === "3d") return 0.72;
    const center = (state.layer / (atlas.layers.length - 1)) * 2 - 1;
    return geometry.sliceWeight(point.w, center);
  }

  function drawTrajectories() {
    const options = projectionOptions();
    const attention = css("--series-2");
    const mlp = css("--series-3");
    const selected = css("--series-1");
    projected = points.map((point) => ({ point, ...canvasPoint(point, options) }));

    atlas.modules.forEach((module) => {
      const trace = projected.filter((entry) => entry.point.moduleId === module.id).sort((a, b) => a.point.layer - b.point.layer);
      context.beginPath();
      trace.forEach((entry, index) => index ? context.lineTo(entry.screenX, entry.screenY) : context.moveTo(entry.screenX, entry.screenY));
      rgba(module.id === state.moduleId ? selected : (trace[0].point.family === "attention" ? attention : mlp), module.id === state.moduleId ? 0.92 : 0.25);
      context.lineWidth = module.id === state.moduleId ? 2.6 : 1.1;
      context.stroke();
    });

    [...projected].sort((a, b) => a.depth - b.depth).forEach((entry) => {
      const isSelectedTrace = entry.point.moduleId === state.moduleId;
      const isSelectedLayer = entry.point.layer === state.layer;
      const isHover = state.hover === entry.point;
      const color = isSelectedTrace ? selected : (entry.point.family === "attention" ? attention : mlp);
      const opacity = weightFor(entry.point) * (isSelectedTrace ? 1 : 0.64);
      const radius = (isSelectedLayer && isSelectedTrace ? 6 : isSelectedTrace ? 3.5 : 2.4) * entry.scale;
      context.beginPath();
      context.arc(entry.screenX, entry.screenY, isHover ? radius + 3 : radius, 0, Math.PI * 2);
      rgba(color, opacity);
      context.fill();
      if (isSelectedLayer && isSelectedTrace) {
        context.globalAlpha = 0.9;
        context.strokeStyle = css("--foreground");
        context.lineWidth = 1.5;
        context.stroke();
      }
    });
    context.globalAlpha = 1;
  }

  function pairedModule(moduleId) {
    const selected = points.find((point) => point.moduleId === moduleId);
    return selected.family === "attention" ? "gate_proj" : "o_proj";
  }

  function drawSpinCycles() {
    if (state.mode !== "5d") return;
    state.spinResult = geometry.analyzeSpinLadder(points, state.moduleId, pairedModule(state.moduleId), state.tau, state.q);
    const options = projectionOptions();
    const colors = {
      forced_positive: css("--muted-foreground"),
      live_positive: css("--series-4"),
      frustrated_live: css("--series-5"),
      synthetic_negative_below_liveness: css("--series-1")
    };
    const centers = state.spinResult.cycles.map((cycle) => ({ cycle, ...canvasPoint(cycle.center, options) })).sort((a, b) => a.cycle.center.w - b.cycle.center.w);
    if (centers.length) {
      context.beginPath();
      centers.forEach((entry, index) => index ? context.lineTo(entry.screenX, entry.screenY) : context.moveTo(entry.screenX, entry.screenY));
      rgba(css("--series-5"), 0.34);
      context.lineWidth = 1.5;
      context.setLineDash([4, 5]);
      context.stroke();
      context.setLineDash([]);
    }
    centers.forEach((entry) => {
      const color = colors[entry.cycle.category];
      const radius = entry.cycle.sign < 0 ? 6 : 4.5;
      rgba(color, entry.cycle.center.w === ((state.layer / (atlas.layers.length - 1)) * 2 - 1) ? 1 : 0.82);
      context.lineWidth = 1.8;
      if (entry.cycle.category === "synthetic_negative_below_liveness") {
        context.beginPath();
        context.moveTo(entry.screenX - radius, entry.screenY - radius);
        context.lineTo(entry.screenX + radius, entry.screenY + radius);
        context.moveTo(entry.screenX + radius, entry.screenY - radius);
        context.lineTo(entry.screenX - radius, entry.screenY + radius);
        context.stroke();
      } else if (entry.cycle.sign < 0) {
        context.beginPath();
        context.moveTo(entry.screenX, entry.screenY - radius);
        context.lineTo(entry.screenX + radius, entry.screenY + radius);
        context.lineTo(entry.screenX - radius, entry.screenY + radius);
        context.closePath();
        context.fill();
      } else {
        context.beginPath();
        context.arc(entry.screenX, entry.screenY, radius, 0, Math.PI * 2);
        if (entry.cycle.live) context.fill(); else context.stroke();
      }
    });
    context.globalAlpha = 1;
  }

  function render() {
    if (!drawWidth || !drawHeight) return;
    context.clearRect(0, 0, drawWidth, drawHeight);
    drawAxes();
    drawTrajectories();
    drawSpinCycles();
    updateStatus();
  }

  function selectedPoint() {
    return points.find((point) => point.moduleId === state.moduleId && point.layer === state.layer);
  }

  function updateStatus() {
    if (state.mode === "5d" && state.spinResult) {
      const result = state.spinResult;
      const maximumBudget = result.cycles.length ? Math.max(...result.cycles.map((cycle) => cycle.angleBudget)) * 180 / Math.PI : 0;
      const distance = result.distance.mode === "exact" ? String(result.distance.value) : `${result.distance.lower}–${result.distance.upper} (bounds)`;
      const label = (moduleId) => atlas.modules.find((module) => module.id === moduleId).label;
      const words = (value) => value.replaceAll("_", " ");
      status.textContent = `${label(result.moduleA)} ↔ ${label(result.moduleB)}: gauge phase ${words(result.gaugePhase)}; liveness category ${words(result.certificateCategory)}; β₁=${result.beta1}; max angle budget ${maximumBudget.toFixed(1)}°; coboundary distance ${distance}. Retentions are a parameter-state proxy and q is synthetic.`;
      return;
    }
    const point = state.hover || selectedPoint();
    if (!point) return;
    const prefix = state.hover ? "Inspecting" : "Selected";
    status.textContent = `${prefix} layer ${point.layer} · ${point.moduleLabel}: ΔW norm ${point.energy.toFixed(4)}, top-mode share ${(point.spectralFocus * 100).toFixed(1)}%, effective rank ${point.effectiveRank.toFixed(2)}. ${state.mode === "4d" ? "W is transformer depth." : "Drag to rotate; wheel to zoom."}`;
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
    angleInput.value = String(state.wAngle);
    angleOutput.value = `${state.wAngle}°`;
    moduleInput.value = state.moduleId;
    tauInput.value = state.tau.toFixed(2);
    tauOutput.value = state.tau.toFixed(2);
    qInput.value = state.q.toFixed(2);
    qOutput.value = state.q.toFixed(2);
    angleInput.disabled = state.mode === "3d";
    tauInput.disabled = state.mode !== "5d";
    qInput.disabled = state.mode !== "5d";
    wKey.hidden = state.mode === "3d";
    sKey.hidden = state.mode !== "5d";
    spinCategoryKey.hidden = state.mode !== "5d";
  }

  playButton.addEventListener("click", () => {
    if (state.timer !== null) {
      stopPlayback();
      return;
    }
    playButton.textContent = "Pause";
    playButton.setAttribute("aria-pressed", "true");
    state.timer = window.setInterval(() => {
      state.layer = (state.layer + 1) % atlas.layers.length;
      if (state.mode === "4d") state.wAngle = (state.wAngle + 4) % 181;
      syncControls();
      render();
    }, 700);
  });
  modeInput.addEventListener("change", () => {
    state.mode = modeInput.value;
    stopPlayback();
    syncControls();
    render();
  });
  layerInput.addEventListener("input", () => {
    state.layer = Number(layerInput.value);
    stopPlayback();
    syncControls();
    render();
  });
  angleInput.addEventListener("input", () => {
    state.wAngle = Number(angleInput.value);
    stopPlayback();
    syncControls();
    render();
  });
  moduleInput.addEventListener("change", () => {
    state.moduleId = moduleInput.value;
    stopPlayback();
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

  canvas.addEventListener("pointerdown", (event) => {
    state.dragging = true;
    state.pointerX = event.clientX;
    state.pointerY = event.clientY;
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (state.dragging) {
      state.yaw += (event.clientX - state.pointerX) * 0.008;
      state.pitch = Math.max(-1.3, Math.min(1.3, state.pitch + (event.clientY - state.pointerY) * 0.008));
      state.pointerX = event.clientX;
      state.pointerY = event.clientY;
      state.hover = null;
      render();
      return;
    }
    const rectangle = canvas.getBoundingClientRect();
    const x = event.clientX - rectangle.left;
    const y = event.clientY - rectangle.top;
    const nearest = projected.reduce((best, entry) => {
      const distance = Math.hypot(entry.screenX - x, entry.screenY - y);
      return distance < best.distance ? { distance, point: entry.point } : best;
    }, { distance: 15, point: null });
    state.hover = nearest.point;
    render();
  });
  canvas.addEventListener("pointerup", (event) => {
    state.dragging = false;
    canvas.releasePointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointerleave", () => {
    if (!state.dragging) {
      state.hover = null;
      render();
    }
  });
  canvas.addEventListener("click", () => {
    if (!state.hover) return;
    state.moduleId = state.hover.moduleId;
    state.layer = state.hover.layer;
    stopPlayback();
    syncControls();
    render();
  });
  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    state.zoom = Math.max(0.58, Math.min(1.35, state.zoom * Math.exp(-event.deltaY * 0.001)));
    render();
  }, { passive: false });

  new ResizeObserver(resizeCanvas).observe(canvas);
  syncControls();
  resizeCanvas();
})();
