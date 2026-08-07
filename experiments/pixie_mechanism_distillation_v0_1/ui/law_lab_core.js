(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.PixieMechanismLawLabCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const CANDIDATES = ["base_qwen_derived_1p7b", "pixie_rank8"];

  function familyById(data, familyId) {
    const family = data.families.find((item) => item.task_family_id === familyId);
    if (!family) throw new Error(`Unknown family: ${familyId}`);
    return family;
  }

  function phaseAt(family, candidate, complexity) {
    return family.candidates[candidate].phase_scan.find(
      (item) => item.state_count === complexity
    );
  }

  function transitionKey(row) {
    return `${row.state}:${row.input_symbol}`;
  }

  function initialTransition(family, candidate, complexity) {
    const phase = phaseAt(family, candidate, complexity);
    return phase && phase.transition_table.length
      ? transitionKey(phase.transition_table[0])
      : null;
  }

  function initialIntervention(family, candidate) {
    const rows = family.candidates[candidate].interventions;
    return rows.length ? rows[0].observation_id : null;
  }

  function createState(data) {
    if (!data || data.schema !== "pixieology_mechanism_law_lab_dataset_v1") {
      throw new Error("Invalid Mechanism Law Lab dataset");
    }
    if (!data.families.length) throw new Error("Mechanism Law Lab dataset is empty");
    const family = data.families[0];
    const candidate = "pixie_rank8";
    return {
      familyId: family.task_family_id,
      complexity: family.default_complexity,
      focusCandidate: candidate,
      selectedTransitionKey: initialTransition(
        family,
        candidate,
        family.default_complexity
      ),
      selectedInterventionId: initialIntervention(family, candidate),
    };
  }

  function reduce(data, state, action) {
    if (!action || typeof action.type !== "string") {
      throw new Error("Mechanism Law Lab action requires a type");
    }
    if (action.type === "SELECT_FAMILY") {
      const family = familyById(data, action.familyId);
      const candidate = state.focusCandidate;
      return {
        ...state,
        familyId: family.task_family_id,
        complexity: family.default_complexity,
        selectedTransitionKey: initialTransition(
          family,
          candidate,
          family.default_complexity
        ),
        selectedInterventionId: initialIntervention(family, candidate),
      };
    }
    const family = familyById(data, state.familyId);
    if (action.type === "SET_COMPLEXITY") {
      const complexity = Number(action.complexity);
      if (!family.complexity_values.includes(complexity)) {
        throw new Error(`Complexity k=${complexity} is unavailable for ${state.familyId}`);
      }
      return {
        ...state,
        complexity,
        selectedTransitionKey: initialTransition(
          family,
          state.focusCandidate,
          complexity
        ),
      };
    }
    if (action.type === "SELECT_CANDIDATE") {
      if (!CANDIDATES.includes(action.candidate)) {
        throw new Error(`Unknown candidate: ${action.candidate}`);
      }
      return {
        ...state,
        focusCandidate: action.candidate,
        selectedTransitionKey: initialTransition(
          family,
          action.candidate,
          state.complexity
        ),
        selectedInterventionId: initialIntervention(family, action.candidate),
      };
    }
    if (action.type === "SELECT_TRANSITION") {
      const phase = phaseAt(family, state.focusCandidate, state.complexity);
      if (!phase.transition_table.some((row) => transitionKey(row) === action.key)) {
        throw new Error(`Unknown transition: ${action.key}`);
      }
      return { ...state, selectedTransitionKey: action.key };
    }
    if (action.type === "SELECT_INTERVENTION") {
      const exists = family.candidates[state.focusCandidate].interventions.some(
        (row) => row.observation_id === action.observationId
      );
      if (!exists) throw new Error(`Unknown intervention: ${action.observationId}`);
      return { ...state, selectedInterventionId: action.observationId };
    }
    throw new Error(`Unknown Mechanism Law Lab action: ${action.type}`);
  }

  function derive(data, state) {
    const family = familyById(data, state.familyId);
    const phases = Object.fromEntries(
      CANDIDATES.map((candidate) => [
        candidate,
        phaseAt(family, candidate, state.complexity),
      ])
    );
    if (!phases[CANDIDATES[0]] || !phases[CANDIDATES[1]]) {
      throw new Error(`Incomplete phase data at k=${state.complexity}`);
    }
    const alignment = family.alignments_by_state_count[String(state.complexity)];
    const bothQualified = CANDIDATES.every(
      (candidate) => phases[candidate].qualified
    );
    let phaseStatus = "UNDERFIT_AT_K";
    if (bothQualified && alignment && alignment.available) {
      phaseStatus =
        alignment.fidelity >= data.thresholds.minimum_isomorphism_fidelity
          ? "PROVISIONAL_ISOMORPHISM"
          : "MECHANISM_DIVERGENCE";
    } else if (bothQualified) {
      phaseStatus = "ALIGNMENT_UNAVAILABLE";
    }
    const focusPhase = phases[state.focusCandidate];
    const transition = focusPhase.transition_table.find(
      (row) => transitionKey(row) === state.selectedTransitionKey
    ) || null;
    const intervention = family.candidates[state.focusCandidate].interventions.find(
      (row) => row.observation_id === state.selectedInterventionId
    ) || null;
    return {
      family,
      phases,
      alignment,
      phaseStatus,
      transition,
      intervention,
      selectedByProtocol: CANDIDATES.every(
        (candidate) =>
          family.candidates[candidate].selected_state_count === state.complexity
      ),
      claimStatus: "IMPLEMENTATION_ONLY",
    };
  }

  function agentSnapshot(data, state) {
    const current = derive(data, state);
    return {
      schema: "pixieology_mechanism_law_lab_agent_snapshot_v1",
      dataset_sha256: data.dataset_sha256,
      family_id: state.familyId,
      complexity_state_count: state.complexity,
      focus_candidate: state.focusCandidate,
      phase_status: current.phaseStatus,
      selected_by_protocol: current.selectedByProtocol,
      base_heldout_fidelity:
        current.phases.base_qwen_derived_1p7b.heldout_fidelity,
      pixie_heldout_fidelity: current.phases.pixie_rank8.heldout_fidelity,
      alignment_fidelity: current.alignment ? current.alignment.fidelity : null,
      selected_transition: current.transition,
      selected_intervention: current.intervention,
      comparison_verdict: current.family.comparison.isomorphism_verdict,
      evidence_class: data.evidence_class,
      claim_status: current.claimStatus,
    };
  }

  return {
    CANDIDATES,
    agentSnapshot,
    createState,
    derive,
    familyById,
    phaseAt,
    reduce,
    transitionKey,
  };
});
