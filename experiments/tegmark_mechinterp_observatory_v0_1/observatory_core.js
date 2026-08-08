(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TegmarkObservatoryCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const LENS_META = {
    bimt: {
      kicker: "Seeing is Believing",
      title: "Wiring as a training intervention",
      question: "Did geometry-aware training simplify the circuit without silently changing the task?",
      next: "Train matched seeds under vanilla, L1, local, swap, and BIMT conditions; ingest weights and edge-ablation outcomes."
    },
    clock_pizza: {
      kicker: "The Clock and the Pizza",
      title: "Same behavior, different algorithm",
      question: "Where does the internal algorithm change while validation accuracy remains essentially fixed?",
      next: "Sweep attention rate, width, and seed on modular addition; compute circularity, gradient symmetricity, and distance irrelevance q."
    },
    hypernetwork: {
      kicker: "Interpretable networks using hypernetworks",
      title: "An algorithmic phase diagram",
      question: "Which discrete solution family emerges as complexity pressure and training time change?",
      next: "Train a hypernetwork ensemble across β and time; retain seed distributions and test sizes outside the training support."
    },
    mips: {
      kicker: "MIPS · Opening the AI Black Box",
      title: "A mechanism compiler",
      question: "Can the latent dynamics be converted into exact state, executable code, and a passing verification test?",
      next: "Run simplification, integer/Boolean autoencoding, FSM extraction, symbolic regression, and held-out execution on captured state."
    },
    sid: {
      kicker: "Sparse invariant detector",
      title: "Sparsity is not yet conservation",
      question: "Does a sparse expression live in the dynamics' nullspace and remain constant on held-out trajectories?",
      next: "Build the directional-derivative matrix from measured dynamics, rotate its nullspace sparsely, and test functional independence and held-out constancy."
    },
    open_problems: {
      kicker: "Open Problems in Mechanistic Interpretability",
      title: "Route a picture into a claim",
      question: "What validation evidence is missing before an interpretation can support monitoring, prediction, or control?",
      next: "Pre-register the chosen goal's counterfactual, replacement, held-out, and competitive-baseline tests."
    },
    control_certificate: {
      kicker: "Proven portfolio addition · finite-horizon control",
      title: "Passive sameness, actionable difference",
      question: "Can identical passive state geometry conceal a provably different intervention-reachable subspace?",
      next: "Estimate local transition Jacobian A and registered intervention Jacobian B from a model, then validate the predicted reachable subspace with held-out interventions."
    }
  };

  const defaultSelection = data => ({
    bimtMethod: data.lenses.bimt.methods[4].id,
    bimtEdge: null,
    clockWidth: data.lenses.clock_pizza.widths[1],
    clockAttention: data.lenses.clock_pizza.attention_rates[2],
    hyperBeta: data.lenses.hypernetwork.betas[2],
    hyperStep: data.lenses.hypernetwork.steps[2],
    hyperView: "phase",
    mipsCase: data.lenses.mips.cases[0].id,
    mipsStage: 0,
    sidSystem: data.lenses.sid.systems[0].id,
    sidView: "spectrum",
    claimGoal: data.lenses.open_problems.goals[1].id,
    controlView: "passive",
    controlSystem: data.lenses.control_certificate.systems[0].id
  });

  function findClockCell(data, selection) {
    return data.lenses.clock_pizza.cells.find(c => c.width === Number(selection.clockWidth) && c.attention_rate === Number(selection.clockAttention));
  }

  function findHyperCell(data, selection) {
    return data.lenses.hypernetwork.cells.find(c => c.beta === Number(selection.hyperBeta) && c.step === Number(selection.hyperStep));
  }

  function snapshot(data, lens, selection) {
    const meta = LENS_META[lens];
    let selected;
    let observations;
    if (lens === "bimt") {
      const method = data.lenses.bimt.methods.find(m => m.id === selection.bimtMethod);
      const edge = selection.bimtEdge == null ? null : method.edges[selection.bimtEdge];
      selected = {method: method.id, edge_index: selection.bimtEdge};
      observations = {
        task_loss: method.task_loss,
        connection_cost: method.connection_cost,
        active_edges: method.active_edges,
        selected_edge: edge
      };
    } else if (lens === "clock_pizza") {
      const cell = findClockCell(data, selection);
      selected = {width: cell.width, attention_rate: cell.attention_rate};
      observations = {...cell};
    } else if (lens === "hypernetwork") {
      const cell = findHyperCell(data, selection);
      selected = {beta: cell.beta, training_step: cell.step, view: selection.hyperView};
      observations = {...cell};
    } else if (lens === "mips") {
      const item = data.lenses.mips.cases.find(c => c.id === selection.mipsCase);
      selected = {case: item.id, stage_index: selection.mipsStage, stage: item.stages[selection.mipsStage]};
      observations = {status: item.status, integer_code: item.integer_code, symbolic_law: item.symbolic_law, verification: item.verification};
    } else if (lens === "sid") {
      const item = data.lenses.sid.systems.find(s => s.id === selection.sidSystem);
      selected = {system: item.id, view: selection.sidView};
      observations = {dynamics: item.dynamics, basis: item.basis, nullity: item.nullity, independent_rank: item.independent_rank, law: item.law, max_residual: item.max_residual};
    } else if (lens === "open_problems") {
      const goal = data.lenses.open_problems.goals.find(g => g.id === selection.claimGoal);
      selected = {goal: goal.id};
      observations = {pipeline: data.lenses.open_problems.pipeline, evidence_route: goal.evidence_route, progress_axes: data.lenses.open_problems.axes, strongest_validation_rung: data.lenses.open_problems.validation_ladder.at(-1)};
    } else {
      const certificate = data.lenses.control_certificate;
      const system = certificate.systems.find(item => item.id === selection.controlSystem);
      selected = {view: selection.controlView, system: system.id, horizon: certificate.horizon};
      observations = selection.controlView === "passive" ? {
        A: system.A,
        passive_trajectory: system.passive_trajectory,
        passive_views_identical: certificate.exact_claims.passive_views_identical,
        registered_action_visible: false,
        model_identifying_information_bits: 0
      } : {
        A: system.A,
        B: system.B,
        reachability_matrix: system.reachability_matrix,
        gramian: system.gramian,
        reachable_dimension: system.reachability_rank,
        fully_controllable: system.fully_controllable,
        passive_views_identical: certificate.exact_claims.passive_views_identical,
        uniform_prior_information_gain_bits: certificate.exact_claims.uniform_prior_information_gain_bits,
        proof_checks: certificate.proof_checks
      };
    }
    return {
      schema_version: "tegmark_mechinterp_observatory.snapshot.v1",
      lens,
      paper: meta.kicker,
      source: data.sources[lens],
      question: meta.question,
      selection: selected,
      observations,
      evidence_class: data.evidence_class,
      claim_boundary: data.claim_boundary,
      next_evidence_action: meta.next,
      fixture_sha256: data.fixture_sha256
    };
  }

  return {LENS_META, defaultSelection, findClockCell, findHyperCell, snapshot};
});
