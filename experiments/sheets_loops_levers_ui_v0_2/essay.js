(function () {
  "use strict";

  const data = window.SLL_FIXTURE;
  const core = window.SLLEssay;
  const NS = "http://www.w3.org/2000/svg";
  const state = {
    chapter: core.CHAPTERS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "sheets",
    motifId: data.motifs[0].id,
    depth: 9,
    phase: 0,
    playing: false,
    showReturned: true,
  };
  let animationFrame = null;
  let animationStart = null;

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  function svgNode(name, attributes, text) {
    const node = document.createElementNS(NS, name);
    Object.entries(attributes || {}).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function clear(svg, keepAccessible = true) {
    Array.from(svg.children).forEach((child) => {
      if (!keepAccessible || !["title", "desc"].includes(child.tagName.toLowerCase())) child.remove();
    });
  }

  function path(points, close = false) {
    if (!points.length) return "";
    return `M ${points.map((point) => `${point[0].toFixed(2)} ${point[1].toFixed(2)}`).join(" L ")}${close ? " Z" : ""}`;
  }

  function project([x, y, z], scale = 160, center = [450, 265]) {
    return [center[0] + scale * (0.82 * x - 0.5 * y), center[1] + scale * (0.25 * x + 0.42 * y - 0.82 * z)];
  }

  function matrixVector(matrix, vector) {
    return core.matVec(matrix, vector);
  }

  function renderSheets(targetSvg = $("#sheets-svg"), compact = false) {
    clear(targetSvg, !compact);
    const width = compact ? 260 : 900;
    const height = compact ? 150 : 520;
    const margin = compact ? { left: 13, right: 13, top: 15, bottom: 18 } : { left: 66, right: 30, top: 38, bottom: 62 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const xScale = (layer) => margin.left + (layer / 27) * plotWidth;
    const allZ = data.motifs.flatMap((motif) => motif.depth_points.map((point) => point.z));
    const zMin = Math.min(...allZ) - 0.07;
    const zMax = Math.max(...allZ) + 0.07;
    const yScale = (z) => margin.top + (1 - (z - zMin) / (zMax - zMin)) * plotHeight;
    const partners = core.gluingPartners(data, state.motifId, state.depth, data.etale.window_radius, data.etale.epsilon);
    const partnerIds = new Set(partners.map((item) => item.id));
    const windowLow = Math.max(0, state.depth - data.etale.window_radius);
    const windowHigh = Math.min(27, state.depth + data.etale.window_radius);

    targetSvg.appendChild(svgNode("rect", {
      x: xScale(windowLow), y: margin.top, width: Math.max(2, xScale(windowHigh) - xScale(windowLow)), height: plotHeight, class: "chart-window",
    }));
    if (!compact) {
      [0, 9, 18, 27].forEach((layer) => {
        targetSvg.appendChild(svgNode("line", { x1: xScale(layer), x2: xScale(layer), y1: margin.top, y2: height - margin.bottom, class: "grid" }));
        targetSvg.appendChild(svgNode("text", { x: xScale(layer), y: height - 31, "text-anchor": "middle", class: "axis-label" }, String(layer)));
      });
      targetSvg.appendChild(svgNode("text", { x: width / 2, y: height - 9, "text-anchor": "middle", class: "axis-label" }, "ordered depth W (layer)"));
      targetSvg.appendChild(svgNode("text", { x: 18, y: height / 2, transform: `rotate(-90 18 ${height / 2})`, "text-anchor": "middle", class: "axis-label" }, "display section z"));
    }

    data.motifs.forEach((motif) => {
      const points = motif.depth_points.map((point) => [xScale(point.layer), yScale(point.z)]);
      const classes = ["sheet"];
      if (motif.id === state.motifId) classes.push("selected");
      else if (partnerIds.has(motif.id)) classes.push("partner");
      const line = svgNode("path", { d: path(points), class: classes.join(" "), "data-motif": motif.id });
      if (!compact) line.appendChild(svgNode("title", {}, `${motif.label} sheet`));
      targetSvg.appendChild(line);
    });

    if (!compact) {
      const selected = core.motifById(data, state.motifId);
      const selectedPoint = selected.depth_points[state.depth];
      partners.forEach((partner, index) => {
        const partnerMotif = core.motifById(data, partner.id);
        const partnerPoint = partnerMotif.depth_points[state.depth];
        targetSvg.appendChild(svgNode("line", {
          x1: xScale(state.depth), y1: yScale(selectedPoint.z), x2: xScale(state.depth), y2: yScale(partnerPoint.z), class: "epsilon-link",
        }));
        targetSvg.appendChild(svgNode("text", {
          x: xScale(state.depth) + 9, y: Math.min(yScale(selectedPoint.z), yScale(partnerPoint.z)) - 9 - index * 16, class: "axis-label",
        }, `glues to ${partnerMotif.label} · d=${partner.distance.toFixed(3)}`));
      });
      targetSvg.appendChild(svgNode("line", { x1: xScale(state.depth), x2: xScale(state.depth), y1: margin.top, y2: height - margin.bottom, stroke: "var(--accent)", "stroke-width": 2 }));
      targetSvg.appendChild(svgNode("text", { x: xScale(state.depth), y: 24, "text-anchor": "middle", class: "axis-label" }, `U = [${windowLow}, ${windowHigh}]`));
    }
    return partners;
  }

  function renderLoops(targetSvg = $("#loops-svg"), compact = false) {
    clear(targetSvg, !compact);
    const motif = core.motifById(data, state.motifId);
    const center = compact ? [130, 76] : [450, 260];
    const scale = compact ? 80 : 170;
    const projected = motif.loop_points.map((point) => project([point.x, point.y, point.z], scale, center));
    const ground = motif.loop_points.map((point) => project([point.x, point.y, -0.48], scale, center));
    targetSvg.appendChild(svgNode("path", { d: path(ground), class: compact ? "loop-shadow" : "loop-shadow" }));
    targetSvg.appendChild(svgNode("path", { d: path(projected), class: "loop-path" }));
    const position = core.loopPoint(motif, state.phase);
    const projectedPosition = project([position.x, position.y, position.z], scale, center);
    const frame = core.transportedFrame(motif, state.phase);
    const frameLength = compact ? 0.28 : 0.32;

    function drawFrame(vectors, classSuffix, opacity) {
      vectors.forEach((vector, index) => {
        const endpoint = [position.x + vector[0] * frameLength, position.y + vector[1] * frameLength, position.z + vector[2] * frameLength];
        const projectedEnd = project(endpoint, scale, center);
        targetSvg.appendChild(svgNode("line", {
          x1: projectedPosition[0], y1: projectedPosition[1], x2: projectedEnd[0], y2: projectedEnd[1],
          class: `frame-axis ${["x", "y", "z"][index]} ${classSuffix}`, opacity,
        }));
      });
    }
    if (!compact) drawFrame([[1, 0, 0], [0, 1, 0], [0, 0, 1]], "frame-start", 1);
    drawFrame(frame, "", 1);
    targetSvg.appendChild(svgNode("circle", { cx: projectedPosition[0], cy: projectedPosition[1], r: compact ? 4 : 8, class: "moving-point" }));
    if (!compact) {
      targetSvg.appendChild(svgNode("text", { x: 34, y: 42, class: "axis-label" }, "fixed camera · transported SO(3) frame"));
      targetSvg.appendChild(svgNode("text", { x: projectedPosition[0] + 16, y: projectedPosition[1] - 15, class: "axis-label" }, `t = ${(state.phase * 100).toFixed(0)}%`));
      const start = projected[0];
      targetSvg.appendChild(svgNode("text", { x: start[0] + 12, y: start[1] + 20, class: "axis-label" }, "basepoint"));
    }
  }

  function ellipsoidPoints(motif, returned, latitude, samples = 65) {
    const values = motif.control.eigenvalues.map((value) => Math.sqrt(Math.max(0, value)));
    const vectors = motif.control.eigenvectors;
    const output = [];
    for (let index = 0; index < samples; index += 1) {
      const longitude = (index / (samples - 1)) * Math.PI * 2;
      const local = [
        values[0] * Math.cos(latitude) * Math.cos(longitude),
        values[1] * Math.cos(latitude) * Math.sin(longitude),
        values[2] * Math.sin(latitude),
      ];
      let world = [0, 0, 0];
      vectors.forEach((vector, axis) => {
        world = world.map((value, dimension) => value + vector[dimension] * local[axis]);
      });
      if (returned) world = matrixVector(motif.holonomy.matrix, world);
      output.push(world);
    }
    return output;
  }

  function meridianPoints(motif, returned, longitude, samples = 45) {
    const values = motif.control.eigenvalues.map((value) => Math.sqrt(Math.max(0, value)));
    const vectors = motif.control.eigenvectors;
    const points = [];
    for (let index = 0; index < samples; index += 1) {
      const latitude = -Math.PI / 2 + (index / (samples - 1)) * Math.PI;
      const local = [
        values[0] * Math.cos(latitude) * Math.cos(longitude),
        values[1] * Math.cos(latitude) * Math.sin(longitude),
        values[2] * Math.sin(latitude),
      ];
      let world = [0, 0, 0];
      vectors.forEach((vector, axis) => { world = world.map((value, dimension) => value + vector[dimension] * local[axis]); });
      if (returned) world = matrixVector(motif.holonomy.matrix, world);
      points.push(world);
    }
    return points;
  }

  function renderEllipsoid(targetSvg = $("#levers-svg"), compact = false) {
    clear(targetSvg, !compact);
    const motif = core.motifById(data, state.motifId);
    const center = compact ? [130, 78] : [450, 270];
    const scale = compact ? 63 : 150;

    function drawSet(returned, secondary) {
      [-0.62, 0, 0.62].forEach((latitude, index) => {
        const points = ellipsoidPoints(motif, returned, latitude).map((point) => project(point, scale, center));
        targetSvg.appendChild(svgNode("path", { d: path(points), class: `${index === 1 ? "ellipsoid" : "ellipsoid-grid"}${secondary ? " secondary" : ""}` }));
      });
      [0, Math.PI / 2].forEach((longitude) => {
        const points = meridianPoints(motif, returned, longitude).map((point) => project(point, scale, center));
        targetSvg.appendChild(svgNode("path", { d: path(points), class: `ellipsoid-grid${secondary ? " secondary" : ""}` }));
      });
    }

    if (state.showReturned) drawSet(true, true);
    drawSet(false, false);
    targetSvg.appendChild(svgNode("circle", { cx: center[0], cy: center[1], r: compact ? 3 : 5, class: "origin" }));
    if (!compact) {
      targetSvg.appendChild(svgNode("text", { x: 35, y: 42, class: "axis-label" }, "W registered actions"));
      if (state.showReturned) targetSvg.appendChild(svgNode("text", { x: 35, y: 66, fill: "var(--teal)", class: "axis-label" }, "HWHᵀ after loop"));
      const values = motif.control.eigenvalues.map((value) => value.toFixed(2)).join(" · ");
      targetSvg.appendChild(svgNode("text", { x: 450, y: 494, "text-anchor": "middle", class: "axis-label" }, `eigenvalues λ = ${values}`));
    }
  }

  function updateReadings() {
    const motif = core.motifById(data, state.motifId);
    const partners = core.gluingPartners(data, state.motifId, state.depth, data.etale.window_radius, data.etale.epsilon);
    $("#sheets-reading").innerHTML = partners.length
      ? `<strong>${motif.label} locally glues to ${partners.map((item) => item.label).join(", ")}.</strong><span class="metric-line">The raw ε-neighborhood is pairwise; connected components would be its transitive closure.</span>`
      : `<strong>${motif.label} remains a distinct sheet in this chart.</strong><span class="metric-line">No target enters the ε-neighborhood across the five-layer window.</span>`;
    $("#loops-reading").innerHTML = `<strong>${motif.holonomy.angle_degrees}° residual frame rotation.</strong><span class="metric-line">Association return cosine ${motif.holonomy.association_return_cosine.toFixed(3)} over S¹. This is defined because the path closes.</span>`;
    const controlStatus = motif.control.normalized_margin > 0.05 ? "resolved on this exact fixture" : "abstain if B were measured at this margin";
    $("#levers-reading").innerHTML = `<strong>Reachable rank ${motif.control.rank}/3 · ${controlStatus}.</strong><span class="metric-line">Normalized margin ${motif.control.normalized_margin.toFixed(3)} · loop/control coupling κ ${motif.control.holonomy_coupling.toFixed(3)}.</span>`;
  }

  function renderSynthesis() {
    renderSheets($("#synthesis-sheets"), true);
    renderLoops($("#synthesis-loops"), true);
    renderEllipsoid($("#synthesis-levers"), true);
    const motif = core.motifById(data, state.motifId);
    const partners = core.gluingPartners(data, state.motifId, state.depth, data.etale.window_radius, data.etale.epsilon);
    $("#syn-sheet-copy").textContent = partners.length ? `At layer ${state.depth}, ${motif.label} overlaps ${partners.map((item) => item.label).join(", ")}.` : `At layer ${state.depth}, ${motif.label} stays locally distinct.`;
    $("#syn-loop-copy").textContent = `The transported frame returns ${motif.holonomy.angle_degrees}° rotated; cosine ${motif.holonomy.association_return_cosine.toFixed(3)}.`;
    $("#syn-lever-copy").textContent = `Registered actions reach rank ${motif.control.rank}/3 with coupling κ=${motif.control.holonomy_coupling.toFixed(3)}.`;
    $("#candidate-claim").textContent = partners.length
      ? `${motif.label}'s local depth convergence is a candidate predictor of shared transported control geometry—not yet evidence that the motifs are functionally isomorphic.`
      : `${motif.label}'s distinct depth chart, loop transport, and reachable action fiber form a coordinated mechanism description—not yet a causal identity claim.`;
    $("#next-test").textContent = "capture the same registered subspace on held-out prompts, intervene along estimated eigenvectors, and test whether the depth overlap predicts returned effects better than matched controls.";
  }

  function updateSnapshot() {
    $("#agent-json").textContent = JSON.stringify(core.snapshot(data, state), null, 2);
  }

  function renderAll() {
    const motif = core.motifById(data, state.motifId);
    $("#motif-token").textContent = `${motif.id} · fixture ${data.fixture_sha256.slice(0, 10)}`;
    $("#depth-output").textContent = state.depth;
    $("#phase-output").textContent = `${Math.round(state.phase * 100)}%`;
    renderSheets();
    renderLoops();
    renderEllipsoid();
    updateReadings();
    renderSynthesis();
    updateSnapshot();
  }

  function setChapter(chapter, updateHash = true) {
    if (!core.CHAPTERS.includes(chapter)) chapter = "sheets";
    state.chapter = chapter;
    $$("[role=tab]").forEach((tab) => {
      const active = tab.dataset.chapter === chapter;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    $$(".chapter").forEach((panel) => {
      const active = panel.id === `chapter-${chapter}`;
      panel.hidden = !active;
      panel.classList.toggle("is-active", active);
    });
    if (updateHash) history.replaceState(null, "", `#${chapter}`);
    updateSnapshot();
  }

  function stopAnimation(finished) {
    if (animationFrame) cancelAnimationFrame(animationFrame);
    animationFrame = null;
    animationStart = null;
    state.playing = false;
    $("#play-loop").setAttribute("aria-pressed", "false");
    $("#play-loop").textContent = finished ? "Replay one circuit" : "Play one circuit";
  }

  function animateLoop(timestamp) {
    if (!state.playing) return;
    if (animationStart === null) animationStart = timestamp;
    const elapsed = timestamp - animationStart;
    state.phase = Math.min(1, elapsed / 5000);
    $("#phase-range").value = Math.round(state.phase * 1000);
    $("#phase-output").textContent = `${Math.round(state.phase * 100)}%`;
    renderLoops();
    renderSynthesis();
    updateSnapshot();
    if (state.phase >= 1) stopAnimation(true);
    else animationFrame = requestAnimationFrame(animateLoop);
  }

  data.motifs.forEach((motif) => {
    const option = document.createElement("option");
    option.value = motif.id;
    option.textContent = `${motif.label} · ${motif.id}`;
    $("#motif-select").appendChild(option);
  });
  $("#motif-select").value = state.motifId;

  $("#motif-select").addEventListener("change", (event) => { state.motifId = event.target.value; renderAll(); });
  $("#depth-range").addEventListener("input", (event) => { state.depth = Number(event.target.value); renderAll(); });
  $("#phase-range").addEventListener("input", (event) => { stopAnimation(false); state.phase = Number(event.target.value) / 1000; renderAll(); });
  $("#returned-toggle").addEventListener("change", (event) => { state.showReturned = event.target.checked; renderEllipsoid(); renderSynthesis(); });
  $("#play-loop").addEventListener("click", () => {
    if (state.playing) { stopAnimation(false); return; }
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      state.phase = state.phase === 1 ? 0 : 1;
      $("#phase-range").value = state.phase * 1000;
      renderAll();
      $("#play-loop").textContent = state.phase === 1 ? "Reset circuit" : "Complete circuit";
      return;
    }
    if (state.phase >= 1) state.phase = 0;
    state.playing = true;
    $("#play-loop").setAttribute("aria-pressed", "true");
    $("#play-loop").textContent = "Pause";
    animationFrame = requestAnimationFrame(animateLoop);
  });

  $$("[role=tab]").forEach((tab) => tab.addEventListener("click", () => setChapter(tab.dataset.chapter)));
  window.addEventListener("hashchange", () => setChapter(location.hash.slice(1), false));
  document.addEventListener("keydown", (event) => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    const direct = { "1": "sheets", "2": "loops", "3": "levers", "4": "synthesis" }[event.key];
    let next = direct;
    const index = core.CHAPTERS.indexOf(state.chapter);
    if (event.key === "ArrowRight") next = core.CHAPTERS[(index + 1) % core.CHAPTERS.length];
    if (event.key === "ArrowLeft") next = core.CHAPTERS[(index + core.CHAPTERS.length - 1) % core.CHAPTERS.length];
    if (next) { event.preventDefault(); setChapter(next); $(`#tab-${next}`).focus(); }
  });

  function setAgentPanel(open) {
    $("#agent-panel").hidden = !open;
    $("#agent-toggle").setAttribute("aria-expanded", String(open));
    if (open) { updateSnapshot(); $("#agent-close").focus(); }
    else $("#agent-toggle").focus();
  }
  $("#agent-toggle").addEventListener("click", () => setAgentPanel($("#agent-panel").hidden));
  $("#agent-close").addEventListener("click", () => setAgentPanel(false));
  $("#copy-snapshot").addEventListener("click", async () => {
    await navigator.clipboard.writeText($("#agent-json").textContent);
    $("#copy-snapshot").textContent = "Copied";
    setTimeout(() => { $("#copy-snapshot").textContent = "Copy JSON"; }, 1200);
  });

  setChapter(state.chapter, false);
  renderAll();
})();
