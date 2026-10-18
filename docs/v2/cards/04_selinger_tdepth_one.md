# T-depth-one Toffoli / doubly-controlled gates (Selinger 2013)

**What it does.** Writes CCZ (hence Toffoli) as a phase polynomial: (-1)^{x1 x2 x3} =
prod over the 7 non-empty parities p of x1, x2, x3 of omega^{+-p}, with T on x1, x2, x3, x1+x2+x3 and T^dagger
on the three pairwise parities. Computing the 4 multi-variable parities onto 4 ancillas lets all 7 T/T^dagger
act in one layer: T-depth 1 with four ancillas. More generally a class of circuits reduces to T-depth 1 given
enough ancillas; adding one control to any controlled gate costs at most 8 extra T and T-depth 2.

**When it applies (pattern).** Any ccz/ccx (or a block of commuting phase-polynomial terms) when the
objective includes T-depth and clean ancillas are available. It does NOT lower T-count (still 7 per CCZ);
under the project's lexicographic objective (correctness, T-count, qubits, T-depth) it only breaks ties.

**Cost.** 7 T, T-depth 1, 4 clean ancillas (returned to |0>), no measurement; 18 CX in our construction.

**Verification mode: relaxed (ancilla precondition, no measurement)**: exact on the clean-ancilla subspace;
not unitary-equivalent on dirty ancillas.

**Worked example (run: `results/v2/cards_worked_examples.json`, key `selinger_tdepth1_ccz`).**
CX ladder writing x1+x2, x1+x3, x2+x3, x1+x2+x3 to 4 ancillas, one layer [T, T, T, T^dag, T^dag, T^dag, T],
mirror ladder: 7 T, 18 CX; operator distance to CCZ on the ancilla-|0> subspace 2.3e-17, ancilla leakage 0.

**Citation.** P. Selinger, "Quantum circuits of T-depth one", *Phys. Rev. A* 87, 042302 (2013),
doi:10.1103/PhysRevA.87.042302, arXiv:1210.0974.
