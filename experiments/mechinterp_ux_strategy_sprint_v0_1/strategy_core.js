(function (root, factory) {
  const value = factory();
  if (typeof module === "object" && module.exports) module.exports = value;
  root.PixieMechinterpUXCore = value;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function participantSeed(participantId) {
    const text = String(participantId || "").trim().toUpperCase();
    if (!/^[A-Z][A-Z0-9_-]{1,15}$/.test(text)) {
      throw new Error("participant code must be 2–16 anonymous letters, digits, underscores, or hyphens");
    }
    return [...text].reduce((total, character) => ((total * 33) + character.charCodeAt(0)) >>> 0, 5381);
  }

  function rotate(values, offset) {
    if (!values.length) return [];
    const index = ((offset % values.length) + values.length) % values.length;
    return values.slice(index).concat(values.slice(0, index));
  }

  function workflowSchedule(participantId, taskSet) {
    const seed = participantSeed(participantId);
    const conditions = seed % 2 ? ["baseline", "triage_progressive"] : ["triage_progressive", "baseline"];
    const caseSets = seed % 2 ? ["a", "b"] : ["b", "a"];
    const schedule = [];
    conditions.forEach((condition, conditionIndex) => {
      rotate(taskSet.workflow, seed + conditionIndex).forEach((task) => {
        const caseKey = caseSets[conditionIndex];
        const caseId = task.pairs[caseKey];
        schedule.push({
          task_id: `workflow-${condition}-${task.task_type}-${caseKey}`,
          lane: "workflow",
          condition,
          design_question: "workflow",
          variant: condition,
          task_type: task.task_type,
          case_id: caseId,
          prompt: task.prompt,
          answer_type: task.answer_type,
          options: task.options || [],
          starting_state: task.state_by_case[caseId]
        });
      });
    });
    return schedule;
  }

  function componentSchedule(participantId, taskSet) {
    const seed = participantSeed(participantId);
    const byType = new Map(taskSet.workflow.map((task) => [task.task_type, task]));
    return rotate(taskSet.components, seed).map((component, index) => {
      const task = byType.get(component.task_type);
      return {
        task_id: `component-${component.design_question}-${component.variant}-${index}`,
        lane: "components",
        condition: "component_lab",
        design_question: component.design_question,
        variant: component.variant,
        task_type: component.task_type,
        case_id: component.case_id,
        prompt: task.prompt,
        answer_type: task.answer_type,
        options: task.options || [],
        starting_state: task.state_by_case[component.case_id]
      };
    });
  }

  function schedule(participantId, lane, taskSet) {
    if (lane === "workflow") return workflowSchedule(participantId, taskSet);
    if (lane === "components") return componentSchedule(participantId, taskSet);
    throw new Error(`unknown study lane ${lane}`);
  }

  function conditionQuery(task) {
    if (task.lane === "workflow") return task.condition === "baseline" ? {} : {
      orientation: "heatmap",
      threshold: "dendrogram_births",
      language: "dual",
      jobs: "gated"
    };
    const value = {
      orientation: "heatmap",
      threshold: "dendrogram_births",
      language: "dual",
      jobs: "gated"
    };
    value[task.design_question] = task.variant;
    return value;
  }

  return Object.freeze({
    participantSeed,
    workflowSchedule,
    componentSchedule,
    schedule,
    conditionQuery
  });
});
