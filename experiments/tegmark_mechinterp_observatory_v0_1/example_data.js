window.TEGMARK_OBSERVATORY_DATA = {
  "schema_version": "tegmark_mechinterp_observatory.v1",
  "evidence_class": "method_faithful_synthetic_fixture",
  "human_or_model_evidence": false,
  "claim_boundary": "Interaction and data-contract demonstration only; not a paper reproduction and not evidence about Pixie or Qwen.",
  "sources": {
    "bimt": "https://arxiv.org/abs/2305.08746",
    "clock_pizza": "https://arxiv.org/abs/2306.17844",
    "hypernetwork": "https://arxiv.org/abs/2312.03051",
    "mips": "https://arxiv.org/abs/2402.05110",
    "sid": "https://arxiv.org/abs/2305.19525",
    "open_problems": "https://arxiv.org/abs/2501.16496"
  },
  "lenses": {
    "bimt": {
      "methods": [
        {
          "id": "vanilla",
          "label": "Vanilla",
          "task_loss": 0.0018,
          "connection_cost": 10.9,
          "active_edges": 18,
          "nodes": [
            {
              "id": "x0",
              "label": "x₀",
              "layer": 0,
              "x": 0.08,
              "y": 0.25
            },
            {
              "id": "x1",
              "label": "x₁",
              "layer": 0,
              "x": 0.08,
              "y": 0.75
            },
            {
              "id": "h0",
              "label": "h₀",
              "layer": 1,
              "x": 0.38,
              "y": 0.16
            },
            {
              "id": "h1",
              "label": "h₁",
              "layer": 1,
              "x": 0.38,
              "y": 0.42
            },
            {
              "id": "h2",
              "label": "h₂",
              "layer": 1,
              "x": 0.38,
              "y": 0.68
            },
            {
              "id": "h3",
              "label": "h₃",
              "layer": 1,
              "x": 0.38,
              "y": 0.9
            },
            {
              "id": "g0",
              "label": "g₀",
              "layer": 2,
              "x": 0.68,
              "y": 0.28
            },
            {
              "id": "g1",
              "label": "g₁",
              "layer": 2,
              "x": 0.68,
              "y": 0.72
            },
            {
              "id": "y",
              "label": "ŷ",
              "layer": 3,
              "x": 0.93,
              "y": 0.5
            }
          ],
          "edges": [
            {
              "source": "x0",
              "target": "h0",
              "weight": 0.92,
              "ablation_delta": 0.16
            },
            {
              "source": "x0",
              "target": "h1",
              "weight": 0.71,
              "ablation_delta": 0.08
            },
            {
              "source": "x1",
              "target": "h2",
              "weight": -0.88,
              "ablation_delta": 0.14
            },
            {
              "source": "x1",
              "target": "h3",
              "weight": 0.68,
              "ablation_delta": 0.07
            },
            {
              "source": "h0",
              "target": "g0",
              "weight": 0.83,
              "ablation_delta": 0.22
            },
            {
              "source": "h1",
              "target": "g0",
              "weight": -0.62,
              "ablation_delta": 0.11
            },
            {
              "source": "h2",
              "target": "g1",
              "weight": 0.79,
              "ablation_delta": 0.19
            },
            {
              "source": "h3",
              "target": "g1",
              "weight": 0.58,
              "ablation_delta": 0.09
            },
            {
              "source": "g0",
              "target": "y",
              "weight": 0.91,
              "ablation_delta": 0.31
            },
            {
              "source": "g1",
              "target": "y",
              "weight": -0.86,
              "ablation_delta": 0.27
            },
            {
              "source": "x0",
              "target": "h3",
              "weight": 0.19,
              "ablation_delta": 0.01
            },
            {
              "source": "x1",
              "target": "h0",
              "weight": -0.23,
              "ablation_delta": 0.02
            },
            {
              "source": "h0",
              "target": "g1",
              "weight": 0.17,
              "ablation_delta": 0.01
            },
            {
              "source": "h2",
              "target": "g0",
              "weight": -0.21,
              "ablation_delta": 0.02
            },
            {
              "source": "h1",
              "target": "g1",
              "weight": 0.13,
              "ablation_delta": 0.01
            },
            {
              "source": "h3",
              "target": "g0",
              "weight": 0.12,
              "ablation_delta": 0.01
            },
            {
              "source": "x0",
              "target": "h2",
              "weight": -0.15,
              "ablation_delta": 0.01
            },
            {
              "source": "x1",
              "target": "h1",
              "weight": 0.16,
              "ablation_delta": 0.01
            }
          ]
        },
        {
          "id": "l1",
          "label": "L1",
          "task_loss": 0.0024,
          "connection_cost": 7.2,
          "active_edges": 15,
          "nodes": [
            {
              "id": "x0",
              "label": "x₀",
              "layer": 0,
              "x": 0.08,
              "y": 0.25
            },
            {
              "id": "x1",
              "label": "x₁",
              "layer": 0,
              "x": 0.08,
              "y": 0.75
            },
            {
              "id": "h0",
              "label": "h₀",
              "layer": 1,
              "x": 0.38,
              "y": 0.16
            },
            {
              "id": "h1",
              "label": "h₁",
              "layer": 1,
              "x": 0.38,
              "y": 0.42
            },
            {
              "id": "h2",
              "label": "h₂",
              "layer": 1,
              "x": 0.38,
              "y": 0.68
            },
            {
              "id": "h3",
              "label": "h₃",
              "layer": 1,
              "x": 0.38,
              "y": 0.9
            },
            {
              "id": "g0",
              "label": "g₀",
              "layer": 2,
              "x": 0.68,
              "y": 0.28
            },
            {
              "id": "g1",
              "label": "g₁",
              "layer": 2,
              "x": 0.68,
              "y": 0.72
            },
            {
              "id": "y",
              "label": "ŷ",
              "layer": 3,
              "x": 0.93,
              "y": 0.5
            }
          ],
          "edges": [
            {
              "source": "x0",
              "target": "h0",
              "weight": 0.92,
              "ablation_delta": 0.16
            },
            {
              "source": "x0",
              "target": "h1",
              "weight": 0.71,
              "ablation_delta": 0.08
            },
            {
              "source": "x1",
              "target": "h2",
              "weight": -0.88,
              "ablation_delta": 0.14
            },
            {
              "source": "x1",
              "target": "h3",
              "weight": 0.68,
              "ablation_delta": 0.07
            },
            {
              "source": "h0",
              "target": "g0",
              "weight": 0.83,
              "ablation_delta": 0.22
            },
            {
              "source": "h1",
              "target": "g0",
              "weight": -0.62,
              "ablation_delta": 0.11
            },
            {
              "source": "h2",
              "target": "g1",
              "weight": 0.79,
              "ablation_delta": 0.19
            },
            {
              "source": "h3",
              "target": "g1",
              "weight": 0.58,
              "ablation_delta": 0.09
            },
            {
              "source": "g0",
              "target": "y",
              "weight": 0.91,
              "ablation_delta": 0.31
            },
            {
              "source": "g1",
              "target": "y",
              "weight": -0.86,
              "ablation_delta": 0.27
            },
            {
              "source": "x0",
              "target": "h3",
              "weight": 0.19,
              "ablation_delta": 0.01
            },
            {
              "source": "x1",
              "target": "h0",
              "weight": -0.23,
              "ablation_delta": 0.02
            },
            {
              "source": "h0",
              "target": "g1",
              "weight": 0.17,
              "ablation_delta": 0.01
            },
            {
              "source": "h2",
              "target": "g0",
              "weight": -0.21,
              "ablation_delta": 0.02
            },
            {
              "source": "h1",
              "target": "g1",
              "weight": 0.13,
              "ablation_delta": 0.01
            }
          ]
        },
        {
          "id": "l1_local",
          "label": "L1 + local",
          "task_loss": 0.0027,
          "connection_cost": 5.1,
          "active_edges": 13,
          "nodes": [
            {
              "id": "x0",
              "label": "x₀",
              "layer": 0,
              "x": 0.08,
              "y": 0.25
            },
            {
              "id": "x1",
              "label": "x₁",
              "layer": 0,
              "x": 0.08,
              "y": 0.75
            },
            {
              "id": "h0",
              "label": "h₀",
              "layer": 1,
              "x": 0.38,
              "y": 0.16
            },
            {
              "id": "h1",
              "label": "h₁",
              "layer": 1,
              "x": 0.38,
              "y": 0.42
            },
            {
              "id": "h2",
              "label": "h₂",
              "layer": 1,
              "x": 0.38,
              "y": 0.68
            },
            {
              "id": "h3",
              "label": "h₃",
              "layer": 1,
              "x": 0.38,
              "y": 0.9
            },
            {
              "id": "g0",
              "label": "g₀",
              "layer": 2,
              "x": 0.68,
              "y": 0.28
            },
            {
              "id": "g1",
              "label": "g₁",
              "layer": 2,
              "x": 0.68,
              "y": 0.72
            },
            {
              "id": "y",
              "label": "ŷ",
              "layer": 3,
              "x": 0.93,
              "y": 0.5
            }
          ],
          "edges": [
            {
              "source": "x0",
              "target": "h0",
              "weight": 0.92,
              "ablation_delta": 0.16
            },
            {
              "source": "x0",
              "target": "h1",
              "weight": 0.71,
              "ablation_delta": 0.08
            },
            {
              "source": "x1",
              "target": "h2",
              "weight": -0.88,
              "ablation_delta": 0.14
            },
            {
              "source": "x1",
              "target": "h3",
              "weight": 0.68,
              "ablation_delta": 0.07
            },
            {
              "source": "h0",
              "target": "g0",
              "weight": 0.83,
              "ablation_delta": 0.22
            },
            {
              "source": "h1",
              "target": "g0",
              "weight": -0.62,
              "ablation_delta": 0.11
            },
            {
              "source": "h2",
              "target": "g1",
              "weight": 0.79,
              "ablation_delta": 0.19
            },
            {
              "source": "h3",
              "target": "g1",
              "weight": 0.58,
              "ablation_delta": 0.09
            },
            {
              "source": "g0",
              "target": "y",
              "weight": 0.91,
              "ablation_delta": 0.31
            },
            {
              "source": "g1",
              "target": "y",
              "weight": -0.86,
              "ablation_delta": 0.27
            },
            {
              "source": "x0",
              "target": "h3",
              "weight": 0.19,
              "ablation_delta": 0.01
            },
            {
              "source": "x1",
              "target": "h0",
              "weight": -0.23,
              "ablation_delta": 0.02
            },
            {
              "source": "h0",
              "target": "g1",
              "weight": 0.17,
              "ablation_delta": 0.01
            }
          ]
        },
        {
          "id": "l1_swap",
          "label": "L1 + swap",
          "task_loss": 0.0025,
          "connection_cost": 4.7,
          "active_edges": 12,
          "nodes": [
            {
              "id": "x0",
              "label": "x₀",
              "layer": 0,
              "x": 0.08,
              "y": 0.25
            },
            {
              "id": "x1",
              "label": "x₁",
              "layer": 0,
              "x": 0.08,
              "y": 0.75
            },
            {
              "id": "h0",
              "label": "h₀",
              "layer": 1,
              "x": 0.38,
              "y": 0.16
            },
            {
              "id": "h1",
              "label": "h₁",
              "layer": 1,
              "x": 0.38,
              "y": 0.42
            },
            {
              "id": "h2",
              "label": "h₂",
              "layer": 1,
              "x": 0.38,
              "y": 0.68
            },
            {
              "id": "h3",
              "label": "h₃",
              "layer": 1,
              "x": 0.38,
              "y": 0.9
            },
            {
              "id": "g0",
              "label": "g₀",
              "layer": 2,
              "x": 0.68,
              "y": 0.28
            },
            {
              "id": "g1",
              "label": "g₁",
              "layer": 2,
              "x": 0.68,
              "y": 0.72
            },
            {
              "id": "y",
              "label": "ŷ",
              "layer": 3,
              "x": 0.93,
              "y": 0.5
            }
          ],
          "edges": [
            {
              "source": "x0",
              "target": "h0",
              "weight": 0.92,
              "ablation_delta": 0.16
            },
            {
              "source": "x0",
              "target": "h1",
              "weight": 0.71,
              "ablation_delta": 0.08
            },
            {
              "source": "x1",
              "target": "h2",
              "weight": -0.88,
              "ablation_delta": 0.14
            },
            {
              "source": "x1",
              "target": "h3",
              "weight": 0.68,
              "ablation_delta": 0.07
            },
            {
              "source": "h0",
              "target": "g0",
              "weight": 0.83,
              "ablation_delta": 0.22
            },
            {
              "source": "h1",
              "target": "g0",
              "weight": -0.62,
              "ablation_delta": 0.11
            },
            {
              "source": "h2",
              "target": "g1",
              "weight": 0.79,
              "ablation_delta": 0.19
            },
            {
              "source": "h3",
              "target": "g1",
              "weight": 0.58,
              "ablation_delta": 0.09
            },
            {
              "source": "g0",
              "target": "y",
              "weight": 0.91,
              "ablation_delta": 0.31
            },
            {
              "source": "g1",
              "target": "y",
              "weight": -0.86,
              "ablation_delta": 0.27
            },
            {
              "source": "x0",
              "target": "h3",
              "weight": 0.19,
              "ablation_delta": 0.01
            },
            {
              "source": "x1",
              "target": "h0",
              "weight": -0.23,
              "ablation_delta": 0.02
            }
          ]
        },
        {
          "id": "bimt",
          "label": "BIMT",
          "task_loss": 0.0031,
          "connection_cost": 3.4,
          "active_edges": 10,
          "nodes": [
            {
              "id": "x0",
              "label": "x₀",
              "layer": 0,
              "x": 0.08,
              "y": 0.25
            },
            {
              "id": "x1",
              "label": "x₁",
              "layer": 0,
              "x": 0.08,
              "y": 0.75
            },
            {
              "id": "h0",
              "label": "h₀",
              "layer": 1,
              "x": 0.38,
              "y": 0.16
            },
            {
              "id": "h1",
              "label": "h₁",
              "layer": 1,
              "x": 0.38,
              "y": 0.42
            },
            {
              "id": "h2",
              "label": "h₂",
              "layer": 1,
              "x": 0.38,
              "y": 0.68
            },
            {
              "id": "h3",
              "label": "h₃",
              "layer": 1,
              "x": 0.38,
              "y": 0.9
            },
            {
              "id": "g0",
              "label": "g₀",
              "layer": 2,
              "x": 0.68,
              "y": 0.28
            },
            {
              "id": "g1",
              "label": "g₁",
              "layer": 2,
              "x": 0.68,
              "y": 0.72
            },
            {
              "id": "y",
              "label": "ŷ",
              "layer": 3,
              "x": 0.93,
              "y": 0.5
            }
          ],
          "edges": [
            {
              "source": "x0",
              "target": "h0",
              "weight": 0.92,
              "ablation_delta": 0.16
            },
            {
              "source": "x0",
              "target": "h1",
              "weight": 0.71,
              "ablation_delta": 0.08
            },
            {
              "source": "x1",
              "target": "h2",
              "weight": -0.88,
              "ablation_delta": 0.14
            },
            {
              "source": "x1",
              "target": "h3",
              "weight": 0.68,
              "ablation_delta": 0.07
            },
            {
              "source": "h0",
              "target": "g0",
              "weight": 0.83,
              "ablation_delta": 0.22
            },
            {
              "source": "h1",
              "target": "g0",
              "weight": -0.62,
              "ablation_delta": 0.11
            },
            {
              "source": "h2",
              "target": "g1",
              "weight": 0.79,
              "ablation_delta": 0.19
            },
            {
              "source": "h3",
              "target": "g1",
              "weight": 0.58,
              "ablation_delta": 0.09
            },
            {
              "source": "g0",
              "target": "y",
              "weight": 0.91,
              "ablation_delta": 0.31
            },
            {
              "source": "g1",
              "target": "y",
              "weight": -0.86,
              "ablation_delta": 0.27
            }
          ]
        }
      ],
      "note": "Synthetic ablation fixture: BIMT combines L1, geometry-weighted locality, and neuron swapping."
    },
    "clock_pizza": {
      "widths": [
        32,
        64,
        128,
        256
      ],
      "attention_rates": [
        0.0,
        0.25,
        0.5,
        0.75,
        1.0
      ],
      "cells": [
        {
          "width": 32,
          "attention_rate": 0.0,
          "algorithm": "pizza",
          "gradient_symmetricity": 0.9,
          "distance_irrelevance_q": 0.13,
          "circularity": 0.932,
          "validation_accuracy": 0.999
        },
        {
          "width": 32,
          "attention_rate": 0.25,
          "algorithm": "pizza",
          "gradient_symmetricity": 0.9,
          "distance_irrelevance_q": 0.13,
          "circularity": 0.94,
          "validation_accuracy": 0.999
        },
        {
          "width": 32,
          "attention_rate": 0.5,
          "algorithm": "hybrid",
          "gradient_symmetricity": 0.496,
          "distance_irrelevance_q": 0.495,
          "circularity": 0.945,
          "validation_accuracy": 0.999
        },
        {
          "width": 32,
          "attention_rate": 0.75,
          "algorithm": "clock",
          "gradient_symmetricity": 0.18,
          "distance_irrelevance_q": 0.78,
          "circularity": 0.949,
          "validation_accuracy": 0.999
        },
        {
          "width": 32,
          "attention_rate": 1.0,
          "algorithm": "clock",
          "gradient_symmetricity": 0.18,
          "distance_irrelevance_q": 0.78,
          "circularity": 0.95,
          "validation_accuracy": 0.999
        },
        {
          "width": 64,
          "attention_rate": 0.0,
          "algorithm": "pizza",
          "gradient_symmetricity": 0.9,
          "distance_irrelevance_q": 0.13,
          "circularity": 0.947,
          "validation_accuracy": 0.997
        },
        {
          "width": 64,
          "attention_rate": 0.25,
          "algorithm": "pizza",
          "gradient_symmetricity": 0.9,
          "distance_irrelevance_q": 0.13,
          "circularity": 0.95,
          "validation_accuracy": 0.997
        },
        {
          "width": 64,
          "attention_rate": 0.5,
          "algorithm": "hybrid",
          "gradient_symmetricity": 0.592,
          "distance_irrelevance_q": 0.408,
          "circularity": 0.95,
          "validation_accuracy": 0.997
        },
        {
          "width": 64,
          "attention_rate": 0.75,
          "algorithm": "clock",
          "gradient_symmetricity": 0.18,
          "distance_irrelevance_q": 0.78,
          "circularity": 0.948,
          "validation_accuracy": 0.997
        },
        {
          "width": 64,
          "attention_rate": 1.0,
          "algorithm": "clock",
          "gradient_symmetricity": 0.18,
          "distance_irrelevance_q": 0.78,
          "circularity": 0.943,
          "validation_accuracy": 0.997
        },
        {
          "width": 128,
          "attention_rate": 0.0,
          "algorithm": "pizza",
          "gradient_symmetricity": 0.9,
          "distance_irrelevance_q": 0.13,
          "circularity": 0.939,
          "validation_accuracy": 0.997
        },
        {
          "width": 128,
          "attention_rate": 0.25,
          "algorithm": "pizza",
          "gradient_symmetricity": 0.9,
          "distance_irrelevance_q": 0.13,
          "circularity": 0.931,
          "validation_accuracy": 0.997
        },
        {
          "width": 128,
          "attention_rate": 0.5,
          "algorithm": "pizza",
          "gradient_symmetricity": 0.784,
          "distance_irrelevance_q": 0.235,
          "circularity": 0.922,
          "validation_accuracy": 0.997
        },
        {
          "width": 128,
          "attention_rate": 0.75,
          "algorithm": "clock",
          "gradient_symmetricity": 0.284,
          "distance_irrelevance_q": 0.686,
          "circularity": 0.912,
          "validation_accuracy": 0.997
        },
        {
          "width": 128,
          "attention_rate": 1.0,
          "algorithm": "clock",
          "gradient_symmetricity": 0.18,
          "distance_irrelevance_q": 0.78,
          "circularity": 0.902,
          "validation_accuracy": 0.997
        },
        {
          "width": 256,
          "attention_rate": 0.0,
          "algorithm": "pizza",
          "gradient_symmetricity": 0.9,
          "distance_irrelevance_q": 0.13,
          "circularity": 0.87,
          "validation_accuracy": 0.997
        },
        {
          "width": 256,
          "attention_rate": 0.25,
          "algorithm": "pizza",
          "gradient_symmetricity": 0.9,
          "distance_irrelevance_q": 0.13,
          "circularity": 0.871,
          "validation_accuracy": 0.997
        },
        {
          "width": 256,
          "attention_rate": 0.5,
          "algorithm": "pizza",
          "gradient_symmetricity": 0.9,
          "distance_irrelevance_q": 0.13,
          "circularity": 0.874,
          "validation_accuracy": 0.997
        },
        {
          "width": 256,
          "attention_rate": 0.75,
          "algorithm": "hybrid",
          "gradient_symmetricity": 0.668,
          "distance_irrelevance_q": 0.339,
          "circularity": 0.88,
          "validation_accuracy": 0.997
        },
        {
          "width": 256,
          "attention_rate": 1.0,
          "algorithm": "clock",
          "gradient_symmetricity": 0.18,
          "distance_irrelevance_q": 0.78,
          "circularity": 0.887,
          "validation_accuracy": 0.997
        }
      ],
      "threshold_note": "Synthetic classifier: high gradient symmetricity and low q indicate Pizza; high q indicates Clock."
    },
    "hypernetwork": {
      "betas": [
        0.0001,
        0.001,
        0.01,
        0.1
      ],
      "steps": [
        200,
        800,
        1600,
        3200
      ],
      "cells": [
        {
          "beta": 0.0001,
          "step": 200,
          "algorithm": "convexity",
          "double_sidedness": 0.438,
          "strongest_connection": 0.575,
          "seed_dependence": 0.667
        },
        {
          "beta": 0.0001,
          "step": 800,
          "algorithm": "double-sided",
          "double_sidedness": 0.814,
          "strongest_connection": 0.665,
          "seed_dependence": 0.601
        },
        {
          "beta": 0.0001,
          "step": 1600,
          "algorithm": "double-sided",
          "double_sidedness": 1.0,
          "strongest_connection": 0.711,
          "seed_dependence": 0.568
        },
        {
          "beta": 0.0001,
          "step": 3200,
          "algorithm": "double-sided",
          "double_sidedness": 1.0,
          "strongest_connection": 0.756,
          "seed_dependence": 0.534
        },
        {
          "beta": 0.001,
          "step": 200,
          "algorithm": "convexity",
          "double_sidedness": 0.0,
          "strongest_connection": 0.505,
          "seed_dependence": 0.647
        },
        {
          "beta": 0.001,
          "step": 800,
          "algorithm": "pudding",
          "double_sidedness": 0.189,
          "strongest_connection": 0.595,
          "seed_dependence": 0.581
        },
        {
          "beta": 0.001,
          "step": 1600,
          "algorithm": "pudding",
          "double_sidedness": 0.378,
          "strongest_connection": 0.641,
          "seed_dependence": 0.548
        },
        {
          "beta": 0.001,
          "step": 3200,
          "algorithm": "pudding",
          "double_sidedness": 0.566,
          "strongest_connection": 0.686,
          "seed_dependence": 0.514
        },
        {
          "beta": 0.01,
          "step": 200,
          "algorithm": "convexity",
          "double_sidedness": 0.0,
          "strongest_connection": 0.435,
          "seed_dependence": 0.627
        },
        {
          "beta": 0.01,
          "step": 800,
          "algorithm": "pudding",
          "double_sidedness": 0.0,
          "strongest_connection": 0.525,
          "seed_dependence": 0.561
        },
        {
          "beta": 0.01,
          "step": 1600,
          "algorithm": "pudding",
          "double_sidedness": 0.0,
          "strongest_connection": 0.571,
          "seed_dependence": 0.528
        },
        {
          "beta": 0.01,
          "step": 3200,
          "algorithm": "pudding",
          "double_sidedness": 0.0,
          "strongest_connection": 0.616,
          "seed_dependence": 0.494
        },
        {
          "beta": 0.1,
          "step": 200,
          "algorithm": "convexity",
          "double_sidedness": 0.0,
          "strongest_connection": 0.365,
          "seed_dependence": 0.607
        },
        {
          "beta": 0.1,
          "step": 800,
          "algorithm": "pudding",
          "double_sidedness": 0.0,
          "strongest_connection": 0.455,
          "seed_dependence": 0.541
        },
        {
          "beta": 0.1,
          "step": 1600,
          "algorithm": "pudding",
          "double_sidedness": 0.0,
          "strongest_connection": 0.501,
          "seed_dependence": 0.508
        },
        {
          "beta": 0.1,
          "step": 3200,
          "algorithm": "pudding",
          "double_sidedness": 0.0,
          "strongest_connection": 0.546,
          "seed_dependence": 0.474
        }
      ],
      "generalization": [
        {
          "input_dim": 2,
          "hidden_dim": 2,
          "loss": 0.004
        },
        {
          "input_dim": 2,
          "hidden_dim": 4,
          "loss": 0.013
        },
        {
          "input_dim": 2,
          "hidden_dim": 8,
          "loss": 0.022
        },
        {
          "input_dim": 2,
          "hidden_dim": 16,
          "loss": 0.031
        },
        {
          "input_dim": 4,
          "hidden_dim": 2,
          "loss": 0.031
        },
        {
          "input_dim": 4,
          "hidden_dim": 4,
          "loss": 0.004
        },
        {
          "input_dim": 4,
          "hidden_dim": 8,
          "loss": 0.013
        },
        {
          "input_dim": 4,
          "hidden_dim": 16,
          "loss": 0.022
        },
        {
          "input_dim": 8,
          "hidden_dim": 2,
          "loss": 0.04
        },
        {
          "input_dim": 8,
          "hidden_dim": 4,
          "loss": 0.031
        },
        {
          "input_dim": 8,
          "hidden_dim": 8,
          "loss": 0.004
        },
        {
          "input_dim": 8,
          "hidden_dim": 16,
          "loss": 0.013
        },
        {
          "input_dim": 16,
          "hidden_dim": 2,
          "loss": 0.049
        },
        {
          "input_dim": 16,
          "hidden_dim": 4,
          "loss": 0.04
        },
        {
          "input_dim": 16,
          "hidden_dim": 8,
          "loss": 0.031
        },
        {
          "input_dim": 16,
          "hidden_dim": 16,
          "loss": 0.004
        }
      ]
    },
    "mips": {
      "cases": [
        {
          "id": "binary_addition",
          "label": "Binary addition",
          "status": "compiled",
          "state_points": [
            {
              "x": -0.9,
              "y": -0.3,
              "code": "0"
            },
            {
              "x": -0.75,
              "y": -0.22,
              "code": "0"
            },
            {
              "x": 0.82,
              "y": 0.35,
              "code": "1"
            },
            {
              "x": 0.96,
              "y": 0.27,
              "code": "1"
            }
          ],
          "integer_code": "carry ∈ {0, 1}",
          "transition_rows": [
            {
              "carry": 0,
              "a": 0,
              "b": 0,
              "next": 0,
              "out": 0
            },
            {
              "carry": 0,
              "a": 1,
              "b": 1,
              "next": 1,
              "out": 0
            },
            {
              "carry": 1,
              "a": 0,
              "b": 1,
              "next": 1,
              "out": 0
            },
            {
              "carry": 1,
              "a": 1,
              "b": 1,
              "next": 1,
              "out": 1
            }
          ],
          "symbolic_law": "out = carry ⊕ a ⊕ b; next = (carry + a + b > 1)",
          "python": "out = carry ^ a ^ b\ncarry = int(carry + a + b > 1)",
          "verification": "8 / 8 Boolean transitions",
          "stages": [
            "network",
            "simplify",
            "integer autoencoder",
            "FSM",
            "symbolic regression",
            "verify"
          ]
        },
        {
          "id": "continuous_majority",
          "label": "Running majority",
          "status": "failed: continuous state",
          "state_points": [
            {
              "x": -0.9,
              "y": -0.42,
              "code": "?"
            },
            {
              "x": -0.5,
              "y": -0.2,
              "code": "?"
            },
            {
              "x": 0.0,
              "y": 0.02,
              "code": "?"
            },
            {
              "x": 0.5,
              "y": 0.22,
              "code": "?"
            },
            {
              "x": 0.9,
              "y": 0.45,
              "code": "?"
            }
          ],
          "integer_code": "No stable finite lattice code",
          "transition_rows": [],
          "symbolic_law": "Unavailable",
          "python": "# stopped before code emission",
          "verification": "not run",
          "stages": [
            "network",
            "simplify",
            "integer autoencoder: failed",
            "FSM: unavailable",
            "symbolic regression: unavailable",
            "verify: unavailable"
          ]
        }
      ]
    },
    "sid": {
      "systems": [
        {
          "id": "harmonic_oscillator",
          "label": "Harmonic oscillator",
          "dynamics": "q̇ = p, ṗ = −q",
          "basis": [
            "1",
            "q",
            "p",
            "q²",
            "qp",
            "p²"
          ],
          "singular_values": [
            9.41,
            6.2,
            4.03,
            2.14,
            0.88,
            2e-08
          ],
          "sparse_coefficients": [
            0,
            0,
            0,
            0.5,
            0,
            0.5
          ],
          "law": "H(q,p) = ½q² + ½p²",
          "nullity": 1,
          "independent_rank": 1,
          "max_residual": 2e-08,
          "trajectories": [
            {
              "label": "r=0.7",
              "points": [
                {
                  "t": 0.0,
                  "q": 0.7,
                  "p": -0.0,
                  "H": 0.245
                },
                {
                  "t": 0.524,
                  "q": 0.6062,
                  "p": -0.35,
                  "H": 0.245
                },
                {
                  "t": 1.047,
                  "q": 0.35,
                  "p": -0.6062,
                  "H": 0.245
                },
                {
                  "t": 1.571,
                  "q": 0.0,
                  "p": -0.7,
                  "H": 0.245
                },
                {
                  "t": 2.094,
                  "q": -0.35,
                  "p": -0.6062,
                  "H": 0.245
                },
                {
                  "t": 2.618,
                  "q": -0.6062,
                  "p": -0.35,
                  "H": 0.245
                },
                {
                  "t": 3.142,
                  "q": -0.7,
                  "p": -0.0,
                  "H": 0.245
                },
                {
                  "t": 3.665,
                  "q": -0.6062,
                  "p": 0.35,
                  "H": 0.245
                },
                {
                  "t": 4.189,
                  "q": -0.35,
                  "p": 0.6062,
                  "H": 0.245
                },
                {
                  "t": 4.712,
                  "q": -0.0,
                  "p": 0.7,
                  "H": 0.245
                },
                {
                  "t": 5.236,
                  "q": 0.35,
                  "p": 0.6062,
                  "H": 0.245
                },
                {
                  "t": 5.76,
                  "q": 0.6062,
                  "p": 0.35,
                  "H": 0.245
                },
                {
                  "t": 6.283,
                  "q": 0.7,
                  "p": 0.0,
                  "H": 0.245
                },
                {
                  "t": 6.807,
                  "q": 0.6062,
                  "p": -0.35,
                  "H": 0.245
                },
                {
                  "t": 7.33,
                  "q": 0.35,
                  "p": -0.6062,
                  "H": 0.245
                },
                {
                  "t": 7.854,
                  "q": 0.0,
                  "p": -0.7,
                  "H": 0.245
                },
                {
                  "t": 8.378,
                  "q": -0.35,
                  "p": -0.6062,
                  "H": 0.245
                },
                {
                  "t": 8.901,
                  "q": -0.6062,
                  "p": -0.35,
                  "H": 0.245
                },
                {
                  "t": 9.425,
                  "q": -0.7,
                  "p": -0.0,
                  "H": 0.245
                },
                {
                  "t": 9.948,
                  "q": -0.6062,
                  "p": 0.35,
                  "H": 0.245
                },
                {
                  "t": 10.472,
                  "q": -0.35,
                  "p": 0.6062,
                  "H": 0.245
                },
                {
                  "t": 10.996,
                  "q": -0.0,
                  "p": 0.7,
                  "H": 0.245
                },
                {
                  "t": 11.519,
                  "q": 0.35,
                  "p": 0.6062,
                  "H": 0.245
                },
                {
                  "t": 12.043,
                  "q": 0.6062,
                  "p": 0.35,
                  "H": 0.245
                },
                {
                  "t": 12.566,
                  "q": 0.7,
                  "p": 0.0,
                  "H": 0.245
                }
              ]
            },
            {
              "label": "r=1.0",
              "points": [
                {
                  "t": 0.0,
                  "q": 1.0,
                  "p": -0.0,
                  "H": 0.5
                },
                {
                  "t": 0.524,
                  "q": 0.866,
                  "p": -0.5,
                  "H": 0.5
                },
                {
                  "t": 1.047,
                  "q": 0.5,
                  "p": -0.866,
                  "H": 0.5
                },
                {
                  "t": 1.571,
                  "q": 0.0,
                  "p": -1.0,
                  "H": 0.5
                },
                {
                  "t": 2.094,
                  "q": -0.5,
                  "p": -0.866,
                  "H": 0.5
                },
                {
                  "t": 2.618,
                  "q": -0.866,
                  "p": -0.5,
                  "H": 0.5
                },
                {
                  "t": 3.142,
                  "q": -1.0,
                  "p": -0.0,
                  "H": 0.5
                },
                {
                  "t": 3.665,
                  "q": -0.866,
                  "p": 0.5,
                  "H": 0.5
                },
                {
                  "t": 4.189,
                  "q": -0.5,
                  "p": 0.866,
                  "H": 0.5
                },
                {
                  "t": 4.712,
                  "q": -0.0,
                  "p": 1.0,
                  "H": 0.5
                },
                {
                  "t": 5.236,
                  "q": 0.5,
                  "p": 0.866,
                  "H": 0.5
                },
                {
                  "t": 5.76,
                  "q": 0.866,
                  "p": 0.5,
                  "H": 0.5
                },
                {
                  "t": 6.283,
                  "q": 1.0,
                  "p": 0.0,
                  "H": 0.5
                },
                {
                  "t": 6.807,
                  "q": 0.866,
                  "p": -0.5,
                  "H": 0.5
                },
                {
                  "t": 7.33,
                  "q": 0.5,
                  "p": -0.866,
                  "H": 0.5
                },
                {
                  "t": 7.854,
                  "q": 0.0,
                  "p": -1.0,
                  "H": 0.5
                },
                {
                  "t": 8.378,
                  "q": -0.5,
                  "p": -0.866,
                  "H": 0.5
                },
                {
                  "t": 8.901,
                  "q": -0.866,
                  "p": -0.5,
                  "H": 0.5
                },
                {
                  "t": 9.425,
                  "q": -1.0,
                  "p": -0.0,
                  "H": 0.5
                },
                {
                  "t": 9.948,
                  "q": -0.866,
                  "p": 0.5,
                  "H": 0.5
                },
                {
                  "t": 10.472,
                  "q": -0.5,
                  "p": 0.866,
                  "H": 0.5
                },
                {
                  "t": 10.996,
                  "q": -0.0,
                  "p": 1.0,
                  "H": 0.5
                },
                {
                  "t": 11.519,
                  "q": 0.5,
                  "p": 0.866,
                  "H": 0.5
                },
                {
                  "t": 12.043,
                  "q": 0.866,
                  "p": 0.5,
                  "H": 0.5
                },
                {
                  "t": 12.566,
                  "q": 1.0,
                  "p": 0.0,
                  "H": 0.5
                }
              ]
            },
            {
              "label": "r=1.3",
              "points": [
                {
                  "t": 0.0,
                  "q": 1.3,
                  "p": -0.0,
                  "H": 0.845
                },
                {
                  "t": 0.524,
                  "q": 1.1258,
                  "p": -0.65,
                  "H": 0.845
                },
                {
                  "t": 1.047,
                  "q": 0.65,
                  "p": -1.1258,
                  "H": 0.845
                },
                {
                  "t": 1.571,
                  "q": 0.0,
                  "p": -1.3,
                  "H": 0.845
                },
                {
                  "t": 2.094,
                  "q": -0.65,
                  "p": -1.1258,
                  "H": 0.845
                },
                {
                  "t": 2.618,
                  "q": -1.1258,
                  "p": -0.65,
                  "H": 0.845
                },
                {
                  "t": 3.142,
                  "q": -1.3,
                  "p": -0.0,
                  "H": 0.845
                },
                {
                  "t": 3.665,
                  "q": -1.1258,
                  "p": 0.65,
                  "H": 0.845
                },
                {
                  "t": 4.189,
                  "q": -0.65,
                  "p": 1.1258,
                  "H": 0.845
                },
                {
                  "t": 4.712,
                  "q": -0.0,
                  "p": 1.3,
                  "H": 0.845
                },
                {
                  "t": 5.236,
                  "q": 0.65,
                  "p": 1.1258,
                  "H": 0.845
                },
                {
                  "t": 5.76,
                  "q": 1.1258,
                  "p": 0.65,
                  "H": 0.845
                },
                {
                  "t": 6.283,
                  "q": 1.3,
                  "p": 0.0,
                  "H": 0.845
                },
                {
                  "t": 6.807,
                  "q": 1.1258,
                  "p": -0.65,
                  "H": 0.845
                },
                {
                  "t": 7.33,
                  "q": 0.65,
                  "p": -1.1258,
                  "H": 0.845
                },
                {
                  "t": 7.854,
                  "q": 0.0,
                  "p": -1.3,
                  "H": 0.845
                },
                {
                  "t": 8.378,
                  "q": -0.65,
                  "p": -1.1258,
                  "H": 0.845
                },
                {
                  "t": 8.901,
                  "q": -1.1258,
                  "p": -0.65,
                  "H": 0.845
                },
                {
                  "t": 9.425,
                  "q": -1.3,
                  "p": -0.0,
                  "H": 0.845
                },
                {
                  "t": 9.948,
                  "q": -1.1258,
                  "p": 0.65,
                  "H": 0.845
                },
                {
                  "t": 10.472,
                  "q": -0.65,
                  "p": 1.1258,
                  "H": 0.845
                },
                {
                  "t": 10.996,
                  "q": -0.0,
                  "p": 1.3,
                  "H": 0.845
                },
                {
                  "t": 11.519,
                  "q": 0.65,
                  "p": 1.1258,
                  "H": 0.845
                },
                {
                  "t": 12.043,
                  "q": 1.1258,
                  "p": 0.65,
                  "H": 0.845
                },
                {
                  "t": 12.566,
                  "q": 1.3,
                  "p": 0.0,
                  "H": 0.845
                }
              ]
            }
          ]
        },
        {
          "id": "damped_oscillator",
          "label": "Damped oscillator (negative control)",
          "dynamics": "q̇ = p, ṗ = −q − 0.2p",
          "basis": [
            "1",
            "q",
            "p",
            "q²",
            "qp",
            "p²"
          ],
          "singular_values": [
            9.51,
            6.35,
            4.14,
            2.07,
            0.91,
            0.18
          ],
          "sparse_coefficients": [
            0,
            0,
            0,
            0,
            0,
            0
          ],
          "law": "No invariant in the proposed basis",
          "nullity": 0,
          "independent_rank": 0,
          "max_residual": 0.18,
          "trajectories": []
        }
      ]
    },
    "open_problems": {
      "pipeline": [
        "decomposition",
        "description",
        "validation"
      ],
      "goals": [
        {
          "id": "monitor",
          "label": "Monitoring",
          "evidence_route": [
            "feature readout",
            "failure-case prediction",
            "held-out audit"
          ]
        },
        {
          "id": "control",
          "label": "Control",
          "evidence_route": [
            "causal intervention",
            "specificity control",
            "behavioral recovery",
            "competitive baseline"
          ]
        },
        {
          "id": "predict",
          "label": "Prediction",
          "evidence_route": [
            "pre-registered forecast",
            "novel distribution",
            "calibration",
            "competitive baseline"
          ]
        },
        {
          "id": "engineer",
          "label": "Engineering",
          "evidence_route": [
            "mechanism edit",
            "regression suite",
            "utility benchmark",
            "competitive baseline"
          ]
        },
        {
          "id": "microscope",
          "label": "Microscope AI",
          "evidence_route": [
            "latent structure",
            "human-checkable claim",
            "external validation",
            "scientific utility"
          ]
        }
      ],
      "axes": [
        {
          "id": "depth",
          "label": "description depth",
          "value": 0.45
        },
        {
          "id": "extent",
          "label": "network extent",
          "value": 0.25
        },
        {
          "id": "distribution",
          "label": "task-distribution extent",
          "value": 0.35
        },
        {
          "id": "timing",
          "label": "during-training access",
          "value": 0.15
        }
      ],
      "validation_ladder": [
        "correlational fit",
        "counterfactual effect",
        "unusual-failure prediction",
        "component replacement",
        "ground-truth recovery",
        "downstream utility",
        "competitive real-task baseline"
      ]
    }
  },
  "fixture_sha256": "b7501e9030591e4980b09cbe6bcfbc3b464c7e8afafea6876cd855783d760923"
};
