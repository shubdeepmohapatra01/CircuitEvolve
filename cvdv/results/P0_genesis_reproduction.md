# P0 — Genesis reproduction and correctness audit (2026-10-13)

Genesis = ruadapt/Genesis-CVDV-Compiler @ 996d5d30 (Chen et al., ISCA'25, arXiv:2505.13683), built
with conda openjdk 17 + antlr 4.13.2 in env `cvdv-opt`. Runner `scripts/run_genesis.py` runs
Genesis' `src.main` unchanged, adding a seed and a dump of the final qumode mapping.

## 1. Metrics reproduce

`src/cvdv/metrics.py` (1-op, 2-op, duration with latency 1 / 20) is an independent re-implementation.
It equals Genesis' own `--stats` output on all 19 compiled outputs (13 full-size Table-5 benchmarks in `genesis_table5_repro.csv` plus the 6 `*_small` instances); hubbardHolstein_1 had not finished compiling.

Against the paper's Table 5:
* IR columns (#gates in IR, #Pauli strings) match exactly for every row.
* Final gate count and duration match exactly for kerr_1, heisenberg_2, heisenberg_3, and duration
  for heisenberg_1. Other rows differ by 1–12 % in both directions because Genesis' router uses
  networkx simulated-annealing TSP with `seed=None`; repeated runs differ. Baselines from here on
  use the seeded runner and the best of several seeds.
* hubbardHolstein_1 (688,011 gates in the paper) was still compiling after > 45 min.

Gate origin (`genesis_gate_origin.csv`): share of final gates produced by L1 synthesis
(the rest is multi-Pauli gadgets + routing SWAPs): Kerr 69 %, Z2-Higgs 56–62 %, Bose-Hubbard 13–28 %,
electron-vibration 22–25 %, Heisenberg 0 %.

## 2. Correctness audit (`experiments/audit_genesis.py` → `genesis_audit.json`, `genesis_audit.png`)

Simulator: `src/cvdv/sim.py`, truncated Fock space, Genesis Table 2 conventions; every result
below is unchanged between cutoffs 8 and 12 (Kerr: 16 and 22). The Pauli-gadget result was
reproduced with an independent QuTiP implementation.

| Item | Finding |
|---|---|
| Hopping `a†b + b†a` → BS, `n` → R, `σz(a†b+b†a)` → CBS | exact (infidelity < 1e-14) |
| Multi-Pauli exponential gadget, odd weight (Z, ZZZ, X, XXX, XYZ) | ancilla returns to vacuum; implements exp(±2i\|c\|² P) instead of the specified exp(c P) for `pauli(c)` (process overlap with spec 0.89–0.99 at c = 0.3i) |
| Multi-Pauli gadget, even weight (ZZ, ZZZZ, XX, YY, YZ) | ancilla qumode does **not** return to vacuum (worst-case return probability 0.24–0.62); output is entangled with the ancilla |
| n² term (Bose-Hubbard on-site, Z2-Higgs), 20 gates, 6 two-op | infidelity 0.72 at θ = π/4 and 0.80 at θ = π/2 (n ≤ 2 probes). Error scales as θ² (first order), not θ³ as a correct group-commutator approximation would; the leading-order phase has the wrong sign. The first 4 gates `R(−x) CR(−2x) R(x) CR(2x)` compose to the identity |
| Kerr `a†a†aa` (kerr_1 logical circuit, 409 gates, 19 ancilla qubits) | infidelity 0.999 (strict), 0.88 (ancilla-garbage tolerant) |
| Heisenberg physical circuit | infidelity ≈ 1 (all terms are even-weight Pauli strings) |
| Hubbard-Holstein IR | 64 of 132 `pauli(c)` lines carry real c (fermionic hopping), so exp(c P) is not unitary |

Interpretation: under the gate definitions in Genesis' own Table 2, the compiled circuits for 5 of the
6 model families do not implement the Trotter step they are compiled from. Only the purely
quadratic bosonic terms are correct. A convention mismatch (e.g. an internal sign or ordering
convention different from Table 2) could explain the n² sign, but not the even-weight gadget failure,
which fails under all 8 sign combinations of R, CP and BS tested, nor the 2|c|² vs |c| angle.

## 3. Consequence for the comparison contract

The approved contract was "matched error budget: ours must be at least as accurate as Genesis".
With Genesis' error O(1) on most benchmarks, that budget is vacuous. See the open question in the
session log: fix an absolute accuracy target and compare against a *corrected* Genesis baseline.
