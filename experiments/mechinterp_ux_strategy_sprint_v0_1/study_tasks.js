(function (root, factory) {
  const value = factory();
  if (typeof module === "object" && module.exports) module.exports = value;
  root.PixieMechinterpUXTasks = value;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const relationOptions = Object.freeze([
    { value: "direct", label: "Directly glued" },
    { value: "closure_only", label: "Same closure component, not directly glued" },
    { value: "none", label: "Neither" }
  ]);
  const robustnessOptions = Object.freeze([
    { value: "bridge_free_clique", label: "Bridge-free clique" },
    { value: "chained", label: "Chained through an articulation sheet" },
    { value: "isolated", label: "Isolated" }
  ]);
  const jobOptions = Object.freeze([
    { value: "reference_evaluation_only", label: "Inspect the base/Pixie reference evaluations only" },
    { value: "tinylora", label: "Propose a motif-local TinyLoRA" },
    { value: "qlora", label: "Propose an all-layer QLoRA" },
    { value: "authorize", label: "Authorize the selected job in the browser" }
  ]);

  const workflow = Object.freeze([
    {
      task_type: "band",
      prompt: "At what first depth W do Query and Key become directly glued over the displayed chart?",
      answer_type: "integer",
      pairs: Object.freeze({ a: "ux-band-a", b: "ux-band-b" }),
      state_by_case: Object.freeze({
        "ux-band-a": { layer: 4, module_id: "q_proj", chart_radius: 1, glue_tolerance: 0.14 },
        "ux-band-b": { layer: 14, module_id: "q_proj", chart_radius: 1, glue_tolerance: 0.14 }
      })
    },
    {
      task_type: "relation",
      prompt: "At the supplied depth, what is the relation between Query and Value?",
      answer_type: "choice",
      options: relationOptions,
      pairs: Object.freeze({ a: "ux-chain-a", b: "ux-chain-b" }),
      state_by_case: Object.freeze({
        "ux-chain-a": { layer: 8, module_id: "q_proj", chart_radius: 2, glue_tolerance: 0.12 },
        "ux-chain-b": { layer: 19, module_id: "q_proj", chart_radius: 2, glue_tolerance: 0.12 }
      })
    },
    {
      task_type: "robustness",
      prompt: "How should the selected Query component be described at this depth?",
      answer_type: "choice",
      options: robustnessOptions,
      pairs: Object.freeze({ a: "ux-robust-a", b: "ux-robust-b" }),
      state_by_case: Object.freeze({
        "ux-robust-a": { layer: 9, module_id: "q_proj", chart_radius: 2, glue_tolerance: 0.12 },
        "ux-robust-b": { layer: 20, module_id: "q_proj", chart_radius: 2, glue_tolerance: 0.12 }
      })
    },
    {
      task_type: "job",
      prompt: "The catalog has no confirmed motif. What may this interface legitimately offer next?",
      answer_type: "choice",
      options: jobOptions,
      pairs: Object.freeze({ a: "ux-null-a", b: "ux-null-b" }),
      state_by_case: Object.freeze({
        "ux-null-a": { layer: 7, module_id: "q_proj", chart_radius: 2, glue_tolerance: 0.12 },
        "ux-null-b": { layer: 21, module_id: "q_proj", chart_radius: 2, glue_tolerance: 0.12 }
      })
    }
  ]);

  const components = Object.freeze([
    { design_question: "orientation", variant: "heatmap", task_type: "band", case_id: "ux-band-a" },
    { design_question: "orientation", variant: "globe", task_type: "band", case_id: "ux-band-b" },
    { design_question: "orientation", variant: "case_first", task_type: "band", case_id: "ux-band-a" },
    { design_question: "threshold", variant: "slider", task_type: "relation", case_id: "ux-chain-a" },
    { design_question: "threshold", variant: "dendrogram_births", task_type: "relation", case_id: "ux-chain-b" },
    { design_question: "language", variant: "technical", task_type: "robustness", case_id: "ux-robust-a" },
    { design_question: "language", variant: "dual", task_type: "robustness", case_id: "ux-robust-b" },
    { design_question: "jobs", variant: "inline", task_type: "job", case_id: "ux-null-a" },
    { design_question: "jobs", variant: "gated", task_type: "job", case_id: "ux-null-b" }
  ]);

  return Object.freeze({
    schema: "pixieology_mechinterp_ux_task_set_v1",
    workflow,
    components,
    claimOptions: Object.freeze([
      { value: "descriptive_only", label: "Descriptive local topology only" },
      { value: "causal_mechanism", label: "A causal mechanism is established" },
      { value: "literal_branching", label: "Literal étale branching is established" },
      { value: "human_utility", label: "Human usefulness is established" }
    ])
  });
});
