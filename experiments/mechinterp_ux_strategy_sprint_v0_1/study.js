(function () {
  "use strict";

  const core = window.PixieMechinterpUXCore;
  const taskSet = window.PixieMechinterpUXTasks;
  const setup = document.getElementById("study-setup");
  const active = document.getElementById("study-active");
  const complete = document.getElementById("study-complete");
  const participantInput = document.getElementById("participant-id");
  const cohortInput = document.getElementById("participant-cohort");
  const laneInput = document.getElementById("study-lane");
  const frame = document.getElementById("study-workspace");
  const answerForm = document.getElementById("answer-form");
  const answerField = document.getElementById("answer-field");
  const claimInput = document.getElementById("claim-scope");
  const confidenceInput = document.getElementById("answer-confidence");
  const confidenceOutput = document.getElementById("confidence-value");
  const status = document.getElementById("study-status");
  let session = null;
  let schedule = [];
  let taskStarted = 0;
  let controlActions = 0;
  let helpOpened = 0;
  let frameReady = false;
  let activeTaskIndex = null;

  taskSet.claimOptions.forEach((option) => {
    const element = document.createElement("option");
    element.value = option.value;
    element.textContent = option.label;
    claimInput.appendChild(element);
  });

  function utcNow() {
    return new Date().toISOString();
  }

  function storageKey(participantId, lane) {
    return `pixie-mechinterp-ux-v1:${participantId}:${lane}`;
  }

  function clone(value) {
    return value === null || value === undefined ? value : JSON.parse(JSON.stringify(value));
  }

  function save() {
    if (!session) return;
    window.localStorage.setItem(storageKey(session.participant_id, session.lane), JSON.stringify(session));
  }

  function newSession(participantId, cohort, lane) {
    schedule = core.schedule(participantId, lane, taskSet);
    const value = {
      schema: "pixieology_mechinterp_ux_session_v1",
      study_id: "mechinterp_ux_strategy_sprint_v0_1",
      session_id: `${participantId}-${lane}-${Date.now()}`,
      participant_id: participantId,
      cohort,
      lane,
      baseline_commit: "ad48954530836109d1b20e66708990dd568ac410",
      started_utc: utcNow(),
      ended_utc: null,
      completed: false,
      task_order: schedule.map((task) => task.task_id),
      responses: [],
      debrief: {
        preference: "not_asked",
        comments: ""
      },
      privacy: {
        anonymous_code_only: true,
        network_telemetry: false
      },
      claim_boundary: "Formative synthetic-fixture UX evidence only."
    };
    if (cohort === "agent") {
      value.agent_contract = {
        structured_analysis_used: false,
        svg_parsing_used: false,
        browser_authorization_method_used: false
      };
    }
    return value;
  }

  function restoreOrCreate(participantId, cohort, lane) {
    schedule = core.schedule(participantId, lane, taskSet);
    const existing = window.localStorage.getItem(storageKey(participantId, lane));
    if (!existing) return newSession(participantId, cohort, lane);
    const value = JSON.parse(existing);
    if (
      value.schema !== "pixieology_mechinterp_ux_session_v1" ||
      value.participant_id !== participantId ||
      value.lane !== lane
    ) {
      throw new Error("saved session is incompatible with this study");
    }
    value.cohort = cohort;
    return value;
  }

  function taskUrl(task) {
    const query = new URLSearchParams();
    query.set("case", task.case_id);
    query.set("layer", String(task.starting_state.layer));
    query.set("module", task.starting_state.module_id);
    query.set("radius", String(task.starting_state.chart_radius));
    query.set("epsilon", String(task.starting_state.glue_tolerance));
    const variants = core.conditionQuery(task);
    Object.entries(variants).forEach(([key, value]) => query.set(key, value));
    const page = task.condition === "baseline" ? "baseline.html" : "triage.html";
    return `${page}?${query.toString()}`;
  }

  function renderAnswer(task) {
    answerField.replaceChildren();
    const label = document.createElement("label");
    label.htmlFor = "task-answer";
    label.textContent = "Your answer";
    let control;
    if (task.answer_type === "integer") {
      control = document.createElement("input");
      control.type = "number";
      control.min = "0";
      control.max = "27";
      control.step = "1";
    } else {
      control = document.createElement("select");
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Choose an answer";
      control.appendChild(placeholder);
      task.options.forEach((option) => {
        const element = document.createElement("option");
        element.value = option.value;
        element.textContent = option.label;
        control.appendChild(element);
      });
    }
    control.id = "task-answer";
    control.required = true;
    label.appendChild(control);
    answerField.appendChild(label);
  }

  function compactAnalysis(analysis) {
    return {
      schema: analysis.schema,
      sequence: analysis.sequence,
      coordinate_source: analysis.coordinate_source,
      state: clone(analysis.state),
      direct_glued_partners: clone(analysis.direct_glued_partners),
      closure_component: clone(analysis.closure_component),
      overview: clone(analysis.overview),
      selected_component: clone(analysis.topology.selected_component),
      dendrogram_mst: clone(analysis.topology.dendrogram_mst),
      quotient: clone(analysis.quotient),
      spin: clone(analysis.spin),
      feedback_jobs: clone(analysis.feedback_jobs),
      claim_boundary: analysis.claim_boundary,
      share_uri: analysis.share_uri
    };
  }

  function attachFrameInstrumentation() {
    const documentValue = frame.contentDocument;
    if (!documentValue) return;
    documentValue.addEventListener("input", (event) => {
      if (event.target.closest("[data-state-key]")) controlActions += 1;
    }, true);
    documentValue.addEventListener("click", (event) => {
      if (event.target.closest("button, .base-node")) controlActions += 1;
    }, true);
    documentValue.querySelectorAll("details").forEach((details) => {
      details.addEventListener("toggle", () => {
        if (details.open) helpOpened += 1;
      });
    });
  }

  function renderTask(index) {
    if (index >= schedule.length) {
      finishSession();
      return;
    }
    const task = schedule[index];
    activeTaskIndex = index;
    frameReady = false;
    controlActions = 0;
    helpOpened = 0;
    status.textContent = "Loading the sealed workspace state…";
    document.getElementById("task-progress").textContent = `Task ${index + 1} of ${schedule.length} · ${task.design_question}`;
    document.getElementById("task-prompt").textContent = task.prompt;
    document.getElementById("condition-badge").textContent =
      task.lane === "workflow" ? task.condition.replaceAll("_", " ") : `${task.design_question} · ${task.variant.replaceAll("_", " ")}`;
    renderAnswer(task);
    claimInput.value = "";
    confidenceInput.value = "3";
    confidenceOutput.textContent = "3 / 5";
    frame.src = taskUrl(task);
    frame.onload = () => {
      try {
        const explorer = frame.contentWindow.PixieEtaleExplorer;
        if (!explorer) throw new Error("workspace API is unavailable");
        explorer.setPlaying(false);
        explorer.loadCase(task.case_id);
        explorer.setState(task.starting_state);
        attachFrameInstrumentation();
        frameReady = true;
        taskStarted = performance.now();
        status.textContent = "Workspace ready. The answer is not scored until analysis.";
      } catch (error) {
        status.textContent = `Workspace failed closed: ${error.message}`;
      }
    };
  }

  function finishSession() {
    session.completed = true;
    session.ended_utc = utcNow();
    activeTaskIndex = null;
    save();
    active.hidden = true;
    complete.hidden = false;
  }

  function recordCurrentAnswer(answer, claimScope, confidence) {
    if (!frameReady) throw new Error("workspace is not ready");
    const index = session.responses.length;
    if (activeTaskIndex !== index) {
      throw new Error("only the next sealed task can be recorded");
    }
    const task = schedule[index];
    if (!task) throw new Error("the sealed task schedule is complete");
    if (!taskSet.claimOptions.some((option) => option.value === claimScope)) {
      throw new Error("unknown evidence boundary");
    }
    const confidenceValue = Number(confidence);
    if (!Number.isInteger(confidenceValue) || confidenceValue < 1 || confidenceValue > 5) {
      throw new Error("confidence must be an integer from 1 to 5");
    }
    const explorer = frame.contentWindow.PixieEtaleExplorer;
    const analysis = explorer.getAnalysis();
    if (session.cohort === "agent") {
      session.agent_contract.structured_analysis_used = true;
    }
    const response = {
      schema: "pixieology_mechinterp_ux_task_response_v1",
      task_id: task.task_id,
      lane: task.lane,
      condition: task.condition,
      design_question: task.design_question,
      variant: task.variant,
      task_type: task.task_type,
      case_id: task.case_id,
      starting_state: clone(task.starting_state),
      final_state: clone(explorer.getState()),
      answer,
      claim_scope: claimScope,
      confidence: confidenceValue,
      elapsed_ms: Math.max(0, performance.now() - taskStarted),
      control_actions: controlActions,
      help_opened: helpOpened,
      analysis: compactAnalysis(analysis)
    };
    session.responses.push(response);
    save();
    renderTask(session.responses.length);
    return clone(response);
  }

  function startSession(config) {
    const participantId = String(config.participant_id || "").trim().toUpperCase();
    core.participantSeed(participantId);
    const lane = config.lane;
    if (!["workflow", "components"].includes(lane)) throw new Error("invalid study lane");
    if (!["researcher", "learner_gamer", "agent"].includes(config.cohort)) throw new Error("invalid cohort");
    session = restoreOrCreate(participantId, config.cohort, lane);
    schedule = core.schedule(participantId, lane, taskSet);
    setup.hidden = true;
    complete.hidden = true;
    active.hidden = false;
    if (session.completed || session.responses.length >= schedule.length) finishSession();
    else renderTask(session.responses.length);
    return clone(session);
  }

  function exportReceipt() {
    if (!session || !session.completed) throw new Error("session is incomplete");
    session.debrief.preference = document.getElementById("session-preference").value;
    session.debrief.comments = document.getElementById("session-comments").value.trim();
    save();
    const blob = new Blob([`${JSON.stringify(session, null, 2)}\n`], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${session.session_id}.json`;
    link.click();
    URL.revokeObjectURL(url);
    return clone(session);
  }

  document.getElementById("start-session").addEventListener("click", () => {
    document.getElementById("setup-error").textContent = "";
    try {
      startSession({
        participant_id: participantInput.value,
        cohort: cohortInput.value,
        lane: laneInput.value
      });
    } catch (error) {
      document.getElementById("setup-error").textContent = error.message;
    }
  });

  answerForm.addEventListener("submit", (event) => {
    event.preventDefault();
    try {
      const control = document.getElementById("task-answer");
      const answer = control.type === "number" ? Number(control.value) : control.value;
      if (control.value === "" || claimInput.value === "") throw new Error("answer and evidence boundary are required");
      recordCurrentAnswer(answer, claimInput.value, confidenceInput.value);
    } catch (error) {
      status.textContent = error.message;
    }
  });

  confidenceInput.addEventListener("input", () => {
    confidenceOutput.textContent = `${confidenceInput.value} / 5`;
  });
  document.getElementById("task-help").addEventListener("toggle", (event) => {
    if (event.target.open) helpOpened += 1;
  });
  document.getElementById("export-receipt").addEventListener("click", exportReceipt);

  window.PixieMechinterpUXStudy = Object.freeze({
    schema: "pixieology_mechinterp_ux_study_contract_v1",
    methods: Object.freeze([
      "startSession", "loadTask", "recordAnswer", "exportReceipt", "getSession",
      "getCurrentTask", "getWorkspaceAnalysis"
    ]),
    startSession,
    loadTask: (index) => {
      if (!session) throw new Error("start a session first");
      if (!Number.isInteger(index) || index < 0 || index >= schedule.length) throw new RangeError("task index out of range");
      if (index !== session.responses.length) throw new Error("only the next sealed task may be loaded");
      renderTask(index);
    },
    recordAnswer: ({ answer, claim_scope, confidence }) => recordCurrentAnswer(answer, claim_scope, confidence),
    exportReceipt,
    getSession: () => clone(session),
    getCurrentTask: () => activeTaskIndex === null ? null : clone(schedule[activeTaskIndex]),
    getWorkspaceAnalysis: () => {
      if (!frameReady) return null;
      if (session.cohort === "agent") {
        session.agent_contract.structured_analysis_used = true;
        save();
      }
      return compactAnalysis(frame.contentWindow.PixieEtaleExplorer.getAnalysis());
    }
  });
})();
