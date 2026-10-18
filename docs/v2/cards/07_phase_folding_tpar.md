# Phase folding and T-par (Amy, Maslov, Mosca 2014)

**What it does.** Inside a {CNOT, X, T, S, Z} region every phase gate applies omega^k to a parity (XOR of
input variables) of the region's inputs: the region is a phase polynomial plus a linear reversible map.
Terms on the same parity merge (T + T = S, T + T^dagger = I), which cuts T-count ("phase folding"); T-par then
re-synthesizes each region, grouping parities into T layers by matroid partitioning to minimize T-depth,
optionally with ancillas. Hadamard gates bound the regions.

**When it applies (pattern).** Any Clifford+T circuit with repeated parities across CNOT networks: expanded
Toffoli cascades (each 7-T Toffoli is 7 parity terms), adders, GF(2^n) multipliers, Hamming / hwb circuits.
Also on Clifford+Rz with arbitrary angles (merge angles on equal parities).

**Cost.** Never increases T-count; no ancillas or measurements for T-count reduction (ancillas only for
T-depth). Reported on its benchmarks: up to 65.7 % T-count and 87.6 % T-depth reduction without ancillae.

**Verification mode: exact** (unitary-preserving; D[omega] check of the rewritten window).

**Worked example (run: `results/v2/cards_worked_examples.json`, key `phase_folding_parity`).**
`cx(0,1) t(1) cx(0,1)` and `cx(1,0) t(0) cx(1,0)` both put T on parity x0+x1; the two terms fold into S on
that parity: 2 T -> 0 T (pyzx), dense-unitary distance 1e-16. The project already has a deterministic
phase-folding pass (`circuitevolve/blocks/passes.py`).

**Citation.** M. Amy, D. Maslov, M. Mosca, "Polynomial-time T-depth optimization of Clifford+T circuits
via matroid partitioning", *IEEE Trans. Comput.-Aided Des. Integr. Circuits Syst.* 33(10), 1476-1489 (2014),
doi:10.1109/TCAD.2014.2341953, arXiv:1303.2042.
