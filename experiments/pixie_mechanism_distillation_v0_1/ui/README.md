# Mechanism Law Lab

This interface is a second organizing concept for the Pixie mech-interp UX.
The etale atlas asks where representations become locally equivalent. The Law
Lab asks whether observations can be compressed into a small executable law
that survives a causal test.

The workflow is deliberately claim-shaped:

1. **Observe** a fidelity/complexity phase scan instead of hiding the cluster
   count as a tuning choice.
2. **Compress** the selected activation partition into an executable state ×
   input transition table.
3. **Align** Base and Pixie programs under a bijective state relabeling, keeping
   behavioral agreement separate from mechanism agreement.
4. **Falsify** the program with a registered targeted patch, matched random
   patch, and guardrail readout.

The checked-in dataset is generated from deterministic synthetic fixtures. It
exists to make the interaction and agent contracts testable before activation
capture. `example_data.json` is the machine-readable source;
`example_data.js` is the same payload wrapped for direct `file://` opening.

## Agent contract

The browser exposes `window.PixieMechanismLawLab`:

- `getState()` returns the minimal presentation state;
- `snapshot()` returns a claim-bounded, machine-readable current view;
- `dispatch(action)` accepts the same actions as visible controls;
- `dataHash` binds the view to the captured example dataset.

Supported actions are `SELECT_FAMILY`, `SET_COMPLEXITY`, `SELECT_CANDIDATE`,
`SELECT_TRANSITION`, and `SELECT_INTERVENTION`. Every state change emits a
`lawlab:statechange` DOM event whose detail is the same agent snapshot.

## Reproduce

```powershell
python ..\run.py build-ui-example --output-root . --families 4
node tests\page-contract.test.mjs
node tests\agent-smoke.mjs
```

Open `index.html` directly afterward. No server, model, adapter, or network
request is required.
