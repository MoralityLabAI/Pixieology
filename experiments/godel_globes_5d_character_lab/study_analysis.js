(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.GodelCharacterStudyAnalysis = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const expectedStudyId = "godel_globes_5d_character_ab_v1";
  const expectedTaskCount = 5;

  function median(values) {
    if (!values.length) return null;
    const ordered = values.slice().sort((a, b) => a - b);
    const middle = Math.floor(ordered.length / 2);
    return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
  }

  function validateReceipt(receipt) {
    if (!receipt || typeof receipt !== "object") throw new TypeError("receipt must be an object");
    if (receipt.study_id !== expectedStudyId) throw new Error(`unexpected study_id ${receipt.study_id}`);
    if (!receipt.participant_id) throw new Error("participant_id is required");
    if (!["embodied", "flat"].includes(receipt.condition)) throw new Error("invalid condition");
    if (![1, 2].includes(receipt.round)) throw new Error("invalid round");
    if (!Array.isArray(receipt.task_results)) throw new Error("task_results must be an array");
  }

  function summarizeReceipt(receipt) {
    const passed = receipt.task_results.filter((result) => result.status === "PASS");
    return {
      participant_id: receipt.participant_id,
      condition: receipt.condition,
      round: receipt.round,
      task_count: receipt.task_results.length,
      passed_tasks: passed.length,
      completion_rate: passed.length / expectedTaskCount,
      elapsed_ms: receipt.task_results.reduce((sum, result) => sum + (Number(result.elapsed_ms) || 0), 0),
      wrong_dimension_actions: receipt.task_results.reduce(
        (sum, result) => sum + (Number(result.wrong_dimension_actions) || 0), 0
      ),
      debrief: receipt.debrief || null
    };
  }

  function gate(condition, ready) {
    if (!ready) return "NOT_RUN";
    return condition ? "PASS" : "FAIL";
  }

  function analyze(receipts, minimumParticipants = 6) {
    if (!Array.isArray(receipts)) throw new TypeError("receipts must be an array");
    if (!Number.isInteger(minimumParticipants) || minimumParticipants < 1) {
      throw new RangeError("minimumParticipants must be a positive integer");
    }
    receipts.forEach(validateReceipt);

    const byParticipant = new Map();
    const seen = new Set();
    receipts.forEach((receipt) => {
      const key = `${receipt.participant_id}::${receipt.condition}`;
      if (seen.has(key)) throw new Error(`duplicate condition receipt ${key}`);
      seen.add(key);
      const bucket = byParticipant.get(receipt.participant_id) || {};
      bucket[receipt.condition] = summarizeReceipt(receipt);
      byParticipant.set(receipt.participant_id, bucket);
    });

    const paired = Array.from(byParticipant.entries())
      .filter(([, conditions]) => conditions.embodied && conditions.flat)
      .map(([participantId, conditions]) => ({ participantId, ...conditions }));
    const ready = paired.length >= minimumParticipants;
    const conditionSummary = {};
    ["embodied", "flat"].forEach((condition) => {
      const rows = paired.map((pair) => pair[condition]);
      conditionSummary[condition] = {
        participants: rows.length,
        mean_completion_rate: rows.length
          ? Number((rows.reduce((sum, row) => sum + row.completion_rate, 0) / rows.length).toFixed(6))
          : null,
        median_elapsed_ms: median(rows.map((row) => row.elapsed_ms)),
        median_wrong_dimension_actions: median(rows.map((row) => row.wrong_dimension_actions))
      };
    });

    const finalDebriefs = paired
      .map((pair) => [pair.embodied, pair.flat].sort((a, b) => b.round - a.round).find((row) => row.debrief)?.debrief)
      .filter(Boolean);
    const humanThreshold = Math.ceil(paired.length * (5 / 6));
    const anatomyCorrect = finalDebriefs.filter((item) => item.reflection_location === "head").length;
    const mapCorrect = finalDebriefs.filter((item) => item.map_meaning === "approximate_similarity").length;
    const preferences = { embodied: 0, flat: 0, no_preference: 0, not_asked: 0 };
    finalDebriefs.forEach((item) => {
      if (Object.hasOwn(preferences, item.preference)) preferences[item.preference] += 1;
    });

    const allTasksPresent = paired.every((pair) =>
      pair.embodied.task_count === expectedTaskCount && pair.flat.task_count === expectedTaskCount
    );
    const completionNoninferior = ready &&
      conditionSummary.embodied.mean_completion_rate >= conditionSummary.flat.mean_completion_rate;
    const timeNoninferior = ready && conditionSummary.flat.median_elapsed_ms > 0 &&
      conditionSummary.embodied.median_elapsed_ms <= conditionSummary.flat.median_elapsed_ms * 1.1;
    const errorNoninferior = ready &&
      conditionSummary.embodied.median_wrong_dimension_actions <= conditionSummary.flat.median_wrong_dimension_actions;
    const gates = {
      minimum_paired_sample: gate(ready, true),
      complete_task_receipts: gate(allTasksPresent, ready),
      completion_noninferiority: gate(completionNoninferior, ready),
      time_noninferiority_10pct: gate(timeNoninferior, ready),
      dimension_error_noninferiority: gate(errorNoninferior, ready),
      anatomy_comprehension_5_of_6: gate(finalDebriefs.length >= minimumParticipants && anatomyCorrect >= humanThreshold, ready),
      map_semantics_5_of_6: gate(finalDebriefs.length >= minimumParticipants && mapCorrect >= humanThreshold, ready)
    };
    gates.minimum_paired_sample = ready ? "PASS" : "NOT_RUN";
    const decisive = Object.values(gates).every((status) => status !== "NOT_RUN");
    const status = decisive
      ? (Object.values(gates).every((item) => item === "PASS") ? "PASS" : "FAIL")
      : "NOT_RUN";

    return {
      schema_version: 1,
      study_id: expectedStudyId,
      status,
      minimum_participants: minimumParticipants,
      paired_participants: paired.length,
      condition_summary: conditionSummary,
      human_debrief: {
        responses: finalDebriefs.length,
        reflection_on_head: anatomyCorrect,
        approximate_similarity_answer: mapCorrect,
        preference: preferences
      },
      gates
    };
  }

  return Object.freeze({ expectedStudyId, expectedTaskCount, median, analyze });
});
