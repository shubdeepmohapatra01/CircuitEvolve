# cvdv — LLM-evolved rewrite rules for hybrid CV-DV Hamiltonian simulation

Standalone sub-project of CircuitEvolve (the Clifford+T track lives in `../circuitevolve`; the two
are merged later). Baseline: Genesis (Chen et al., ISCA'25). ISA: phase-space + beam splitter
{qubit rotations, R, D, BS, CD, CR, CP}. Metrics: Genesis' 1-op / 2-op / duration (1 / 20) plus
verified error. Design: `docs/DESIGN_MEMO.md`. Status: `results/P0_genesis_reproduction.md`.

```
src/cvdv/qasm.py      CVDV-QASM reader/writer (literal-only parameter parsing)
src/cvdv/sim.py       truncated-Fock statevector simulator, Genesis Table 2 conventions
src/cvdv/target.py    Trotter-term specification from Genesis' intermediate IR
src/cvdv/metrics.py   Genesis metrics, re-implemented (matches --stats exactly)
src/cvdv/verify.py    whole-circuit verifier vs ordered product of terms, two cutoffs
scripts/              fetch/build Genesis (pinned), seeded runner, batch runner
experiments/          audit_genesis.py
results/              append-only outputs
third_party/genesis/  Genesis checkout (gitignored; scripts/fetch_genesis.sh)
```

Environment: `cvdv-opt` (python 3.12, openjdk 17, antlr 4.13.2, numpy/scipy/qutip/sympy/networkx).
