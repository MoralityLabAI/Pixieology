# Design question register

| ID | Question | Comparison | Primary measure | Default on tie |
| --- | --- | --- | --- | --- |
| `orientation` | What should orient a researcher before local comparison? | compact depth heatmap / globe preview / case-first | correct band location, time | heatmap |
| `threshold` | How should epsilon be controlled? | continuous slider / exact dendrogram births | relation accuracy, time | dendrogram births with numeric epsilon |
| `language` | How much topology language should be visible? | technical-first / plain plus technical | robustness accuracy, unsupported claims | plain plus technical |
| `jobs` | Where should proposed work appear? | inline queue / post-diagnosis drawer | correct job or no-job choice | gated drawer |
| `workflow` | Should progressive triage replace the dense explorer default? | baseline / triage | accuracy, time, unsupported claims | retain baseline |
| `learner` | Is a guided investigation safe for learner/gamers? | conventional wording / guided triage | transfer accuracy, unsupported claims | do not promote |
| `agent` | Can agents complete the same tasks without reading SVG geometry? | receipt API / visual inference | deterministic completion | receipt API required |

## Fixed decisions

- Researchers break ties; learner/gamer and agent surfaces are layered on the
  same evidence contract.
- The browser is inspect-only. It cannot authorize or execute jobs.
- Direct threshold edges and transitive closure are distinct outputs.
- S is unavailable for fixture and activation cases without a registered
  context loop. Synthetic tau/q controls belong to a theory sandbox.
- Parameter and synthetic fixtures may settle shell and comprehension
  questions, but not motif usefulness or causal value.

## Workflow decision rule

Promote progressive triage only with at least six paired researcher sessions,
correctness increment at least `0.15`, median paired time ratio at most `0.90`,
no increase in unsupported claims, and at least `0.80` correct job/no-job
choices. If accuracy and claim discipline pass but time does not, retain triage
as an optional guided mode. Otherwise retain the baseline.
