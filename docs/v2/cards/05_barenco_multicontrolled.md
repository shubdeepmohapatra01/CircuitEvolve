# Multiple-control Toffoli decompositions (Barenco et al. 1995)

**What it does.** Decomposes generalized (n-bit) Deutsch-Toffoli gates into one-bit gates and CNOT, with
upper and lower bounds on gate counts. The construction used in the suite (barenco_tof_m) implements an
m-control Toffoli with 4(m - 2) Toffolis using m - 2 *borrowed* work qubits whose state is arbitrary and is
restored; the alternative clean-ancilla ladder (tof_m, Nielsen-Chuang style) uses 2m - 3 Toffolis and
m - 2 ancillas that must start in |0>.

**When it applies (pattern).** A multi-controlled X/Z (MCX) in a logical circuit: Grover oracles, modular
comparisons, controlled adders, `mcx` in high-level descriptions. Choose by ancilla availability: dirty
qubits -> Barenco (exact unitary, no precondition); clean ancillas -> ladder, then cards 01/03 make the
ladder cheap (temporary ANDs or relative-phase Toffolis inside the ladder).

**Cost (Toffolis x 7 T before optimization).** barenco_tof_m: 4(m-2) Toffolis; tof_m: 2m-3 Toffolis.

**Verification mode.** Barenco borrowed-qubit form: exact (unitary on all inputs). Clean-ancilla ladder:
relaxed when it relies on |0> ancillas; the benchmark files themselves are compared by exact unitary.

**Worked example (from `benchmarks/nam_arith/MANIFEST.csv`, computed).** barenco_tof_3/4/5/10: 4, 8, 12, 32
ccz = 4(m-2); tof_3/4/5/10: 3, 5, 7, 17 ccz = 2m-3. Published optimized T (Nam et al. 2018 Table 4):
barenco_tof_m 16/28/40/100, tof_m 15/23/31/71, i.e. the ladder is cheaper after optimization.

**Citation.** A. Barenco, C. H. Bennett, R. Cleve, D. P. DiVincenzo, N. Margolus, P. Shor, T. Sleator,
J. Smolin, H. Weinfurter, "Elementary gates for quantum computation", *Phys. Rev. A* 52, 3457 (1995),
doi:10.1103/PhysRevA.52.3457, arXiv:quant-ph/9503016.
