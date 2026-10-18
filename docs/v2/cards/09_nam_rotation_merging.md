# Rotation merging and Hadamard reduction (Nam, Ross, Su, Childs, Maslov 2018)

**What it does.** Five unitary-preserving subroutines over {H, X, CNOT, Rz(theta)}: (1) Hadamard gate
reduction (rewrite rules that remove H gates and so enlarge {CNOT, Rz} regions); (2) single-qubit gate
cancellation and merging, commuting gates through CNOTs; (3) two-qubit (CNOT) cancellation; (4) rotation
merging with phase polynomials - in each {NOT, CNOT, Rz} region, Rz gates on the same affine parity of the
region inputs are merged (continuous angles allowed); (5) floating Rz gates plus gate-count-preserving and
-reducing rewrite rules for CNOT reduction. Light = sequence 1,3,2,3,1,2,4,3,2; Heavy = 1,3,2,3,1,2,5; both
repeated to a fixed point (paper section "General-purpose optimization algorithms").

**When it applies (pattern).** Clifford+T arithmetic (Toffoli-expanded circuits), QFT/adder circuits with
continuous phases, product-formula simulation circuits. Preserves the layout of the original algorithm.

**Cost.** Never increases T or CNOT count; no ancillas or measurements.

**Verification mode: exact** (unitary-preserving).

**Worked example (authors' optimized files, njross/optimizer@8cd55d5, counted and verified by
`experiments/v2_bench_baselines.py`).** adder_8: 399 -> 215 T (Light and Heavy), matching Nam et al. Table 4;
tof_3: 21 -> 15 T. On the same input pyzx reaches 173 T for adder_8 (card 08), i.e. ZX phase teleportation
finds merges across Hadamards that the region-based merging does not.

**Citation.** Y. Nam, N. J. Ross, Y. Su, A. M. Childs, D. Maslov, "Automated optimization of large quantum
circuits with continuous parameters", *npj Quantum Information* 4, 23 (2018),
doi:10.1038/s41534-018-0072-4, arXiv:1710.07345.
