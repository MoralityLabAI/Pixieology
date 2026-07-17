# Five-dimensional character navigation hypotheses

This is a retail-game UX experiment. It does not assert that the projection is a
model's literal latent geometry or make a scientific claim for the Jinn/Beast paper.

The proposed embodiment is `2 + 2 + 1`:

- left wing: Wonder and Play;
- right wing: Care and Resolve;
- head: Reflection.

Each character form is a bounded tuple in `[0, 1]^5`. A warp is the Euclidean
geodesic between two tuples, animated with a time easing that does not change the
path. The salon map is a fixed two-component PCA projection fitted only to the
twelve authored prototype forms.

## Registered prototype gates

1. **Embodiment legibility:** every dimension has one stable anatomical channel;
   exactly two dimensions affect each wing and one affects the head.
2. **Synchronized editing:** anchor selection and fine-grained controls update the
   same five-dimensional state.
3. **Neighborhood fidelity:** pairwise 5D distance and projected 2D distance have
   Spearman correlation at least `0.80`; normalized projection stress is at most
   `0.30`.
4. **Warp continuity:** interpolation never leaves `[0, 1]^5`, moves monotonically
   along the endpoint path, and reverses exactly.
5. **Ontology boundary:** no authored retail preset uses Jinn, Beast of the Earth,
   or related theological labels as a generic personality class.
6. **Human comprehension:** after no more than two minutes, at least four of five
   players can identify which anatomy controls each dimension, warp to an authored
   form, alter it, and return. This gate cannot be established by unit tests.

Automated gates evaluate whether the interaction is internally honest. They do not
establish whether the interface is delightful or comprehensible to retail players.

The stronger product test is the counterbalanced embodied-versus-flat comparison in
`AB_TEST_PROTOCOL.md`. Its thresholds were fixed before collecting participant
receipts so that a visually appealing prototype cannot redefine its own success.
