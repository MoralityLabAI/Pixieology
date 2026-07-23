# Human learning and craft protocol

These studies begin only after at least one motif is confirmed descriptively.
Synthetic agents may check task mechanics, API determinism, and scoring code;
they are never counted as participants or human evidence.

## Craft study

- Design: within-participant, counterbalanced raw-view versus motif-view order.
- Minimum sample: 12 complete paired participants.
- Unit: a held-out activation-conditioned case.
- Tasks: locate a comparison depth, identify direct versus closure-only
  partners, choose the next intervention, and state the evidence boundary.
- Primary outcomes: scored answer correctness, elapsed time, and unsupported
  causal claims.
- Registered pass: motif view improves correctness by at least 0.15, has a
  median paired time ratio no greater than 0.90, and does not increase
  unsupported causal claims.

The motif view may expose a confirmed label, exemplar, chart state, direct
edges, closure component, chain excess, bridges or `bridge: none`, and the
epsilon-cut dendrogram. The raw view exposes the same case and controls but no
motif card or recommended next investigation.

## Learning study

- Design: between-participant conventional-versus-motif lesson, randomized and
  balanced.
- Minimum sample: 32 total participants.
- Content: direct tolerance edges, transitive closure, clique versus chained
  convergence, bridge robustness, persistence across W, and claim boundaries.
- Primary outcome: accuracy on transfer cases not used in either lesson.
- Registered pass: motif lesson improves transfer accuracy by at least 0.15 and
  retains at least 80% of its immediate pre/post gain.

No study item asks participants to infer literal étale branching, monodromy
over the interval W, semantic identity, or causality from recurrence alone.
Condition labels are frozen before responses are examined.

## Agent-facing task surface

The browser exposes deterministic case and receipt methods:

```javascript
const cases = window.PixieEtaleExplorer.listCases();
const receipt = window.PixieEtaleExplorer.loadCase(cases[0].case_id);
window.PixieEtaleExplorer.setState({ glue_tolerance: 0.3 });
const answerContext = window.PixieEtaleExplorer.getAnalysis();
```

Every scored task records the case ID, condition, starting state, final state,
answer, correctness, elapsed milliseconds, and unsupported-causal-claim flag.
Learning rows additionally record pretest, immediate, and transfer accuracy.
