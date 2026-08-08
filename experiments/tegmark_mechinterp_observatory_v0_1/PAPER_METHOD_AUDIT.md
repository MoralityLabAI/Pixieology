# Six-paper method-to-visualization audit

This audit distinguishes visual similarity from method fidelity. The target is not a gallery of paper figures. It is an interface in which each interaction exposes a scientific decision the paper actually makes.

## Coverage verdict

| Paper | What the method needs a UI to expose | Prior Pixieology coverage | Observatory lens | Remaining real-evidence gap |
|---|---|---|---|---|
| [Seeing is Believing](https://arxiv.org/abs/2305.08746) | Geometric neuron embedding; L1/local/swap ablation; task-loss versus wiring-cost tradeoff; edge ablations | Weak. Existing graphs did not represent BIMT training or its ablations. | A five-method wiring workbench with signed edges and per-edge ablation delta | Train matched networks under the five ablations and ingest their actual weights |
| [Clock and Pizza](https://arxiv.org/abs/2306.17844) | Behavior held fixed while internal algorithm changes; attention-rate × width phase boundary; gradient symmetricity; distance irrelevance `q`; circularity | Strong conceptual coverage, but the old scalar `k` sweep was not faithful to the paper's phase space. | A selectable attention-rate × width algorithm map with the three diagnostics and accuracy shown together | Run modular-addition models across seeds and compute the paper's metrics |
| [Interpretable Networks using Hypernetworks](https://arxiv.org/abs/2312.03051) | Complexity pressure `β`; training time; categorical algorithm phase; order parameters; systematic generalization | Conceptual only. State-complexity scans lacked the hypernetwork and training-time axes. | A `β` × training-step phase map plus algorithm order parameters and an out-of-grid generalization view | Train a hypernetwork ensemble and preserve seed-level uncertainty |
| [MIPS](https://arxiv.org/abs/2402.05110) | Train → simplify → integer/Boolean autoencode → FSM → symbolic regress → execute/verify; explicit failures for noisy lattices and continuous computation | Best prior match, but it stopped at a transition table. | A compiler trace from latent points to integer code, FSM, formula, code, and verification, including a continuous-state failure case | Perform the integer autoencoding and symbolic regression on captured recurrent or transformer state |
| [Sparse Invariants](https://arxiv.org/abs/2305.19525) | Human-supplied basis; directional-derivative matrix; singular spectrum/nullspace; sparse rotation; functional independence; invariant trajectory | Partial and potentially misleading: sparse centroid signatures are not conservation laws. | A singular-spectrum and constant-along-trajectories workbench with a damped negative control | Build `G` from measured dynamics, then test held-out trajectories and functional independence |
| [Open Problems in Mechanistic Interpretability](https://arxiv.org/abs/2501.16496) | Decomposition → description → validation; goal-specific evidence; counterfactual and replacement tests; progress axes; competitive baselines | Broad claim discipline existed, without an explicit goal/axis surface. | A claim-route planner that makes missing validation rungs visible | Bind every real study to registered interventions, held-out outcomes, and baselines |

## Method-faithful reading

### 1. Seeing is Believing

The paper's unit of explanation is a trained wiring diagram whose geometry affected learning. A post-hoc node layout is therefore insufficient. BIMT combines three interventions: L1 pressure, a distance-weighted connection cost, and periodic neuron swaps that reduce that cost. The useful comparison is the ablation family: vanilla, L1, L1 + local, L1 + swap, and full BIMT. The UI must keep prediction loss next to connection cost because interpretability is purchased with a tradeoff, not inferred from graph prettiness.

The observatory's graph is synthetic, but it preserves that decision structure. Selecting a method changes active edges and the two objective readouts. Edge selection shows a counterfactual ablation delta rather than treating visual salience as causal evidence.

### 2. Clock and Pizza

This paper is a warning against behavior-only labels: networks with essentially identical modular-addition performance can implement Clock, Pizza, hybrid, or non-circular mechanisms. Its phase diagram has physical controls—attention rate and width—not an arbitrary embedding axis. The mechanism classifiers are also distinct:

- gradient symmetricity measures whether the two inputs affect the model symmetrically;
- distance irrelevance `q` separates Pizza-like logits from Clock-like distance dependence;
- circularity filters mechanisms outside the circular family.

The observatory keeps validation accuracy visible while the algorithm label changes. That is the scientific point of the view.

### 3. Generating Interpretable Networks using Hypernetworks

The hypernetwork is a distribution-producing instrument. Its interpretable regimes emerge over complexity pressure `β` and training time, with categorical algorithms described by order parameters such as double-sidedness and strongest-connection structure. A faithful view therefore needs a phase map, not only a complexity slider. Seed dependence is a measurement, not noise to hide. Systematic generalization to network sizes outside the training support is a separate check and should not be collapsed into the phase label.

### 4. MIPS / Opening the AI Black Box

MIPS is a compiler pipeline, not merely state clustering. Its output becomes operational only after integer/Boolean autoencoding makes a lookup table exact enough for symbolic regression, code emission, and execution. The UI shows every stage so that an attractive latent projection cannot masquerade as a synthesized mechanism.

The paper reports two important failure families and the lens makes one selectable:

1. noise or nonlinearity corrupts an otherwise near-discrete lookup table;
2. the network performs genuinely continuous computation, violating the finite-state assumption.

An unavailable downstream stage is displayed as unavailable, not inferred.

### 5. Sparse invariants

Sparsity alone is not conservation. The method begins with dynamics and a proposed basis, builds the matrix of basis derivatives along the vector field, detects its nullspace with an SVD, rotates that space toward sparse laws, and checks functional independence. A defensible UI therefore needs all of these observable checkpoints:

`dynamics + basis → singular spectrum → sparse coefficients → independent laws → held-out trajectory constancy`

The damped oscillator is an essential negative control: the familiar energy expression is no longer conserved, so the lens must be able to report no invariant in the proposed basis.

### 6. Open Problems in Mechanistic Interpretability

This paper supplies the governance layer. An interpretation is a hypothesis. A visualization becomes useful when it routes that hypothesis toward counterfactual predictions, unusual-failure explanations, component replacement, ground-truth recovery, downstream engineering utility, and ultimately competitive baselines on real tasks. The paper also distinguishes progress by description depth, network extent, task-distribution extent, and whether understanding is post-training or developed during training.

The claim-route lens makes those axes and rungs explicit. It prevents a polished decomposition from being silently promoted to a validated mechanism.

## Synthesis for low-dimensional control

The six papers form a usable sequence for the Pixieology strategy:

1. **Shape the representation** with BIMT-like locality or other training-time constraints.
2. **Detect algorithmic phases** with Clock/Pizza diagnostics instead of performance alone.
3. **Map the phase landscape** across complexity and training using the hypernetwork view.
4. **Compile candidate dynamics** into an executable mechanism with MIPS.
5. **Search for conserved control coordinates** with the sparse-invariant pipeline.
6. **Escalate claims by intervention evidence** using the Open Problems validation route.

Holonomy is valuable only after this sequence identifies a state space and transport rule. A loop-dependent readout can then diagnose context-sensitive transport. It cannot by itself establish an algorithm, a conservation law, or control.

## Claim boundary

Every number in `example_data.json` is a deterministic, method-faithful synthetic fixture. It tests interaction design and machine-readable contracts. It is not a reproduction of the papers, not a result from a trained model, and not evidence about Pixie or Qwen.
