(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.GodelCharacterStudy = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const schemaVersion = 1;
  const studyId = "godel_globes_5d_character_ab_v1";
  const tupleOrder = ["wonder", "play", "care", "resolve", "reflection"];
  const seedling = [0.5, 0.5, 0.5, 0.5, 0.5];
  const moonArchivist = [0.35, 0.2, 0.75, 0.78, 0.92];

  const tasks = Object.freeze([
    Object.freeze({
      id: "left-wing",
      instruction: "Make Wonder 85 and Play 25. Leave the other traits at 50.",
      startTuple: seedling,
      targetTuple: [0.85, 0.25, 0.5, 0.5, 0.5],
      allowedDimensions: ["wonder", "play"],
      kind: "target"
    }),
    Object.freeze({
      id: "right-wing",
      instruction: "Make Care 90 and Resolve 85. Leave the other traits at 50.",
      startTuple: seedling,
      targetTuple: [0.5, 0.5, 0.9, 0.85, 0.5],
      allowedDimensions: ["care", "resolve"],
      kind: "target"
    }),
    Object.freeze({
      id: "head",
      instruction: "Make Reflection 90. Leave the other traits at 50.",
      startTuple: seedling,
      targetTuple: [0.5, 0.5, 0.5, 0.5, 0.9],
      allowedDimensions: ["reflection"],
      kind: "target"
    }),
    Object.freeze({
      id: "named-warp",
      instruction: "Travel to Moon Archivist.",
      startTuple: seedling,
      targetTuple: moonArchivist,
      allowedDimensions: [],
      kind: "target"
    }),
    Object.freeze({
      id: "edit-and-return",
      instruction: "From Moon Archivist, raise Play to 60, then use Warp back to restore Moon Archivist.",
      startTuple: moonArchivist,
      targetTuple: moonArchivist,
      modifiedTuple: [0.35, 0.6, 0.75, 0.78, 0.92],
      allowedDimensions: ["play"],
      kind: "edit-and-return"
    })
  ]);

  function assertTuple(tuple, name = "tuple") {
    if (!Array.isArray(tuple) || tuple.length !== tupleOrder.length) {
      throw new TypeError(`${name} must contain exactly five numbers`);
    }
    tuple.forEach((value, index) => {
      if (!Number.isFinite(value) || value < 0 || value > 1) {
        throw new RangeError(`${name}[${index}] must be in [0, 1]`);
      }
    });
  }

  function stableParity(value) {
    const text = String(value).trim();
    if (!text) throw new Error("participant_id is required");
    let hash = 0;
    for (const character of text) hash = (hash * 31 + character.codePointAt(0)) >>> 0;
    return hash % 2;
  }

  function conditionFor(participantId, round) {
    if (round !== 1 && round !== 2) throw new RangeError("round must be 1 or 2");
    const embodiedFirst = stableParity(participantId) === 0;
    if (round === 1) return embodiedFirst ? "embodied" : "flat";
    return embodiedFirst ? "flat" : "embodied";
  }

  function tupleError(actual, target) {
    assertTuple(actual, "actual");
    assertTuple(target, "target");
    return actual.reduce((sum, value, index) => sum + Math.abs(value - target[index]), 0);
  }

  function nearTuple(actual, target, tolerance = 0.011) {
    return tupleError(actual, target) <= tolerance * tupleOrder.length;
  }

  function cloneTask(task) {
    return {
      ...task,
      startTuple: task.startTuple.slice(),
      targetTuple: task.targetTuple.slice(),
      modifiedTuple: task.modifiedTuple ? task.modifiedTuple.slice() : undefined,
      allowedDimensions: task.allowedDimensions.slice()
    };
  }

  class StudySession {
    constructor({ participantId, round, condition, now = () => Date.now() }) {
      this.participantId = String(participantId || "").trim();
      if (!this.participantId) throw new Error("participant_id is required");
      this.round = Number(round);
      this.condition = condition || conditionFor(this.participantId, this.round);
      if (!new Set(["embodied", "flat"]).has(this.condition)) {
        throw new Error("condition must be embodied or flat");
      }
      this.now = now;
      this.startedAt = this.now();
      this.elapsedOffset = 0;
      this.events = [];
      this.results = [];
      this.active = null;
      this.debrief = null;
      this.sequence = 0;
      this.record("session_start", { condition: this.condition, round: this.round });
    }

    static fromReceipt(receipt, { now = () => Date.now() } = {}) {
      if (!receipt || receipt.study_id !== studyId || receipt.schema_version !== schemaVersion) {
        throw new Error("cannot resume an incompatible study receipt");
      }
      if (!Array.isArray(receipt.events) || !Array.isArray(receipt.task_results)) {
        throw new Error("cannot resume a malformed study receipt");
      }
      const session = new StudySession({
        participantId: receipt.participant_id,
        round: receipt.round,
        condition: receipt.condition,
        now
      });
      const events = receipt.events.map((event) => ({ ...event }));
      const lastElapsed = events.reduce((maximum, event) => Math.max(maximum, Number(event.t_ms) || 0), 0);
      const nextSequence = events.reduce((maximum, event) => Math.max(maximum, Number(event.seq) + 1 || 0), 0);
      session.startedAt = session.now();
      session.elapsedOffset = lastElapsed;
      session.events = events;
      session.results = receipt.task_results.map((result) => ({ ...result }));
      session.debrief = receipt.debrief ? { ...receipt.debrief } : null;
      session.sequence = nextSequence;
      session.active = null;
      session.record("session_resume", { completed_tasks: session.results.length });
      return session;
    }

    elapsedMs() {
      return this.elapsedOffset + Math.max(0, this.now() - this.startedAt);
    }

    record(type, payload = {}) {
      const event = {
        seq: this.sequence,
        t_ms: this.elapsedMs(),
        type,
        ...payload
      };
      this.sequence += 1;
      this.events.push(event);
      return event;
    }

    beginTask(taskId) {
      if (this.active) throw new Error("finish or skip the active task first");
      const task = tasks.find((candidate) => candidate.id === taskId);
      if (!task) throw new Error(`unknown task ${taskId}`);
      this.active = {
        task: cloneTask(task),
        startedAtMs: this.elapsedMs(),
        actionCount: 0,
        wrongDimensionActions: 0,
        modifiedReached: false
      };
      this.record("task_start", { task_id: task.id });
      return cloneTask(task);
    }

    action(type, payload, tuple) {
      if (!this.active) return { complete: false };
      assertTuple(tuple);
      this.active.actionCount += 1;
      if (type === "dimension_change" && payload.dimension) {
        if (!this.active.task.allowedDimensions.includes(payload.dimension)) {
          this.active.wrongDimensionActions += 1;
        }
      }
      if (
        this.active.task.kind === "edit-and-return" &&
        nearTuple(tuple, this.active.task.modifiedTuple)
      ) {
        this.active.modifiedReached = true;
      }
      this.record(type, { ...payload, task_id: this.active.task.id, tuple: tuple.slice() });
      return this.check(tuple);
    }

    check(tuple) {
      if (!this.active) return { complete: false };
      assertTuple(tuple);
      const { task, modifiedReached } = this.active;
      const complete = task.kind === "edit-and-return"
        ? modifiedReached && nearTuple(tuple, task.targetTuple)
        : nearTuple(tuple, task.targetTuple);
      if (!complete) return { complete: false, error: tupleError(tuple, task.targetTuple) };
      return this.finish(tuple);
    }

    finish(tuple) {
      if (!this.active) throw new Error("no active task");
      const elapsed = Math.max(0, this.elapsedMs() - this.active.startedAtMs);
      const result = {
        task_id: this.active.task.id,
        status: "PASS",
        elapsed_ms: elapsed,
        actions: this.active.actionCount,
        wrong_dimension_actions: this.active.wrongDimensionActions,
        final_l1_error: Number(tupleError(tuple, this.active.task.targetTuple).toFixed(6))
      };
      this.results.push(result);
      this.record("task_complete", result);
      this.active = null;
      return { complete: true, result: { ...result } };
    }

    skip(reason = "participant_skipped") {
      if (!this.active) throw new Error("no active task");
      const elapsed = Math.max(0, this.elapsedMs() - this.active.startedAtMs);
      const result = {
        task_id: this.active.task.id,
        status: "SKIP",
        elapsed_ms: elapsed,
        actions: this.active.actionCount,
        wrong_dimension_actions: this.active.wrongDimensionActions,
        reason
      };
      this.results.push(result);
      this.record("task_skip", result);
      this.active = null;
      return { ...result };
    }

    setDebrief({ reflectionLocation, mapMeaning, preference = "not_asked", comments = "" }) {
      const locations = new Set(["left_wing", "right_wing", "head", "unsure"]);
      const meanings = new Set(["approximate_similarity", "literal_model_geometry", "capability", "unsure"]);
      const preferences = new Set(["embodied", "flat", "no_preference", "not_asked"]);
      if (!locations.has(reflectionLocation)) throw new Error("invalid reflection_location");
      if (!meanings.has(mapMeaning)) throw new Error("invalid map_meaning");
      if (!preferences.has(preference)) throw new Error("invalid preference");
      this.debrief = {
        reflection_location: reflectionLocation,
        map_meaning: mapMeaning,
        preference,
        comments: String(comments).slice(0, 1_000)
      };
      this.record("debrief_saved", { ...this.debrief });
      return { ...this.debrief };
    }

    receipt() {
      return {
        schema_version: schemaVersion,
        study_id: studyId,
        participant_id: this.participantId,
        round: this.round,
        condition: this.condition,
        completed_tasks: this.results.filter((result) => result.status === "PASS").length,
        task_results: this.results.map((result) => ({ ...result })),
        debrief: this.debrief ? { ...this.debrief } : null,
        events: this.events.map((event) => ({ ...event }))
      };
    }
  }

  return Object.freeze({
    schemaVersion,
    studyId,
    tupleOrder: Object.freeze(tupleOrder.slice()),
    tasks,
    stableParity,
    conditionFor,
    tupleError,
    nearTuple,
    StudySession
  });
});
