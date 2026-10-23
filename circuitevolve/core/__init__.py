"""CircuitEvolve core (2026-10-13): ONE pipeline with three parts plus a selection loop.

  circuit.py   Clifford+Rz circuit object, QASM in/out, TKET stage-1 inputs, <=4-qubit windows
  mutator.py   LLM prompt for one window + literal parsing of replacement windows (never exec/eval)
  verifier.py  wrapper around the FROZEN blocks/verify_block.py: exact D[omega] or operator-norm check of a
               window at its allowance; whole-circuit check against the original circuit (n <= 20)
  metric.py    T-count under BQSKit's convention (gridsynth at eps_rz = eps_synth / N_Rz), rotations, CNOTs
  ledger.py    total error eps: v0 rule eps/2 for window rewrites, eps/2 for final synthesis
  loop.py      selection loop: best + a few diverse circuits, playbook with measured-improvement evidence,
               one JSON line per LLM call in results/window_runs/<tag>.jsonl
See docs/CORE.md.
"""
