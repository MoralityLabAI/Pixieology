(function () {
  "use strict";

  const data = window.PixieMechanismLawLabData;
  const core = window.PixieMechanismLawLabCore;
  if (!data || !core) throw new Error("Mechanism Law Lab dependencies are missing");

  const names = {
    base_qwen_derived_1p7b: "Base",
    pixie_rank8: "Pixie",
  };
  const elements = Object.fromEntries(
    [
      "family-select",
      "complexity-range",
      "complexity-output",
      "protocol-choice",
      "phase-status",
      "phase-chart",
      "base-fidelity",
      "pixie-fidelity",
      "alignment-fidelity",
      "description-bits",
      "base-invariant",
      "pixie-invariant",
      "base-law-table",
      "pixie-law-table",
      "alignment-map",
      "alignment-note",
      "transition-detail",
      "focus-base",
      "focus-pixie",
      "intervention-list",
      "intervention-title",
      "intervention-predicted",
      "intervention-observed",
      "intervention-random",
      "intervention-guardrail",
      "intervention-verdict",
      "claim-boundary",
      "agent-status",
    ].map((id) => [id, document.getElementById(id)])
  );
  if (Object.values(elements).some((element) => !element)) {
    throw new Error("Mechanism Law Lab page contract is incomplete");
  }

  let state = core.createState(data);

  function escape(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function percent(value) {
    return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
  }

  function phaseLabel(status) {
    return {
      UNDERFIT_AT_K: "Underfit at k",
      PROVISIONAL_ISOMORPHISM: "Provisional isomorphism",
      MECHANISM_DIVERGENCE: "Mechanism divergence",
      ALIGNMENT_UNAVAILABLE: "Alignment unavailable",
    }[status] || status;
  }

  function renderControls(current) {
    const family = current.family;
    elements["family-select"].value = state.familyId;
    elements["complexity-range"].min = String(Math.min(...family.complexity_values));
    elements["complexity-range"].max = String(Math.max(...family.complexity_values));
    elements["complexity-range"].value = String(state.complexity);
    elements["complexity-output"].value = `k = ${state.complexity}`;
    const baseK = family.candidates.base_qwen_derived_1p7b.selected_state_count;
    const pixieK = family.candidates.pixie_rank8.selected_state_count;
    elements["protocol-choice"].textContent = `Base k${baseK} / Pixie k${pixieK}`;
    elements["phase-status"].textContent = phaseLabel(current.phaseStatus);
  }

  function renderPhaseChart(current) {
    const width = Math.max(320, Math.round(elements["phase-chart"].getBoundingClientRect().width));
    const height = 300;
    const margin = { left: 64, right: 28, top: 24, bottom: 52 };
    const family = current.family;
    const allRows = core.CANDIDATES.flatMap(
      (candidate) => family.candidates[candidate].phase_scan
    );
    const xValues = family.complexity_values;
    const minFidelity = Math.min(...allRows.map((row) => row.heldout_fidelity));
    const yMin = Math.max(0, Math.floor((minFidelity - 0.08) * 10) / 10);
    const yMax = 1;
    const x = (value) => {
      const span = Math.max(1, Math.max(...xValues) - Math.min(...xValues));
      return margin.left + ((value - Math.min(...xValues)) / span) * (width - margin.left - margin.right);
    };
    const y = (value) =>
      margin.top + ((yMax - value) / Math.max(0.01, yMax - yMin)) * (height - margin.top - margin.bottom);
    const pathFor = (candidate, offset) => family.candidates[candidate].phase_scan
      .map((row, index) => `${index ? "L" : "M"}${(x(row.state_count) + offset).toFixed(1)},${y(row.heldout_fidelity).toFixed(1)}`)
      .join(" ");
    const ticks = Array.from(new Set([yMin, (yMin + 1) / 2, 0.9, 1]))
      .filter((value) => value >= yMin && value <= 1)
      .sort((left, right) => left - right);
    const grid = ticks.map((tick) => `
      <line class="grid" x1="${margin.left}" x2="${width - margin.right}" y1="${y(tick)}" y2="${y(tick)}"></line>
      <text x="${margin.left - 12}" y="${y(tick) + 4}" text-anchor="end">${Math.round(tick * 100)}%</text>
    `).join("");
    const xTicks = xValues.map((tick) => `
      <line class="axis" x1="${x(tick)}" x2="${x(tick)}" y1="${height - margin.bottom}" y2="${height - margin.bottom + 6}"></line>
      <text x="${x(tick)}" y="${height - margin.bottom + 24}" text-anchor="middle">${tick}</text>
    `).join("");
    const basePoints = family.candidates.base_qwen_derived_1p7b.phase_scan.map((row) => `
      <circle class="base-point" cx="${x(row.state_count) - 3}" cy="${y(row.heldout_fidelity)}" r="5">
        <title>Base k=${row.state_count}: ${percent(row.heldout_fidelity)}, ${Math.round(row.description_length_bits)} bits</title>
      </circle>
    `).join("");
    const pixiePoints = family.candidates.pixie_rank8.phase_scan.map((row) => {
      const centerX = x(row.state_count) + 3;
      const centerY = y(row.heldout_fidelity);
      return `
        <rect class="pixie-point" x="${centerX - 4.5}" y="${centerY - 4.5}" width="9" height="9" transform="rotate(45 ${centerX} ${centerY})">
          <title>Pixie k=${row.state_count}: ${percent(row.heldout_fidelity)}, ${Math.round(row.description_length_bits)} bits</title>
        </rect>
      `;
    }).join("");
    const floor = data.thresholds.discovery_fidelity_floor;
    elements["phase-chart"].setAttribute("viewBox", `0 0 ${width} ${height}`);
    elements["phase-chart"].innerHTML = `
      <title id="phase-chart-title">Held-out program fidelity by state count</title>
      <desc id="phase-chart-desc">Base and Pixie fidelity curves for ${escape(state.familyId)}. The selected complexity is k=${state.complexity}.</desc>
      ${grid}
      <line class="axis axis-strong" x1="${margin.left}" x2="${margin.left}" y1="${margin.top}" y2="${height - margin.bottom}"></line>
      <line class="axis axis-strong" x1="${margin.left}" x2="${width - margin.right}" y1="${height - margin.bottom}" y2="${height - margin.bottom}"></line>
      ${xTicks}
      <line class="threshold" x1="${margin.left}" x2="${width - margin.right}" y1="${y(floor)}" y2="${y(floor)}"></line>
      <text x="${width - margin.right}" y="${y(floor) - 8}" text-anchor="end">discovery floor ${Math.round(floor * 100)}%</text>
      <line class="selection" x1="${x(state.complexity)}" x2="${x(state.complexity)}" y1="${margin.top}" y2="${height - margin.bottom}"></line>
      <path class="base-line" d="${pathFor("base_qwen_derived_1p7b", -3)}"></path>
      <path class="pixie-line" d="${pathFor("pixie_rank8", 3)}"></path>
      ${basePoints}
      ${pixiePoints}
      <text class="axis-label" x="${(margin.left + width - margin.right) / 2}" y="${height - 8}" text-anchor="middle">state-count complexity k</text>
      <text class="axis-label" x="17" y="${(margin.top + height - margin.bottom) / 2}" text-anchor="middle" transform="rotate(-90 17 ${(margin.top + height - margin.bottom) / 2})">held-out fidelity</text>
    `;
    elements["base-fidelity"].textContent = percent(
      current.phases.base_qwen_derived_1p7b.heldout_fidelity
    );
    elements["pixie-fidelity"].textContent = percent(
      current.phases.pixie_rank8.heldout_fidelity
    );
    elements["alignment-fidelity"].textContent = current.alignment
      ? percent(current.alignment.fidelity)
      : "Unavailable";
    elements["description-bits"].textContent = `${Math.round(
      current.phases.base_qwen_derived_1p7b.description_length_bits
    )} / ${Math.round(current.phases.pixie_rank8.description_length_bits)} bits`;
  }

  function lawTable(candidate, phase) {
    const inputs = [...new Set(phase.transition_table.map((row) => row.input_symbol))].sort();
    const states = [...new Set(phase.transition_table.map((row) => row.state))].sort((a, b) => a - b);
    const rows = states.map((stateId) => {
      const cells = inputs.map((input) => {
        const row = phase.transition_table.find(
          (item) => item.state === stateId && item.input_symbol === input
        );
        if (!row) return "<td>—</td>";
        const key = core.transitionKey(row);
        const selected = state.focusCandidate === candidate && state.selectedTransitionKey === key;
        return `<td><button type="button" class="transition-button${selected ? " is-selected" : ""}" data-candidate="${candidate}" data-transition-key="${escape(key)}" aria-pressed="${selected}">q${row.next_state} <span>/ ${escape(row.output_symbol)}</span></button></td>`;
      }).join("");
      return `<tr><th scope="row">q${stateId}</th>${cells}</tr>`;
    }).join("");
    return `
      <table class="law-table">
        <caption class="visually-hidden">${escape(names[candidate])} transition law at k=${phase.state_count}</caption>
        <thead><tr><th scope="col">state</th>${inputs.map((input) => `<th scope="col">+ ${escape(input)}</th>`).join("")}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  function renderLaws(current) {
    const basePhase = current.phases.base_qwen_derived_1p7b;
    const pixiePhase = current.phases.pixie_rank8;
    elements["base-law-table"].innerHTML = lawTable("base_qwen_derived_1p7b", basePhase);
    elements["pixie-law-table"].innerHTML = lawTable("pixie_rank8", pixiePhase);
    elements["base-invariant"].textContent = `Sparse coordinates a[${basePhase.sparse_invariant.selected_dimensions.join(", ")}] identify ${basePhase.sparse_invariant.unique_state_signatures}/${basePhase.state_count} states`;
    elements["pixie-invariant"].textContent = `Sparse coordinates a[${pixiePhase.sparse_invariant.selected_dimensions.join(", ")}] identify ${pixiePhase.sparse_invariant.unique_state_signatures}/${pixiePhase.state_count} states`;
    elements["focus-base"].setAttribute(
      "aria-pressed",
      String(state.focusCandidate === "base_qwen_derived_1p7b")
    );
    elements["focus-pixie"].setAttribute(
      "aria-pressed",
      String(state.focusCandidate === "pixie_rank8")
    );
    document.querySelectorAll("[data-transition-key]").forEach((button) => {
      button.addEventListener("click", () => {
        const candidate = button.dataset.candidate;
        if (candidate !== state.focusCandidate) {
          dispatch({ type: "SELECT_CANDIDATE", candidate }, false);
        }
        dispatch({ type: "SELECT_TRANSITION", key: button.dataset.transitionKey });
      });
    });

    if (current.alignment && current.alignment.mapping) {
      elements["alignment-map"].innerHTML = Object.entries(current.alignment.mapping)
        .sort((left, right) => Number(left[0]) - Number(right[0]))
        .map(([pixieState, baseState]) => `
          <div class="mapping-row">
            <span class="mapping-pixie">Pixie q${escape(pixieState)}</span>
            <span class="connector" aria-hidden="true"></span>
            <span class="mapping-base">Base q${escape(baseState)}</span>
          </div>
        `).join("");
      elements["alignment-note"].textContent = `${percent(current.alignment.fidelity)} of transition rules survive the best bijective relabeling.`;
    } else {
      elements["alignment-map"].textContent = "No bijection at this complexity.";
      elements["alignment-note"].textContent = "Different state counts or alignment limit exceeded.";
    }
    elements["transition-detail"].textContent = current.transition
      ? `${names[state.focusCandidate]} q${current.transition.state} + ${current.transition.input_symbol} → q${current.transition.next_state} / ${current.transition.output_symbol} · support ${current.transition.support} · purity ${percent(current.transition.purity)}`
      : "Select a transition cell to inspect it.";
  }

  function renderInterventions(current) {
    const rows = current.family.candidates[state.focusCandidate].interventions;
    elements["intervention-list"].innerHTML = rows.map((row, index) => {
      const selected = row.observation_id === state.selectedInterventionId;
      return `<button type="button" class="intervention-button${selected ? " is-selected" : ""}" data-observation-id="${escape(row.observation_id)}" aria-pressed="${selected}">Patch ${String(index + 1).padStart(2, "0")}<br>${escape(row.predicted_output_symbol)} predicted</button>`;
    }).join("");
    document.querySelectorAll("[data-observation-id]").forEach((button) => {
      button.addEventListener("click", () => dispatch({
        type: "SELECT_INTERVENTION",
        observationId: button.dataset.observationId,
      }));
    });
    const row = current.intervention;
    if (!row) {
      elements["intervention-title"].textContent = "No observation selected";
      elements["intervention-predicted"].textContent = "—";
      elements["intervention-observed"].textContent = "—";
      elements["intervention-random"].textContent = "—";
      elements["intervention-guardrail"].textContent = "—";
      elements["intervention-verdict"].textContent = "Not run";
      return;
    }
    elements["intervention-title"].textContent = `${names[state.focusCandidate]} · ${row.observation_id}`;
    elements["intervention-predicted"].textContent = row.predicted_output_symbol;
    elements["intervention-observed"].textContent = row.observed_output_symbol;
    elements["intervention-random"].textContent = row.matched_random_output_symbol;
    elements["intervention-guardrail"].textContent = Number(row.guardrail_delta).toFixed(3);
    const passed = row.predicted_output_symbol === row.observed_output_symbol
      && row.matched_random_output_symbol === row.baseline_output_symbol
      && Math.abs(row.guardrail_delta) <= 0.05;
    elements["intervention-verdict"].textContent = passed
      ? "Fixture check passes · target changed · random did not"
      : "Fixture check does not support this law";
  }

  function render() {
    const current = core.derive(data, state);
    renderControls(current);
    renderPhaseChart(current);
    renderLaws(current);
    renderInterventions(current);
    elements["claim-boundary"].textContent = data.claim_boundary;
    elements["agent-status"].textContent = `AGENT API READY · ${state.familyId} · k=${state.complexity} · ${current.claimStatus}`;
    document.dispatchEvent(new CustomEvent("lawlab:statechange", {
      detail: core.agentSnapshot(data, state),
    }));
  }

  function dispatch(action, shouldRender = true) {
    state = core.reduce(data, state, action);
    if (shouldRender) render();
    return core.agentSnapshot(data, state);
  }

  elements["family-select"].innerHTML = data.families.map((family) =>
    `<option value="${escape(family.task_family_id)}">${escape(family.task_family_id)} · ${family.oracle_shape.state_count} states / ${family.oracle_shape.input_symbols.length} inputs</option>`
  ).join("");
  elements["family-select"].addEventListener("change", (event) => dispatch({
    type: "SELECT_FAMILY",
    familyId: event.target.value,
  }));
  elements["complexity-range"].addEventListener("input", (event) => dispatch({
    type: "SET_COMPLEXITY",
    complexity: Number(event.target.value),
  }));
  elements["focus-base"].addEventListener("click", () => dispatch({
    type: "SELECT_CANDIDATE",
    candidate: "base_qwen_derived_1p7b",
  }));
  elements["focus-pixie"].addEventListener("click", () => dispatch({
    type: "SELECT_CANDIDATE",
    candidate: "pixie_rank8",
  }));

  window.PixieMechanismLawLab = Object.freeze({
    dataHash: data.dataset_sha256,
    dispatch,
    getState: () => ({ ...state }),
    snapshot: () => core.agentSnapshot(data, state),
  });
  render();
  if (typeof ResizeObserver === "function") {
    let chartWidth = Math.round(elements["phase-chart"].getBoundingClientRect().width);
    new ResizeObserver(() => {
      const nextWidth = Math.round(elements["phase-chart"].getBoundingClientRect().width);
      if (Math.abs(nextWidth - chartWidth) > 1) {
        chartWidth = nextWidth;
        renderPhaseChart(core.derive(data, state));
      }
    }).observe(elements["phase-chart"]);
  }
})();
