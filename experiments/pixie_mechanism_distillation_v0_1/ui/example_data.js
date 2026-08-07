(function (root, factory) {
  const value = factory();
  if (typeof module === "object" && module.exports) module.exports = value;
  root.PixieMechanismLawLabData = value;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  return {
  "claim_boundary": "This example validates the Mechanism Law Lab interaction and data contracts only; it is not evidence about Qwen or Pixie internals.",
  "dataset_sha256": "0b60a82688d1b0b942e7fb61155ef976c365e2f45c2cab68e8ecd2dde34c1e9f",
  "design_lineage": [
    {
      "source": "Generating Interpretable Networks using Hypernetworks",
      "ui_move": "Treat state-count complexity as a phase scan, not a hidden tuning knob."
    },
    {
      "source": "MIPS / Distilling Machine-Learned Algorithms into Code",
      "ui_move": "Make the executable transition law the primary inspection object."
    },
    {
      "source": "The Clock and the Pizza",
      "ui_move": "Separate behavioral agreement from internal-mechanism agreement."
    },
    {
      "source": "Sparse Invariants",
      "ui_move": "Expose the smallest activation coordinate set that identifies states."
    }
  ],
  "evidence_class": "synthetic_implementation_fixture",
  "experiment_id": "pixie_mechanism_distillation_v0_1",
  "families": [
    {
      "alignments_by_state_count": {
        "1": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0
          },
          "matched_transitions": 2,
          "transition_union_count": 2
        },
        "2": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1
          },
          "matched_transitions": 4,
          "transition_union_count": 4
        },
        "3": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1,
            "2": 2
          },
          "matched_transitions": 6,
          "transition_union_count": 6
        }
      },
      "candidates": {
        "base_qwen_derived_1p7b": {
          "candidate": "base_qwen_derived_1p7b",
          "causal": {
            "causal_prediction_accuracy": 1,
            "matched_control_margin": 1,
            "matched_random_change_rate": 0,
            "mean_absolute_guardrail_delta": 0.0,
            "observation_count": 6,
            "status": "COMPLETE",
            "target_change_rate": 1
          },
          "description_length_bits": 462.0,
          "gates": {
            "causal_prediction": true,
            "guardrail": true,
            "matched_control": true,
            "program_fidelity": true,
            "sparse_invariant": true,
            "task_accuracy": true
          },
          "heldout_evaluation": {
            "candidate": "base_qwen_derived_1p7b",
            "case_count": 8,
            "heldout_program_fidelity": 1.0,
            "missing_transition_rate": 0.0,
            "output_fidelity": 1.0,
            "schema": "pixieology_mechanism_program_evaluation_v1",
            "sparse_invariant_agreement": 1.0,
            "split": "held_out",
            "step_count": 61,
            "task_accuracy": 1.0,
            "task_family_id": "fsm-00"
          },
          "interventions": [
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-00-0",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-00"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-00-1",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-00"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-00-2",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-00"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-00-3",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-00"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-00-4",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-00"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-00-5",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-00"
            }
          ],
          "phase_scan": [
            {
              "description_length_bits": 150.0,
              "discovery_fidelity": 0.8032786885245902,
              "heldout_fidelity": 0.7540983606557377,
              "output_fidelity": 0.7540983606557377,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0
                ],
                "unique_state_signatures": 1
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 1,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.5862068965517241,
                  "state": 0,
                  "support": 29
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 32
                }
              ]
            },
            {
              "description_length_bits": 300.0,
              "discovery_fidelity": 0.8032786885245902,
              "heldout_fidelity": 0.7704918032786885,
              "output_fidelity": 0.9344262295081968,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  2
                ],
                "unique_state_signatures": 2
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 2,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.8095238095238095,
                  "state": 0,
                  "support": 21
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.6,
                  "state": 0,
                  "support": 20
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 12
                }
              ]
            },
            {
              "description_length_bits": 462.0,
              "discovery_fidelity": 1.0,
              "heldout_fidelity": 1.0,
              "output_fidelity": 1.0,
              "qualified": true,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  1
                ],
                "unique_state_signatures": 3
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 3,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 17
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 8
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 12
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 12
                }
              ]
            }
          ],
          "program_sha256": "d5b49de78d34d54b39b889f00806417885f03e8ece83ba97ccdf79ca76899115",
          "selected_state_count": 3,
          "sparse_invariant": {
            "maximum_dimensions": 3,
            "method": "sparse_centroid_signature_v1",
            "minimum_squared_state_separation": 0.25,
            "selected_dimensions": [
              0,
              1
            ],
            "unique_state_signatures": 3
          },
          "transition_table": [
            {
              "input_symbol": "I0",
              "next_state": 2,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 0,
              "support": 17
            },
            {
              "input_symbol": "I1",
              "next_state": 1,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 0,
              "support": 8
            },
            {
              "input_symbol": "I0",
              "next_state": 0,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 1,
              "support": 8
            },
            {
              "input_symbol": "I1",
              "next_state": 1,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 1,
              "support": 12
            },
            {
              "input_symbol": "I0",
              "next_state": 1,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 2,
              "support": 4
            },
            {
              "input_symbol": "I1",
              "next_state": 0,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 2,
              "support": 12
            }
          ]
        },
        "pixie_rank8": {
          "candidate": "pixie_rank8",
          "causal": {
            "causal_prediction_accuracy": 1,
            "matched_control_margin": 1,
            "matched_random_change_rate": 0,
            "mean_absolute_guardrail_delta": 0.0,
            "observation_count": 6,
            "status": "COMPLETE",
            "target_change_rate": 1
          },
          "description_length_bits": 462.0,
          "gates": {
            "causal_prediction": true,
            "guardrail": true,
            "matched_control": true,
            "program_fidelity": true,
            "sparse_invariant": true,
            "task_accuracy": true
          },
          "heldout_evaluation": {
            "candidate": "pixie_rank8",
            "case_count": 8,
            "heldout_program_fidelity": 1.0,
            "missing_transition_rate": 0.0,
            "output_fidelity": 1.0,
            "schema": "pixieology_mechanism_program_evaluation_v1",
            "sparse_invariant_agreement": 1.0,
            "split": "held_out",
            "step_count": 61,
            "task_accuracy": 1.0,
            "task_family_id": "fsm-00"
          },
          "interventions": [
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-00-0",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-00"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-00-1",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-00"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-00-2",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-00"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-00-3",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-00"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-00-4",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-00"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-00-5",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-00"
            }
          ],
          "phase_scan": [
            {
              "description_length_bits": 150.0,
              "discovery_fidelity": 0.8032786885245902,
              "heldout_fidelity": 0.7540983606557377,
              "output_fidelity": 0.7540983606557377,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0
                ],
                "unique_state_signatures": 1
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 1,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.5862068965517241,
                  "state": 0,
                  "support": 29
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 32
                }
              ]
            },
            {
              "description_length_bits": 300.0,
              "discovery_fidelity": 0.8032786885245902,
              "heldout_fidelity": 0.7704918032786885,
              "output_fidelity": 0.9344262295081968,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0
                ],
                "unique_state_signatures": 2
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 2,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.8095238095238095,
                  "state": 0,
                  "support": 21
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.6,
                  "state": 0,
                  "support": 20
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 12
                }
              ]
            },
            {
              "description_length_bits": 462.0,
              "discovery_fidelity": 1.0,
              "heldout_fidelity": 1.0,
              "output_fidelity": 1.0,
              "qualified": true,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  1
                ],
                "unique_state_signatures": 3
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 3,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 17
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 8
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 12
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 12
                }
              ]
            }
          ],
          "program_sha256": "2339e2015dbca32629efffd28562339d4b5f082b46edf24d5ca2ed5e0acdcaf1",
          "selected_state_count": 3,
          "sparse_invariant": {
            "maximum_dimensions": 3,
            "method": "sparse_centroid_signature_v1",
            "minimum_squared_state_separation": 0.25,
            "selected_dimensions": [
              0,
              1
            ],
            "unique_state_signatures": 3
          },
          "transition_table": [
            {
              "input_symbol": "I0",
              "next_state": 2,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 0,
              "support": 17
            },
            {
              "input_symbol": "I1",
              "next_state": 1,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 0,
              "support": 8
            },
            {
              "input_symbol": "I0",
              "next_state": 0,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 1,
              "support": 8
            },
            {
              "input_symbol": "I1",
              "next_state": 1,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 1,
              "support": 12
            },
            {
              "input_symbol": "I0",
              "next_state": 1,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 2,
              "support": 4
            },
            {
              "input_symbol": "I1",
              "next_state": 0,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 2,
              "support": 12
            }
          ]
        }
      },
      "comparison": {
        "description_length_reduction": 0.0,
        "evidence_class": "synthetic_or_incomplete",
        "isomorphism_verdict": "USABLE_ISOMORPHISM",
        "winner": "TIE"
      },
      "complexity_values": [
        1,
        2,
        3
      ],
      "default_complexity": 3,
      "oracle_shape": {
        "input_symbols": [
          "I0",
          "I1"
        ],
        "output_symbols": [
          "O0",
          "O1"
        ],
        "state_count": 3
      },
      "task_family_id": "fsm-00"
    },
    {
      "alignments_by_state_count": {
        "1": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0
          },
          "matched_transitions": 3,
          "transition_union_count": 3
        },
        "2": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1
          },
          "matched_transitions": 6,
          "transition_union_count": 6
        },
        "3": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1,
            "2": 2
          },
          "matched_transitions": 9,
          "transition_union_count": 9
        },
        "4": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3
          },
          "matched_transitions": 12,
          "transition_union_count": 12
        }
      },
      "candidates": {
        "base_qwen_derived_1p7b": {
          "candidate": "base_qwen_derived_1p7b",
          "causal": {
            "causal_prediction_accuracy": 1,
            "matched_control_margin": 1,
            "matched_random_change_rate": 0,
            "mean_absolute_guardrail_delta": 0.0,
            "observation_count": 8,
            "status": "COMPLETE",
            "target_change_rate": 1
          },
          "description_length_bits": 668.0,
          "gates": {
            "causal_prediction": true,
            "guardrail": true,
            "matched_control": true,
            "program_fidelity": true,
            "sparse_invariant": true,
            "task_accuracy": true
          },
          "heldout_evaluation": {
            "candidate": "base_qwen_derived_1p7b",
            "case_count": 8,
            "heldout_program_fidelity": 1.0,
            "missing_transition_rate": 0.0,
            "output_fidelity": 1.0,
            "schema": "pixieology_mechanism_program_evaluation_v1",
            "sparse_invariant_agreement": 1.0,
            "split": "held_out",
            "step_count": 61,
            "task_accuracy": 1.0,
            "task_family_id": "fsm-01"
          },
          "interventions": [
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-01-0",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-01-1",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-01-2",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-01-3",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-01-4",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-01-5",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-01-6",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-01-7",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            }
          ],
          "phase_scan": [
            {
              "description_length_bits": 161.0,
              "discovery_fidelity": 0.6065573770491803,
              "heldout_fidelity": 0.5737704918032787,
              "output_fidelity": 0.5737704918032787,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0
                ],
                "unique_state_signatures": 1
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 1,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 0.6666666666666666,
                  "state": 0,
                  "support": 18
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 0.5238095238095238,
                  "state": 0,
                  "support": 21
                },
                {
                  "input_symbol": "I2",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 0.6363636363636364,
                  "state": 0,
                  "support": 22
                }
              ]
            },
            {
              "description_length_bits": 322.0,
              "discovery_fidelity": 0.7377049180327869,
              "heldout_fidelity": 0.7213114754098361,
              "output_fidelity": 0.7213114754098361,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  1
                ],
                "unique_state_signatures": 2
              },
              "sparse_invariant_agreement": 0.7213114754098361,
              "state_count": 2,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 0.7692307692307693,
                  "state": 0,
                  "support": 13
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.7692307692307693,
                  "state": 0,
                  "support": 13
                },
                {
                  "input_symbol": "I2",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 0.7142857142857143,
                  "state": 0,
                  "support": 14
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.6,
                  "state": 1,
                  "support": 5
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I2",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 0.5,
                  "state": 1,
                  "support": 8
                }
              ]
            },
            {
              "description_length_bits": 501.0,
              "discovery_fidelity": 0.9016393442622951,
              "heldout_fidelity": 0.9180327868852459,
              "output_fidelity": 0.9180327868852459,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  1
                ],
                "unique_state_signatures": 3
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 3,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 10
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 3
                },
                {
                  "input_symbol": "I2",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 4
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.6,
                  "state": 1,
                  "support": 5
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I2",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 0.5,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 3
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 10
                },
                {
                  "input_symbol": "I2",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 10
                }
              ]
            },
            {
              "description_length_bits": 668.0,
              "discovery_fidelity": 1.0,
              "heldout_fidelity": 1.0,
              "output_fidelity": 1.0,
              "qualified": true,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  1,
                  2
                ],
                "unique_state_signatures": 4
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 4,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 10
                },
                {
                  "input_symbol": "I1",
                  "next_state": 3,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 3
                },
                {
                  "input_symbol": "I2",
                  "next_state": 3,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 4
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 3
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 4
                },
                {
                  "input_symbol": "I2",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 4
                },
                {
                  "input_symbol": "I0",
                  "next_state": 3,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 3
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 10
                },
                {
                  "input_symbol": "I2",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 10
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 3,
                  "support": 4
                },
                {
                  "input_symbol": "I2",
                  "next_state": 3,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 3,
                  "support": 4
                }
              ]
            }
          ],
          "program_sha256": "77de7c3f646901eea2d084efc7e2a4caeb5f559b662ffe0bf4bc7eb9e8e6a7fc",
          "selected_state_count": 4,
          "sparse_invariant": {
            "maximum_dimensions": 3,
            "method": "sparse_centroid_signature_v1",
            "minimum_squared_state_separation": 0.25,
            "selected_dimensions": [
              0,
              1,
              2
            ],
            "unique_state_signatures": 4
          },
          "transition_table": [
            {
              "input_symbol": "I0",
              "next_state": 2,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 0,
              "support": 10
            },
            {
              "input_symbol": "I1",
              "next_state": 3,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 0,
              "support": 3
            },
            {
              "input_symbol": "I2",
              "next_state": 3,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 0,
              "support": 4
            },
            {
              "input_symbol": "I0",
              "next_state": 0,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 1,
              "support": 3
            },
            {
              "input_symbol": "I1",
              "next_state": 0,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 1,
              "support": 4
            },
            {
              "input_symbol": "I2",
              "next_state": 2,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 1,
              "support": 4
            },
            {
              "input_symbol": "I0",
              "next_state": 3,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 2,
              "support": 3
            },
            {
              "input_symbol": "I1",
              "next_state": 2,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 2,
              "support": 10
            },
            {
              "input_symbol": "I2",
              "next_state": 1,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 2,
              "support": 10
            },
            {
              "input_symbol": "I0",
              "next_state": 1,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 3,
              "support": 2
            },
            {
              "input_symbol": "I1",
              "next_state": 0,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 3,
              "support": 4
            },
            {
              "input_symbol": "I2",
              "next_state": 3,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 3,
              "support": 4
            }
          ]
        },
        "pixie_rank8": {
          "candidate": "pixie_rank8",
          "causal": {
            "causal_prediction_accuracy": 1,
            "matched_control_margin": 1,
            "matched_random_change_rate": 0,
            "mean_absolute_guardrail_delta": 0.0,
            "observation_count": 8,
            "status": "COMPLETE",
            "target_change_rate": 1
          },
          "description_length_bits": 668.0,
          "gates": {
            "causal_prediction": true,
            "guardrail": true,
            "matched_control": true,
            "program_fidelity": true,
            "sparse_invariant": true,
            "task_accuracy": true
          },
          "heldout_evaluation": {
            "candidate": "pixie_rank8",
            "case_count": 8,
            "heldout_program_fidelity": 1.0,
            "missing_transition_rate": 0.0,
            "output_fidelity": 1.0,
            "schema": "pixieology_mechanism_program_evaluation_v1",
            "sparse_invariant_agreement": 1.0,
            "split": "held_out",
            "step_count": 61,
            "task_accuracy": 1.0,
            "task_family_id": "fsm-01"
          },
          "interventions": [
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-01-0",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-01-1",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-01-2",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-01-3",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-01-4",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-01-5",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-01-6",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-01-7",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-01"
            }
          ],
          "phase_scan": [
            {
              "description_length_bits": 161.0,
              "discovery_fidelity": 0.6065573770491803,
              "heldout_fidelity": 0.5737704918032787,
              "output_fidelity": 0.5737704918032787,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0
                ],
                "unique_state_signatures": 1
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 1,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 0.6666666666666666,
                  "state": 0,
                  "support": 18
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 0.5238095238095238,
                  "state": 0,
                  "support": 21
                },
                {
                  "input_symbol": "I2",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 0.6363636363636364,
                  "state": 0,
                  "support": 22
                }
              ]
            },
            {
              "description_length_bits": 322.0,
              "discovery_fidelity": 0.7377049180327869,
              "heldout_fidelity": 0.7213114754098361,
              "output_fidelity": 0.7213114754098361,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  2
                ],
                "unique_state_signatures": 2
              },
              "sparse_invariant_agreement": 0.7213114754098361,
              "state_count": 2,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 0.7692307692307693,
                  "state": 0,
                  "support": 13
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.7692307692307693,
                  "state": 0,
                  "support": 13
                },
                {
                  "input_symbol": "I2",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 0.7142857142857143,
                  "state": 0,
                  "support": 14
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.6,
                  "state": 1,
                  "support": 5
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I2",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 0.5,
                  "state": 1,
                  "support": 8
                }
              ]
            },
            {
              "description_length_bits": 501.0,
              "discovery_fidelity": 0.9016393442622951,
              "heldout_fidelity": 0.9180327868852459,
              "output_fidelity": 0.9180327868852459,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  1,
                  2
                ],
                "unique_state_signatures": 3
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 3,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 10
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 3
                },
                {
                  "input_symbol": "I2",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 4
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.6,
                  "state": 1,
                  "support": 5
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I2",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 0.5,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 3
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 10
                },
                {
                  "input_symbol": "I2",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 10
                }
              ]
            },
            {
              "description_length_bits": 668.0,
              "discovery_fidelity": 1.0,
              "heldout_fidelity": 1.0,
              "output_fidelity": 1.0,
              "qualified": true,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  1,
                  2
                ],
                "unique_state_signatures": 4
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 4,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 10
                },
                {
                  "input_symbol": "I1",
                  "next_state": 3,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 3
                },
                {
                  "input_symbol": "I2",
                  "next_state": 3,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 4
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 3
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 4
                },
                {
                  "input_symbol": "I2",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 4
                },
                {
                  "input_symbol": "I0",
                  "next_state": 3,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 3
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 10
                },
                {
                  "input_symbol": "I2",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 10
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 3,
                  "support": 4
                },
                {
                  "input_symbol": "I2",
                  "next_state": 3,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 3,
                  "support": 4
                }
              ]
            }
          ],
          "program_sha256": "baeab5a1ad26d1caab0f0ecf34fd286a0f46c5dd860ae82d57994fdb96fcf6b6",
          "selected_state_count": 4,
          "sparse_invariant": {
            "maximum_dimensions": 3,
            "method": "sparse_centroid_signature_v1",
            "minimum_squared_state_separation": 0.25,
            "selected_dimensions": [
              0,
              1,
              2
            ],
            "unique_state_signatures": 4
          },
          "transition_table": [
            {
              "input_symbol": "I0",
              "next_state": 2,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 0,
              "support": 10
            },
            {
              "input_symbol": "I1",
              "next_state": 3,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 0,
              "support": 3
            },
            {
              "input_symbol": "I2",
              "next_state": 3,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 0,
              "support": 4
            },
            {
              "input_symbol": "I0",
              "next_state": 0,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 1,
              "support": 3
            },
            {
              "input_symbol": "I1",
              "next_state": 0,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 1,
              "support": 4
            },
            {
              "input_symbol": "I2",
              "next_state": 2,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 1,
              "support": 4
            },
            {
              "input_symbol": "I0",
              "next_state": 3,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 2,
              "support": 3
            },
            {
              "input_symbol": "I1",
              "next_state": 2,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 2,
              "support": 10
            },
            {
              "input_symbol": "I2",
              "next_state": 1,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 2,
              "support": 10
            },
            {
              "input_symbol": "I0",
              "next_state": 1,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 3,
              "support": 2
            },
            {
              "input_symbol": "I1",
              "next_state": 0,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 3,
              "support": 4
            },
            {
              "input_symbol": "I2",
              "next_state": 3,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 3,
              "support": 4
            }
          ]
        }
      },
      "comparison": {
        "description_length_reduction": 0.0,
        "evidence_class": "synthetic_or_incomplete",
        "isomorphism_verdict": "USABLE_ISOMORPHISM",
        "winner": "TIE"
      },
      "complexity_values": [
        1,
        2,
        3,
        4
      ],
      "default_complexity": 4,
      "oracle_shape": {
        "input_symbols": [
          "I0",
          "I1",
          "I2"
        ],
        "output_symbols": [
          "O0",
          "O1"
        ],
        "state_count": 4
      },
      "task_family_id": "fsm-01"
    },
    {
      "alignments_by_state_count": {
        "1": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0
          },
          "matched_transitions": 4,
          "transition_union_count": 4
        },
        "2": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1
          },
          "matched_transitions": 8,
          "transition_union_count": 8
        },
        "3": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1,
            "2": 2
          },
          "matched_transitions": 8,
          "transition_union_count": 9
        },
        "4": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3
          },
          "matched_transitions": 7,
          "transition_union_count": 10
        },
        "5": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3,
            "4": 4
          },
          "matched_transitions": 9,
          "transition_union_count": 14
        }
      },
      "candidates": {
        "base_qwen_derived_1p7b": {
          "candidate": "base_qwen_derived_1p7b",
          "causal": {
            "causal_prediction_accuracy": 1,
            "matched_control_margin": 1,
            "matched_random_change_rate": 0,
            "mean_absolute_guardrail_delta": 0.0,
            "observation_count": 8,
            "status": "COMPLETE",
            "target_change_rate": 1
          },
          "description_length_bits": 775.0,
          "gates": {
            "causal_prediction": true,
            "guardrail": true,
            "matched_control": true,
            "program_fidelity": true,
            "sparse_invariant": true,
            "task_accuracy": false
          },
          "heldout_evaluation": {
            "candidate": "base_qwen_derived_1p7b",
            "case_count": 8,
            "heldout_program_fidelity": 0.9508196721311475,
            "missing_transition_rate": 0.04918032786885246,
            "output_fidelity": 0.9508196721311475,
            "schema": "pixieology_mechanism_program_evaluation_v1",
            "sparse_invariant_agreement": 0.9836065573770492,
            "split": "held_out",
            "step_count": 61,
            "task_accuracy": 0.625,
            "task_family_id": "fsm-02"
          },
          "interventions": [
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-02-0",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-02-1",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-02-2",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-02-3",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-02-4",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-02-5",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-02-6",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-02-7",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            }
          ],
          "phase_scan": [
            {
              "description_length_bits": 172.0,
              "discovery_fidelity": 0.8852459016393442,
              "heldout_fidelity": 0.8688524590163934,
              "output_fidelity": 0.8688524590163934,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0
                ],
                "unique_state_signatures": 1
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 1,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.75,
                  "state": 0,
                  "support": 16
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 0.8333333333333334,
                  "state": 0,
                  "support": 18
                },
                {
                  "input_symbol": "I2",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 15
                },
                {
                  "input_symbol": "I3",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 12
                }
              ]
            },
            {
              "description_length_bits": 344.0,
              "discovery_fidelity": 0.9344262295081968,
              "heldout_fidelity": 0.9180327868852459,
              "output_fidelity": 0.9672131147540983,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  1
                ],
                "unique_state_signatures": 2
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 2,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 15
                },
                {
                  "input_symbol": "I2",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 13
                },
                {
                  "input_symbol": "I3",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 11
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.6666666666666666,
                  "state": 1,
                  "support": 12
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 3
                },
                {
                  "input_symbol": "I2",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 2
                },
                {
                  "input_symbol": "I3",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 1
                }
              ]
            },
            {
              "description_length_bits": 488.0,
              "discovery_fidelity": 0.9344262295081968,
              "heldout_fidelity": 0.9180327868852459,
              "output_fidelity": 0.9672131147540983,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  1,
                  4
                ],
                "unique_state_signatures": 3
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 3,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 0.6666666666666666,
                  "state": 0,
                  "support": 12
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 3
                },
                {
                  "input_symbol": "I3",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 1
                },
                {
                  "input_symbol": "I2",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 2
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 15
                },
                {
                  "input_symbol": "I2",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 13
                },
                {
                  "input_symbol": "I3",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 11
                }
              ]
            },
            {
              "description_length_bits": 603.0,
              "discovery_fidelity": 0.9508196721311475,
              "heldout_fidelity": 0.9508196721311475,
              "output_fidelity": 0.9508196721311475,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  2,
                  4
                ],
                "unique_state_signatures": 4
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 4,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 8
                },
                {
                  "input_symbol": "I2",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 2
                },
                {
                  "input_symbol": "I0",
                  "next_state": 3,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 0.8333333333333334,
                  "state": 2,
                  "support": 18
                },
                {
                  "input_symbol": "I2",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 13
                },
                {
                  "input_symbol": "I3",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 12
                },
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 3,
                  "support": 4
                }
              ]
            },
            {
              "description_length_bits": 775.0,
              "discovery_fidelity": 1.0,
              "heldout_fidelity": 0.9508196721311475,
              "output_fidelity": 0.9508196721311475,
              "qualified": true,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  1,
                  4
                ],
                "unique_state_signatures": 4
              },
              "sparse_invariant_agreement": 0.9836065573770492,
              "state_count": 5,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 8
                },
                {
                  "input_symbol": "I2",
                  "next_state": 4,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 2
                },
                {
                  "input_symbol": "I0",
                  "next_state": 3,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 15
                },
                {
                  "input_symbol": "I2",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 13
                },
                {
                  "input_symbol": "I3",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 11
                },
                {
                  "input_symbol": "I0",
                  "next_state": 4,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 3,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 4,
                  "support": 3
                },
                {
                  "input_symbol": "I3",
                  "next_state": 4,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 4,
                  "support": 1
                }
              ]
            }
          ],
          "program_sha256": "190677b69cddc9b746078a6877bd0a89869aecac466788b6d099f8266d973049",
          "selected_state_count": 5,
          "sparse_invariant": {
            "maximum_dimensions": 3,
            "method": "sparse_centroid_signature_v1",
            "minimum_squared_state_separation": 0.25,
            "selected_dimensions": [
              0,
              1,
              4
            ],
            "unique_state_signatures": 4
          },
          "transition_table": [
            {
              "input_symbol": "I0",
              "next_state": 2,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 0,
              "support": 8
            },
            {
              "input_symbol": "I2",
              "next_state": 4,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 1,
              "support": 2
            },
            {
              "input_symbol": "I0",
              "next_state": 3,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 2,
              "support": 4
            },
            {
              "input_symbol": "I1",
              "next_state": 2,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 2,
              "support": 15
            },
            {
              "input_symbol": "I2",
              "next_state": 2,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 2,
              "support": 13
            },
            {
              "input_symbol": "I3",
              "next_state": 2,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 2,
              "support": 11
            },
            {
              "input_symbol": "I0",
              "next_state": 4,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 3,
              "support": 4
            },
            {
              "input_symbol": "I1",
              "next_state": 1,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 4,
              "support": 3
            },
            {
              "input_symbol": "I3",
              "next_state": 4,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 4,
              "support": 1
            }
          ]
        },
        "pixie_rank8": {
          "candidate": "pixie_rank8",
          "causal": {
            "causal_prediction_accuracy": 1,
            "matched_control_margin": 1,
            "matched_random_change_rate": 0,
            "mean_absolute_guardrail_delta": 0.0,
            "observation_count": 8,
            "status": "COMPLETE",
            "target_change_rate": 1
          },
          "description_length_bits": 775.0,
          "gates": {
            "causal_prediction": true,
            "guardrail": true,
            "matched_control": true,
            "program_fidelity": true,
            "sparse_invariant": true,
            "task_accuracy": false
          },
          "heldout_evaluation": {
            "candidate": "pixie_rank8",
            "case_count": 8,
            "heldout_program_fidelity": 0.9508196721311475,
            "missing_transition_rate": 0.04918032786885246,
            "output_fidelity": 0.9508196721311475,
            "schema": "pixieology_mechanism_program_evaluation_v1",
            "sparse_invariant_agreement": 0.9836065573770492,
            "split": "held_out",
            "step_count": 61,
            "task_accuracy": 0.625,
            "task_family_id": "fsm-02"
          },
          "interventions": [
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-02-0",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-02-1",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-02-2",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-02-3",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-02-4",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-02-5",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-02-6",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            },
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-02-7",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-02"
            }
          ],
          "phase_scan": [
            {
              "description_length_bits": 172.0,
              "discovery_fidelity": 0.8852459016393442,
              "heldout_fidelity": 0.8688524590163934,
              "output_fidelity": 0.8688524590163934,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0
                ],
                "unique_state_signatures": 1
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 1,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.75,
                  "state": 0,
                  "support": 16
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 0.8333333333333334,
                  "state": 0,
                  "support": 18
                },
                {
                  "input_symbol": "I2",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 15
                },
                {
                  "input_symbol": "I3",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 12
                }
              ]
            },
            {
              "description_length_bits": 344.0,
              "discovery_fidelity": 0.9344262295081968,
              "heldout_fidelity": 0.9180327868852459,
              "output_fidelity": 0.9672131147540983,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  2
                ],
                "unique_state_signatures": 2
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 2,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 15
                },
                {
                  "input_symbol": "I2",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 13
                },
                {
                  "input_symbol": "I3",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 11
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.6666666666666666,
                  "state": 1,
                  "support": 12
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 3
                },
                {
                  "input_symbol": "I2",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 2
                },
                {
                  "input_symbol": "I3",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 1
                }
              ]
            },
            {
              "description_length_bits": 488.0,
              "discovery_fidelity": 0.9344262295081968,
              "heldout_fidelity": 0.9180327868852459,
              "output_fidelity": 0.9672131147540983,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  2
                ],
                "unique_state_signatures": 3
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 3,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 0.6666666666666666,
                  "state": 0,
                  "support": 12
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 3
                },
                {
                  "input_symbol": "I3",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 1
                },
                {
                  "input_symbol": "I2",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 2
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 15
                },
                {
                  "input_symbol": "I2",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 13
                },
                {
                  "input_symbol": "I3",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 11
                }
              ]
            },
            {
              "description_length_bits": 603.0,
              "discovery_fidelity": 0.9508196721311475,
              "heldout_fidelity": 0.9508196721311475,
              "output_fidelity": 0.9508196721311475,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  1,
                  3
                ],
                "unique_state_signatures": 4
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 4,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 8
                },
                {
                  "input_symbol": "I2",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 2
                },
                {
                  "input_symbol": "I0",
                  "next_state": 3,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 0.8333333333333334,
                  "state": 2,
                  "support": 18
                },
                {
                  "input_symbol": "I2",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 13
                },
                {
                  "input_symbol": "I3",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 12
                },
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 3,
                  "support": 4
                }
              ]
            },
            {
              "description_length_bits": 775.0,
              "discovery_fidelity": 1.0,
              "heldout_fidelity": 0.9508196721311475,
              "output_fidelity": 0.9508196721311475,
              "qualified": true,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  1,
                  2
                ],
                "unique_state_signatures": 4
              },
              "sparse_invariant_agreement": 0.9836065573770492,
              "state_count": 5,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 8
                },
                {
                  "input_symbol": "I2",
                  "next_state": 4,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 2
                },
                {
                  "input_symbol": "I0",
                  "next_state": 3,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 15
                },
                {
                  "input_symbol": "I2",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 2,
                  "support": 13
                },
                {
                  "input_symbol": "I3",
                  "next_state": 2,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 2,
                  "support": 11
                },
                {
                  "input_symbol": "I0",
                  "next_state": 4,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 3,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 4,
                  "support": 3
                },
                {
                  "input_symbol": "I3",
                  "next_state": 4,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 4,
                  "support": 1
                }
              ]
            }
          ],
          "program_sha256": "e630610ebd28cdaddee1fc3f834359b7f776d83d8e31782519cea6f6ef9275c3",
          "selected_state_count": 5,
          "sparse_invariant": {
            "maximum_dimensions": 3,
            "method": "sparse_centroid_signature_v1",
            "minimum_squared_state_separation": 0.25,
            "selected_dimensions": [
              0,
              1,
              2
            ],
            "unique_state_signatures": 4
          },
          "transition_table": [
            {
              "input_symbol": "I0",
              "next_state": 2,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 0,
              "support": 8
            },
            {
              "input_symbol": "I2",
              "next_state": 4,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 1,
              "support": 2
            },
            {
              "input_symbol": "I0",
              "next_state": 3,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 2,
              "support": 4
            },
            {
              "input_symbol": "I1",
              "next_state": 2,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 2,
              "support": 15
            },
            {
              "input_symbol": "I2",
              "next_state": 2,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 2,
              "support": 13
            },
            {
              "input_symbol": "I3",
              "next_state": 2,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 2,
              "support": 11
            },
            {
              "input_symbol": "I0",
              "next_state": 4,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 3,
              "support": 4
            },
            {
              "input_symbol": "I1",
              "next_state": 1,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 4,
              "support": 3
            },
            {
              "input_symbol": "I3",
              "next_state": 4,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 4,
              "support": 1
            }
          ]
        }
      },
      "comparison": {
        "description_length_reduction": 0.0,
        "evidence_class": "synthetic_or_incomplete",
        "isomorphism_verdict": "USABLE_ISOMORPHISM",
        "winner": "UNDETERMINED"
      },
      "complexity_values": [
        1,
        2,
        3,
        4,
        5
      ],
      "default_complexity": 5,
      "oracle_shape": {
        "input_symbols": [
          "I0",
          "I1",
          "I2",
          "I3"
        ],
        "output_symbols": [
          "O0",
          "O1"
        ],
        "state_count": 5
      },
      "task_family_id": "fsm-02"
    },
    {
      "alignments_by_state_count": {
        "1": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0
          },
          "matched_transitions": 2,
          "transition_union_count": 2
        },
        "2": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1
          },
          "matched_transitions": 4,
          "transition_union_count": 4
        },
        "3": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1,
            "2": 2
          },
          "matched_transitions": 6,
          "transition_union_count": 6
        },
        "4": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3
          },
          "matched_transitions": 8,
          "transition_union_count": 8
        },
        "5": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3,
            "4": 4
          },
          "matched_transitions": 10,
          "transition_union_count": 10
        },
        "6": {
          "available": true,
          "bijective": true,
          "fidelity": 1.0,
          "mapping": {
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3,
            "4": 4,
            "5": 5
          },
          "matched_transitions": 11,
          "transition_union_count": 12
        }
      },
      "candidates": {
        "base_qwen_derived_1p7b": {
          "candidate": "base_qwen_derived_1p7b",
          "causal": {
            "causal_prediction_accuracy": 1,
            "matched_control_margin": 1,
            "matched_random_change_rate": 0,
            "mean_absolute_guardrail_delta": 0.0,
            "observation_count": 8,
            "status": "COMPLETE",
            "target_change_rate": 1
          },
          "description_length_bits": 944.0,
          "gates": {
            "causal_prediction": true,
            "guardrail": true,
            "matched_control": true,
            "program_fidelity": true,
            "sparse_invariant": false,
            "task_accuracy": true
          },
          "heldout_evaluation": {
            "candidate": "base_qwen_derived_1p7b",
            "case_count": 8,
            "heldout_program_fidelity": 0.9836065573770492,
            "missing_transition_rate": 0.01639344262295082,
            "output_fidelity": 0.9836065573770492,
            "schema": "pixieology_mechanism_program_evaluation_v1",
            "sparse_invariant_agreement": 0.819672131147541,
            "split": "held_out",
            "step_count": 61,
            "task_accuracy": 0.875,
            "task_family_id": "fsm-03"
          },
          "interventions": [
            {
              "baseline_output_symbol": "O0",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "base_qwen_derived_1p7b-fsm-03-0",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-03-1",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-03-2",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-03-3",
              "observed_output_symbol": "O2",
              "predicted_output_symbol": "O2",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-03-4",
              "observed_output_symbol": "O2",
              "predicted_output_symbol": "O2",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-03-5",
              "observed_output_symbol": "O2",
              "predicted_output_symbol": "O2",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-03-6",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "base_qwen_derived_1p7b",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "base_qwen_derived_1p7b-fsm-03-7",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            }
          ],
          "phase_scan": [
            {
              "description_length_bits": 150.0,
              "discovery_fidelity": 0.5245901639344263,
              "heldout_fidelity": 0.5245901639344263,
              "output_fidelity": 0.5245901639344263,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0
                ],
                "unique_state_signatures": 1
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 1,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.46875,
                  "state": 0,
                  "support": 32
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O2",
                  "purity": 0.5862068965517241,
                  "state": 0,
                  "support": 29
                }
              ]
            },
            {
              "description_length_bits": 300.0,
              "discovery_fidelity": 0.5901639344262295,
              "heldout_fidelity": 0.639344262295082,
              "output_fidelity": 0.639344262295082,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  1
                ],
                "unique_state_signatures": 2
              },
              "sparse_invariant_agreement": 0.639344262295082,
              "state_count": 2,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.4583333333333333,
                  "state": 0,
                  "support": 24
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O2",
                  "purity": 0.7391304347826086,
                  "state": 0,
                  "support": 23
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 0.5,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.6666666666666666,
                  "state": 1,
                  "support": 6
                }
              ]
            },
            {
              "description_length_bits": 462.0,
              "discovery_fidelity": 0.819672131147541,
              "heldout_fidelity": 0.8852459016393442,
              "output_fidelity": 0.8852459016393442,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  1,
                  3
                ],
                "unique_state_signatures": 3
              },
              "sparse_invariant_agreement": 0.9508196721311475,
              "state_count": 3,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 0.7333333333333333,
                  "state": 0,
                  "support": 15
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 0.8333333333333334,
                  "state": 0,
                  "support": 6
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 0.5,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.6666666666666666,
                  "state": 1,
                  "support": 6
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 9
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 17
                }
              ]
            },
            {
              "description_length_bits": 624.0,
              "discovery_fidelity": 0.8852459016393442,
              "heldout_fidelity": 0.9180327868852459,
              "output_fidelity": 0.9180327868852459,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  1,
                  4,
                  3
                ],
                "unique_state_signatures": 4
              },
              "sparse_invariant_agreement": 0.9836065573770492,
              "state_count": 4,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 0.7333333333333333,
                  "state": 0,
                  "support": 15
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 0.8333333333333334,
                  "state": 0,
                  "support": 6
                },
                {
                  "input_symbol": "I0",
                  "next_state": 3,
                  "output_symbol": "O1",
                  "purity": 0.6666666666666666,
                  "state": 1,
                  "support": 6
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 4
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 9
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 17
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                }
              ]
            },
            {
              "description_length_bits": 800.0,
              "discovery_fidelity": 0.9672131147540983,
              "heldout_fidelity": 0.9836065573770492,
              "output_fidelity": 0.9836065573770492,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  1,
                  2
                ],
                "unique_state_signatures": 4
              },
              "sparse_invariant_agreement": 0.9672131147540983,
              "state_count": 5,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 11
                },
                {
                  "input_symbol": "I1",
                  "next_state": 4,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 1
                },
                {
                  "input_symbol": "I0",
                  "next_state": 3,
                  "output_symbol": "O1",
                  "purity": 0.6666666666666666,
                  "state": 1,
                  "support": 6
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 4
                },
                {
                  "input_symbol": "I0",
                  "next_state": 4,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 9
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 17
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 4,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 4,
                  "support": 5
                }
              ]
            },
            {
              "description_length_bits": 944.0,
              "discovery_fidelity": 1.0,
              "heldout_fidelity": 0.9836065573770492,
              "output_fidelity": 0.9836065573770492,
              "qualified": true,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  1,
                  3
                ],
                "unique_state_signatures": 4
              },
              "sparse_invariant_agreement": 0.819672131147541,
              "state_count": 6,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 11
                },
                {
                  "input_symbol": "I1",
                  "next_state": 4,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 1
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 2
                },
                {
                  "input_symbol": "I0",
                  "next_state": 4,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 9
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 17
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                },
                {
                  "input_symbol": "I0",
                  "next_state": 5,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 4,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 5,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 4,
                  "support": 5
                },
                {
                  "input_symbol": "I0",
                  "next_state": 3,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 5,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 5,
                  "support": 4
                }
              ]
            }
          ],
          "program_sha256": "b9ca4a2376c1f277cb593e0ecb0b5b3b2a9d826b2f628cd3a9279676d6628754",
          "selected_state_count": 6,
          "sparse_invariant": {
            "maximum_dimensions": 3,
            "method": "sparse_centroid_signature_v1",
            "minimum_squared_state_separation": 0.25,
            "selected_dimensions": [
              0,
              1,
              3
            ],
            "unique_state_signatures": 4
          },
          "transition_table": [
            {
              "input_symbol": "I0",
              "next_state": 2,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 0,
              "support": 11
            },
            {
              "input_symbol": "I1",
              "next_state": 4,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 0,
              "support": 1
            },
            {
              "input_symbol": "I0",
              "next_state": 0,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 1,
              "support": 2
            },
            {
              "input_symbol": "I0",
              "next_state": 4,
              "output_symbol": "O2",
              "purity": 1.0,
              "state": 2,
              "support": 9
            },
            {
              "input_symbol": "I1",
              "next_state": 2,
              "output_symbol": "O2",
              "purity": 1.0,
              "state": 2,
              "support": 17
            },
            {
              "input_symbol": "I0",
              "next_state": 1,
              "output_symbol": "O2",
              "purity": 1.0,
              "state": 3,
              "support": 2
            },
            {
              "input_symbol": "I1",
              "next_state": 1,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 3,
              "support": 2
            },
            {
              "input_symbol": "I0",
              "next_state": 5,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 4,
              "support": 4
            },
            {
              "input_symbol": "I1",
              "next_state": 5,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 4,
              "support": 5
            },
            {
              "input_symbol": "I0",
              "next_state": 3,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 5,
              "support": 4
            },
            {
              "input_symbol": "I1",
              "next_state": 0,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 5,
              "support": 4
            }
          ]
        },
        "pixie_rank8": {
          "candidate": "pixie_rank8",
          "causal": {
            "causal_prediction_accuracy": 1,
            "matched_control_margin": 1,
            "matched_random_change_rate": 0,
            "mean_absolute_guardrail_delta": 0.0,
            "observation_count": 8,
            "status": "COMPLETE",
            "target_change_rate": 1
          },
          "description_length_bits": 944.0,
          "gates": {
            "causal_prediction": true,
            "guardrail": true,
            "matched_control": true,
            "program_fidelity": true,
            "sparse_invariant": false,
            "task_accuracy": true
          },
          "heldout_evaluation": {
            "candidate": "pixie_rank8",
            "case_count": 8,
            "heldout_program_fidelity": 0.9836065573770492,
            "missing_transition_rate": 0.01639344262295082,
            "output_fidelity": 0.9836065573770492,
            "schema": "pixieology_mechanism_program_evaluation_v1",
            "sparse_invariant_agreement": 0.7049180327868853,
            "split": "held_out",
            "step_count": 61,
            "task_accuracy": 0.875,
            "task_family_id": "fsm-03"
          },
          "interventions": [
            {
              "baseline_output_symbol": "O0",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O0",
              "observation_id": "pixie_rank8-fsm-03-0",
              "observed_output_symbol": "O1",
              "predicted_output_symbol": "O1",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-03-1",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-03-2",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-03-3",
              "observed_output_symbol": "O2",
              "predicted_output_symbol": "O2",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-03-4",
              "observed_output_symbol": "O2",
              "predicted_output_symbol": "O2",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-03-5",
              "observed_output_symbol": "O2",
              "predicted_output_symbol": "O2",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-03-6",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            },
            {
              "baseline_output_symbol": "O1",
              "candidate": "pixie_rank8",
              "evidence_class": "synthetic_implementation_fixture",
              "guardrail_delta": 0.0,
              "matched_random_output_symbol": "O1",
              "observation_id": "pixie_rank8-fsm-03-7",
              "observed_output_symbol": "O0",
              "predicted_output_symbol": "O0",
              "schema": "pixieology_mechanism_intervention_observation_v1",
              "task_family_id": "fsm-03"
            }
          ],
          "phase_scan": [
            {
              "description_length_bits": 150.0,
              "discovery_fidelity": 0.5245901639344263,
              "heldout_fidelity": 0.5245901639344263,
              "output_fidelity": 0.5245901639344263,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0
                ],
                "unique_state_signatures": 1
              },
              "sparse_invariant_agreement": 1.0,
              "state_count": 1,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.46875,
                  "state": 0,
                  "support": 32
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O2",
                  "purity": 0.5862068965517241,
                  "state": 0,
                  "support": 29
                }
              ]
            },
            {
              "description_length_bits": 300.0,
              "discovery_fidelity": 0.5901639344262295,
              "heldout_fidelity": 0.639344262295082,
              "output_fidelity": 0.639344262295082,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  2
                ],
                "unique_state_signatures": 2
              },
              "sparse_invariant_agreement": 0.639344262295082,
              "state_count": 2,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.4583333333333333,
                  "state": 0,
                  "support": 24
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O2",
                  "purity": 0.7391304347826086,
                  "state": 0,
                  "support": 23
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 0.5,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.6666666666666666,
                  "state": 1,
                  "support": 6
                }
              ]
            },
            {
              "description_length_bits": 462.0,
              "discovery_fidelity": 0.819672131147541,
              "heldout_fidelity": 0.8852459016393442,
              "output_fidelity": 0.8852459016393442,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  2,
                  4
                ],
                "unique_state_signatures": 3
              },
              "sparse_invariant_agreement": 0.9508196721311475,
              "state_count": 3,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 0.7333333333333333,
                  "state": 0,
                  "support": 15
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 0.8333333333333334,
                  "state": 0,
                  "support": 6
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 0.5,
                  "state": 1,
                  "support": 8
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 0.6666666666666666,
                  "state": 1,
                  "support": 6
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 9
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 17
                }
              ]
            },
            {
              "description_length_bits": 624.0,
              "discovery_fidelity": 0.8852459016393442,
              "heldout_fidelity": 0.9180327868852459,
              "output_fidelity": 0.9180327868852459,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  2,
                  5,
                  4
                ],
                "unique_state_signatures": 4
              },
              "sparse_invariant_agreement": 0.9836065573770492,
              "state_count": 4,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 0.7333333333333333,
                  "state": 0,
                  "support": 15
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 0.8333333333333334,
                  "state": 0,
                  "support": 6
                },
                {
                  "input_symbol": "I0",
                  "next_state": 3,
                  "output_symbol": "O1",
                  "purity": 0.6666666666666666,
                  "state": 1,
                  "support": 6
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 4
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 9
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 17
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                }
              ]
            },
            {
              "description_length_bits": 800.0,
              "discovery_fidelity": 0.9672131147540983,
              "heldout_fidelity": 0.9836065573770492,
              "output_fidelity": 0.9836065573770492,
              "qualified": false,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  1,
                  2,
                  3
                ],
                "unique_state_signatures": 4
              },
              "sparse_invariant_agreement": 0.9672131147540983,
              "state_count": 5,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 11
                },
                {
                  "input_symbol": "I1",
                  "next_state": 4,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 1
                },
                {
                  "input_symbol": "I0",
                  "next_state": 3,
                  "output_symbol": "O1",
                  "purity": 0.6666666666666666,
                  "state": 1,
                  "support": 6
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 1,
                  "support": 4
                },
                {
                  "input_symbol": "I0",
                  "next_state": 4,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 9
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 17
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 4,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 4,
                  "support": 5
                }
              ]
            },
            {
              "description_length_bits": 944.0,
              "discovery_fidelity": 1.0,
              "heldout_fidelity": 0.9836065573770492,
              "output_fidelity": 0.9836065573770492,
              "qualified": true,
              "sparse_invariant": {
                "maximum_dimensions": 3,
                "method": "sparse_centroid_signature_v1",
                "minimum_squared_state_separation": 0.25,
                "selected_dimensions": [
                  0,
                  1,
                  2
                ],
                "unique_state_signatures": 4
              },
              "sparse_invariant_agreement": 0.7049180327868853,
              "state_count": 6,
              "transition_table": [
                {
                  "input_symbol": "I0",
                  "next_state": 2,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 0,
                  "support": 11
                },
                {
                  "input_symbol": "I1",
                  "next_state": 4,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 0,
                  "support": 1
                },
                {
                  "input_symbol": "I0",
                  "next_state": 0,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 1,
                  "support": 2
                },
                {
                  "input_symbol": "I0",
                  "next_state": 4,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 9
                },
                {
                  "input_symbol": "I1",
                  "next_state": 2,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 2,
                  "support": 17
                },
                {
                  "input_symbol": "I0",
                  "next_state": 1,
                  "output_symbol": "O2",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                },
                {
                  "input_symbol": "I1",
                  "next_state": 1,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 3,
                  "support": 2
                },
                {
                  "input_symbol": "I0",
                  "next_state": 5,
                  "output_symbol": "O0",
                  "purity": 1.0,
                  "state": 4,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 5,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 4,
                  "support": 5
                },
                {
                  "input_symbol": "I0",
                  "next_state": 3,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 5,
                  "support": 4
                },
                {
                  "input_symbol": "I1",
                  "next_state": 0,
                  "output_symbol": "O1",
                  "purity": 1.0,
                  "state": 5,
                  "support": 4
                }
              ]
            }
          ],
          "program_sha256": "433ae5476c647b9b937f01df6f4f4b037f771320e1f40c87a1730b6e2963c685",
          "selected_state_count": 6,
          "sparse_invariant": {
            "maximum_dimensions": 3,
            "method": "sparse_centroid_signature_v1",
            "minimum_squared_state_separation": 0.25,
            "selected_dimensions": [
              0,
              1,
              2
            ],
            "unique_state_signatures": 4
          },
          "transition_table": [
            {
              "input_symbol": "I0",
              "next_state": 2,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 0,
              "support": 11
            },
            {
              "input_symbol": "I1",
              "next_state": 4,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 0,
              "support": 1
            },
            {
              "input_symbol": "I0",
              "next_state": 0,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 1,
              "support": 2
            },
            {
              "input_symbol": "I0",
              "next_state": 4,
              "output_symbol": "O2",
              "purity": 1.0,
              "state": 2,
              "support": 9
            },
            {
              "input_symbol": "I1",
              "next_state": 2,
              "output_symbol": "O2",
              "purity": 1.0,
              "state": 2,
              "support": 17
            },
            {
              "input_symbol": "I0",
              "next_state": 1,
              "output_symbol": "O2",
              "purity": 1.0,
              "state": 3,
              "support": 2
            },
            {
              "input_symbol": "I1",
              "next_state": 1,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 3,
              "support": 2
            },
            {
              "input_symbol": "I0",
              "next_state": 5,
              "output_symbol": "O0",
              "purity": 1.0,
              "state": 4,
              "support": 4
            },
            {
              "input_symbol": "I1",
              "next_state": 5,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 4,
              "support": 5
            },
            {
              "input_symbol": "I0",
              "next_state": 3,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 5,
              "support": 4
            },
            {
              "input_symbol": "I1",
              "next_state": 0,
              "output_symbol": "O1",
              "purity": 1.0,
              "state": 5,
              "support": 4
            }
          ]
        }
      },
      "comparison": {
        "description_length_reduction": 0.0,
        "evidence_class": "synthetic_or_incomplete",
        "isomorphism_verdict": "USABLE_ISOMORPHISM",
        "winner": "UNDETERMINED"
      },
      "complexity_values": [
        1,
        2,
        3,
        4,
        5,
        6
      ],
      "default_complexity": 6,
      "oracle_shape": {
        "input_symbols": [
          "I0",
          "I1"
        ],
        "output_symbols": [
          "O0",
          "O1",
          "O2"
        ],
        "state_count": 6
      },
      "task_family_id": "fsm-03"
    }
  ],
  "generator": "sealed_synthetic_mechanism_fixture_v1",
  "human_or_model_evidence": false,
  "schema": "pixieology_mechanism_law_lab_dataset_v1",
  "seed": 2026080604,
  "thresholds": {
    "discovery_fidelity_floor": 0.98,
    "minimum_heldout_program_fidelity": 0.9,
    "minimum_isomorphism_fidelity": 0.9
  }
};
});
