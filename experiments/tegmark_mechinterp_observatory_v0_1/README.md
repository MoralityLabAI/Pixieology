# Physics of Mechanisms Observatory v0.1

A focused six-lens UI study translating the Tegmark-lineage mechanistic-interpretability papers into testable interactions.

The observatory is designed around one question per paper:

1. Did geometric pressure actually simplify the learned wiring?
2. Did the internal algorithm change while behavior stayed fixed?
3. Which algorithmic phase emerged across complexity and training time?
4. Can the latent mechanism compile into executable, verified code?
5. Is a sparse expression genuinely conserved along the dynamics?
6. What evidence is still missing before the interpretation supports a control claim?

## Run

From this directory:

```powershell
python -m http.server 8765
```

Open `http://localhost:8765/`.

Regenerate the deterministic fixture:

```powershell
python build_example.py
```

Run the contracts:

```powershell
python -m unittest tests/test_example_data.py
node --test tests/*.test.mjs
```

## Captured run

- `example_exploration_receipt.json` records a deterministic six-step agent traversal from BIMT wiring through the control-claim route.
- `visual_test_receipt.json` records a real browser pass over all six lenses, the continuous-state and no-invariant negative controls, the 375 × 812 responsive layout, and console status.
- `coverage.json` is the compact machine-readable answer to “what is covered, and what would turn it into evidence?”

The browser pass found and fixed one claim-significant display issue: a residual of `2e-8` was initially rendered as `0`. Small nonzero quantities now use scientific notation.

## Evidence boundary

The bundled data is a `method_faithful_synthetic_fixture`. It demonstrates the UI and agent-facing data contract only. It contains no paper reproduction, activation capture, Qwen/Pixie result, or empirical control evidence.

See [PAPER_METHOD_AUDIT.md](PAPER_METHOD_AUDIT.md) for the primary-source audit and the real experiment required behind each lens.
