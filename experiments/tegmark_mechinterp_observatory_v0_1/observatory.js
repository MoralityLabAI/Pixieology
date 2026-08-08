(function () {
  "use strict";

  const data = window.TEGMARK_OBSERVATORY_DATA;
  const core = window.TegmarkObservatoryCore;
  if (!data || !core) throw new Error("Observatory data or core is unavailable.");

  const state = {
    lens: Object.hasOwn(core.LENS_META, location.hash.slice(1)) ? location.hash.slice(1) : "bimt",
    selection: core.defaultSelection(data)
  };

  const els = {
    tabs: [...document.querySelectorAll("[data-lens]")],
    kicker: document.querySelector("#lens-kicker"),
    title: document.querySelector("#lens-title"),
    question: document.querySelector("#lens-question"),
    source: document.querySelector("#paper-source"),
    controls: document.querySelector("#controls"),
    visual: document.querySelector("#visual"),
    inspector: document.querySelector("#inspector"),
    snapshot: document.querySelector("#agent-snapshot"),
    copy: document.querySelector("#copy-snapshot"),
    fixture: document.querySelector("#fixture-id")
  };

  const fmt = n => {
    if (typeof n !== "number") return n;
    if (n !== 0 && Math.abs(n) < 1e-5) return n.toExponential(2);
    return n.toLocaleString(undefined, {maximumFractionDigits: 6});
  };
  const option = (value, label, selected) => `<option value="${value}"${String(value) === String(selected) ? " selected" : ""}>${label}</option>`;
  const dl = entries => `<dl>${entries.map(([k, v, cls = ""]) => `<dt>${k}</dt><dd class="${cls}">${v}</dd>`).join("")}</dl>`;

  function controlSelect(id, label, values, current, labels = v => v) {
    return `<div class="control"><label for="${id}">${label}</label><select id="${id}">${values.map(v => option(v, labels(v), current)).join("")}</select></div>`;
  }

  function segmented(id, label, choices, current) {
    return `<div class="control"><label>${label}</label><div class="segmented" id="${id}">${choices.map(([value, text]) => `<button type="button" data-value="${value}" aria-pressed="${value === current}">${text}</button>`).join("")}</div></div>`;
  }

  function bindSelect(id, key, numeric = false) {
    document.querySelector(`#${id}`).addEventListener("change", event => {
      state.selection[key] = numeric ? Number(event.target.value) : event.target.value;
      render();
    });
  }

  function bindSegmented(id, key) {
    document.querySelectorAll(`#${id} button`).forEach(button => button.addEventListener("click", () => {
      state.selection[key] = button.dataset.value;
      render();
    }));
  }

  function renderBimt() {
    const lens = data.lenses.bimt;
    const method = lens.methods.find(m => m.id === state.selection.bimtMethod);
    els.controls.innerHTML = controlSelect("bimt-method", "Training condition", lens.methods.map(m => m.id), state.selection.bimtMethod, id => lens.methods.find(m => m.id === id).label);
    bindSelect("bimt-method", "bimtMethod");

    const nodeById = Object.fromEntries(method.nodes.map(n => [n.id, n]));
    const edges = method.edges.map((edge, index) => {
      const a = nodeById[edge.source], b = nodeById[edge.target];
      const color = edge.weight >= 0 ? "var(--green)" : "var(--coral)";
      const width = 1.2 + Math.abs(edge.weight) * 5;
      const selected = index === state.selection.bimtEdge ? " selected" : "";
      return `<path class="edge${selected}" tabindex="0" role="button" aria-label="${edge.source} to ${edge.target}; weight ${edge.weight}" data-edge="${index}" d="M ${a.x*760} ${a.y*410} C ${(a.x+.13)*760} ${a.y*410}, ${(b.x-.13)*760} ${b.y*410}, ${b.x*760} ${b.y*410}" stroke="${color}" stroke-width="${width}" opacity="${0.35 + Math.abs(edge.weight)*0.6}"/>`;
    }).join("");
    const nodes = method.nodes.map(n => `<g class="node" transform="translate(${n.x*760},${n.y*410})"><circle r="18"/><text>${n.label}</text></g>`).join("");
    els.visual.innerHTML = `<svg viewBox="0 0 760 450" role="img" aria-label="Signed neural connectivity graph for ${method.label}"><text class="layer-label" x="28" y="20">input</text><text class="layer-label" x="270" y="20">hidden 1</text><text class="layer-label" x="500" y="20">hidden 2</text><text class="layer-label" x="690" y="20">output</text>${edges}${nodes}</svg>`;
    els.visual.querySelectorAll("[data-edge]").forEach(edge => {
      const choose = () => { state.selection.bimtEdge = Number(edge.dataset.edge); render(); };
      edge.addEventListener("click", choose);
      edge.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(); } });
    });
    const edge = state.selection.bimtEdge == null ? null : method.edges[state.selection.bimtEdge];
    els.inspector.innerHTML = `<h3>${method.label}</h3>${dl([
      ["task loss", fmt(method.task_loss), "metric-large"],
      ["geometry-weighted connection cost", fmt(method.connection_cost)],
      ["active edges", method.active_edges],
      ["selected edge", edge ? `${edge.source} → ${edge.target}` : "Select an edge"],
      ["weight", edge ? fmt(edge.weight) : "—"],
      ["synthetic ablation Δ loss", edge ? fmt(edge.ablation_delta) : "—"]
    ])}`;
  }

  function phaseGrid({xValues, yValues, cells, xKey, yKey, classKey, selected, onCell, xLabel, yLabel, describe}) {
    const columns = `5.5rem repeat(${xValues.length}, minmax(6rem, 1fr))`;
    const header = `<span></span>${xValues.map(v => `<span class="axis-label">${xLabel(v)}</span>`).join("")}`;
    const rows = yValues.map(y => `<span class="axis-label">${yLabel(y)}</span>${xValues.map(x => {
      const cell = cells.find(c => String(c[xKey]) === String(x) && String(c[yKey]) === String(y));
      const active = selected(cell);
      return `<button type="button" class="phase-cell ${cell[classKey]}" aria-pressed="${active}" data-x="${x}" data-y="${y}">${cell[classKey]}<small>${describe(cell)}</small></button>`;
    }).join("")}`).join("");
    els.visual.innerHTML = `<div class="phase-grid" style="grid-template-columns:${columns}">${header}${rows}</div>`;
    els.visual.querySelectorAll(".phase-cell").forEach(button => button.addEventListener("click", () => onCell(button.dataset.x, button.dataset.y)));
  }

  function renderClockPizza() {
    const lens = data.lenses.clock_pizza;
    els.controls.innerHTML = `<div class="legend"><span><i class="legend-swatch pizza"></i>Pizza</span><span><i class="legend-swatch hybrid"></i>Hybrid</span><span><i class="legend-swatch clock"></i>Clock</span></div>`;
    phaseGrid({
      xValues: lens.widths, yValues: lens.attention_rates.slice().reverse(), cells: lens.cells,
      xKey: "width", yKey: "attention_rate", classKey: "algorithm",
      selected: c => c.width === state.selection.clockWidth && c.attention_rate === state.selection.clockAttention,
      onCell: (x, y) => { state.selection.clockWidth = Number(x); state.selection.clockAttention = Number(y); render(); },
      xLabel: v => `width ${v}`, yLabel: v => `α ${v}`,
      describe: c => `${(c.validation_accuracy*100).toFixed(1)}% acc.`
    });
    const cell = core.findClockCell(data, state.selection);
    els.inspector.innerHTML = `<h3>${cell.algorithm} regime</h3>${dl([
      ["attention rate α", fmt(cell.attention_rate)], ["width", cell.width],
      ["gradient symmetricity", fmt(cell.gradient_symmetricity)],
      ["distance irrelevance q", fmt(cell.distance_irrelevance_q)],
      ["circularity", fmt(cell.circularity)],
      ["validation accuracy", `${(cell.validation_accuracy*100).toFixed(1)}%`, "metric-large"]
    ])}<p class="warning">Behavior stays nearly fixed; the algorithm label changes.</p>`;
  }

  function renderHypernetwork() {
    const lens = data.lenses.hypernetwork;
    els.controls.innerHTML = segmented("hyper-view", "View", [["phase", "Algorithm phase"], ["generalization", "Generalization"]], state.selection.hyperView);
    bindSegmented("hyper-view", "hyperView");
    if (state.selection.hyperView === "phase") {
      phaseGrid({
        xValues: lens.steps, yValues: lens.betas.slice().reverse(), cells: lens.cells,
        xKey: "step", yKey: "beta", classKey: "algorithm",
        selected: c => c.step === state.selection.hyperStep && c.beta === state.selection.hyperBeta,
        onCell: (x, y) => { state.selection.hyperStep = Number(x); state.selection.hyperBeta = Number(y); render(); },
        xLabel: v => `${v} steps`, yLabel: v => `β ${v}`,
        describe: c => `D ${c.double_sidedness}`
      });
    } else {
      const dims = [2,4,8,16];
      const maxLoss = Math.max(...lens.generalization.map(c => c.loss));
      const columns = `5rem repeat(${dims.length}, minmax(5.5rem, 1fr))`;
      const header = `<span></span>${dims.map(v => `<span class="axis-label">hidden ${v}</span>`).join("")}`;
      const rows = dims.slice().reverse().map(input => `<span class="axis-label">input ${input}</span>${dims.map(hidden => {
        const c = lens.generalization.find(v => v.input_dim === input && v.hidden_dim === hidden);
        const alpha = 0.18 + 0.74*(1-c.loss/maxLoss);
        return `<div class="phase-cell" style="background:rgba(116,237,176,${alpha})">loss<small>${c.loss}</small></div>`;
      }).join("")}`).join("");
      els.visual.innerHTML = `<div class="phase-grid" style="grid-template-columns:${columns}">${header}${rows}</div>`;
    }
    const cell = core.findHyperCell(data, state.selection);
    els.inspector.innerHTML = `<h3>${cell.algorithm}</h3>${dl([
      ["β", fmt(cell.beta)], ["training step", cell.step],
      ["double-sidedness", fmt(cell.double_sidedness)],
      ["strongest connection", fmt(cell.strongest_connection)],
      ["seed dependence", fmt(cell.seed_dependence)],
      ["current view", state.selection.hyperView]
    ])}`;
  }

  function renderMips() {
    const lens = data.lenses.mips;
    const item = lens.cases.find(c => c.id === state.selection.mipsCase);
    els.controls.innerHTML = controlSelect("mips-case", "Compiler case", lens.cases.map(c => c.id), state.selection.mipsCase, id => lens.cases.find(c => c.id === id).label);
    bindSelect("mips-case", "mipsCase");
    if (state.selection.mipsStage >= item.stages.length) state.selection.mipsStage = 0;
    const stages = item.stages.map((stage, index) => `<button type="button" class="stage${stage.includes("unavailable") || stage.includes("failed") ? " unavailable" : ""}" data-stage="${index}" aria-pressed="${state.selection.mipsStage === index}"><small>0${index+1}</small><br>${stage}</button>`).join("");
    const points = item.state_points.map(p => `<g transform="translate(${190+p.x*120},${115-p.y*150})"><circle r="9" fill="${p.code === "?" ? "var(--coral)" : "var(--green)"}"/><text x="13" y="4" fill="var(--text)" font-size="13">${p.code}</text></g>`).join("");
    els.visual.innerHTML = `<div class="stage-lane">${stages}</div><div class="compiler-body"><svg viewBox="0 0 380 240" role="img" aria-label="Synthetic latent state points and integer codes"><line x1="20" y1="115" x2="360" y2="115" stroke="var(--line)"/><line x1="190" y1="20" x2="190" y2="220" stroke="var(--line)"/>${points}</svg><pre class="code">${item.python}</pre></div>`;
    els.visual.querySelectorAll("[data-stage]").forEach(button => button.addEventListener("click", () => { state.selection.mipsStage = Number(button.dataset.stage); render(); }));
    const failure = item.status.startsWith("failed");
    els.inspector.innerHTML = `<h3>${item.label}</h3>${dl([
      ["status", item.status, failure ? "failure" : "metric-large"],
      ["selected stage", item.stages[state.selection.mipsStage]],
      ["integer code", item.integer_code],
      ["symbolic law", item.symbolic_law],
      ["verification", item.verification]
    ])}`;
  }

  function linePath(points, x, y) {
    return points.map((p, i) => `${i ? "L" : "M"} ${x(p).toFixed(2)} ${y(p).toFixed(2)}`).join(" ");
  }

  function renderSid() {
    const lens = data.lenses.sid;
    const item = lens.systems.find(s => s.id === state.selection.sidSystem);
    els.controls.innerHTML = controlSelect("sid-system", "Dynamics", lens.systems.map(s => s.id), state.selection.sidSystem, id => lens.systems.find(s => s.id === id).label) + segmented("sid-view", "View", [["spectrum", "Nullspace"], ["trajectories", "Trajectory constancy"]], state.selection.sidView);
    bindSelect("sid-system", "sidSystem"); bindSegmented("sid-view", "sidView");
    if (state.selection.sidView === "spectrum") {
      const max = Math.log10(Math.max(...item.singular_values)+1);
      const bars = item.singular_values.map((v, i) => {
        const h = Math.max(2, 230 * Math.log10(v+1)/max);
        return `<g><rect x="${50+i*92}" y="${280-h}" width="54" height="${h}" fill="${v < 1e-5 ? "var(--green)" : "var(--blue)"}"/><text x="${77+i*92}" y="300" text-anchor="middle" fill="var(--muted)" font-size="11">σ${i+1}</text><text x="${77+i*92}" y="${270-h}" text-anchor="middle" fill="var(--text)" font-size="10">${v}</text></g>`;
      }).join("");
      const coeffs = item.basis.map((basis, i) => `<div class="coefficient">${basis}<strong>${item.sparse_coefficients[i]}</strong></div>`).join("");
      els.visual.innerHTML = `<svg viewBox="0 0 640 320" role="img" aria-label="Singular spectrum of directional derivative matrix">${bars}</svg><div class="coefficients">${coeffs}</div>`;
    } else if (!item.trajectories.length) {
      els.visual.innerHTML = `<p class="failure">No invariant trajectory is available: this negative control has no nullspace in the proposed basis.</p>`;
    } else {
      const all = item.trajectories.flatMap(t => t.points);
      const maxT = Math.max(...all.map(p => p.t));
      const minH = Math.min(...all.map(p => p.H)), maxH = Math.max(...all.map(p => p.H));
      const spread = Math.max(0.001, maxH-minH);
      const x = p => 45 + p.t/maxT*540;
      const y = p => 260 - (p.H-minH)/spread*190;
      const colors = ["var(--green)", "var(--amber)", "var(--blue)"];
      const paths = item.trajectories.map((t,i) => `<path d="${linePath(t.points,x,y)}" fill="none" stroke="${colors[i]}" stroke-width="3"/>`).join("");
      els.visual.innerHTML = `<svg viewBox="0 0 640 310" role="img" aria-label="Invariant value over time for three trajectories"><line x1="45" y1="260" x2="600" y2="260" stroke="var(--line)"/><line x1="45" y1="40" x2="45" y2="260" stroke="var(--line)"/>${paths}<text x="560" y="290" fill="var(--muted)">time</text><text x="12" y="38" fill="var(--muted)">H</text></svg>`;
    }
    els.inspector.innerHTML = `<h3>${item.label}</h3>${dl([
      ["dynamics", item.dynamics], ["basis", item.basis.join(", ")],
      ["nullity", item.nullity], ["independent rank", item.independent_rank],
      ["sparse law", item.law, item.nullity ? "metric-large" : "failure"],
      ["max residual", fmt(item.max_residual)]
    ])}`;
  }

  function renderOpenProblems() {
    const lens = data.lenses.open_problems;
    const goal = lens.goals.find(g => g.id === state.selection.claimGoal);
    els.controls.innerHTML = controlSelect("claim-goal", "Intended use", lens.goals.map(g => g.id), state.selection.claimGoal, id => lens.goals.find(g => g.id === id).label);
    bindSelect("claim-goal", "claimGoal");
    const route = goal.evidence_route.map((step, i) => `<div class="route-step"><span class="index">0${i+1}</span><strong>${step}</strong><span class="state">missing</span></div>`).join("");
    const axes = lens.axes.map(axis => `<div class="axis-row"><span>${axis.label}</span><div class="axis-track"><div class="axis-fill" style="width:${axis.value*100}%"></div></div><span>${Math.round(axis.value*100)}%</span></div>`).join("");
    els.visual.innerHTML = `<div class="claim-route">${route}</div><div class="axes">${axes}</div>`;
    els.inspector.innerHTML = `<h3>${goal.label} route</h3>${dl([
      ["interpretability pipeline", lens.pipeline.join(" → ")],
      ["required evidence", goal.evidence_route.length + " steps"],
      ["fixture evidence satisfied", "0 steps", "failure"],
      ["strongest validation rung", lens.validation_ladder.at(-1)],
      ["claim status", "interaction prototype only", "warning"]
    ])}`;
  }

  function updateSnapshot() {
    const snap = core.snapshot(data, state.lens, state.selection);
    els.snapshot.textContent = JSON.stringify(snap, null, 2);
    return snap;
  }

  function render() {
    const meta = core.LENS_META[state.lens];
    els.tabs.forEach(tab => {
      const active = tab.dataset.lens === state.lens;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    els.kicker.textContent = meta.kicker;
    els.title.textContent = meta.title;
    els.question.textContent = meta.question;
    els.source.href = data.sources[state.lens];
    els.visual.setAttribute("data-active-lens", state.lens);
    ({bimt: renderBimt, clock_pizza: renderClockPizza, hypernetwork: renderHypernetwork, mips: renderMips, sid: renderSid, open_problems: renderOpenProblems})[state.lens]();
    updateSnapshot();
  }

  els.tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => { state.lens = tab.dataset.lens; history.replaceState(null, "", `#${state.lens}`); render(); });
    tab.addEventListener("keydown", event => {
      if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      event.preventDefault();
      let next = index;
      if (event.key === 'ArrowLeft') next = (index + els.tabs.length - 1) % els.tabs.length;
      if (event.key === 'ArrowRight') next = (index + 1) % els.tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = els.tabs.length - 1;
      els.tabs[next].click(); els.tabs[next].focus();
    });
  });

  els.copy.addEventListener("click", async () => {
    const payload = JSON.stringify(updateSnapshot(), null, 2);
    try {
      await navigator.clipboard.writeText(payload);
      els.copy.textContent = "Copied";
      setTimeout(() => { els.copy.textContent = "Copy snapshot JSON"; }, 1200);
    } catch (_) {
      els.snapshot.focus();
    }
  });

  els.fixture.textContent = `fixture ${data.fixture_sha256.slice(0, 12)}`;
  render();
})();
