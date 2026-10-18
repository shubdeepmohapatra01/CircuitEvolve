# Relative-phase Toffoli (Maslov 2016)

**What it does.** A relative-phase Toffoli equals Toffoli up to a diagonal unitary D (phases on basis
states). It is cheaper than the exact gate; Maslov gives circuit identities that replace certain
configurations of multiple-control Toffolis with relative-phase implementations without changing the
overall function, reducing CNOT-count, T-count and ancilla count of multiple-control Toffoli circuits.

**When it applies (pattern).** A Toffoli `G` that is later undone by `G^dagger` where everything in
between commutes with D (in particular gates that only use the target in the Z basis as a control, e.g.
CX(t, x), or that act on other qubits): `G . W . G^dagger = R . W . R^dagger` with `R = D G`. Typical:
the inner compute/uncompute Toffolis of barenco_tof_n and tof_n ladders, carry compute/uncompute.

**Cost.** RCCX (Margolus-type): 4 T, 3 CX, no ancilla, no measurement. RC3X (3 controls): 8 T, 6 CX.
A pair of RCCX replaces a pair of 7-T Toffolis: 14 T -> 8 T.

**Verification mode: exact** when used in cancelling pairs (the whole pattern is unitary-equivalent; check
the enclosing window with the exact D[omega] verifier). An isolated relative-phase Toffoli is NOT a Toffoli
(operator distance 2 here) and must be rejected.

**Worked example (run: `results/v2/cards_worked_examples.json`).** qiskit `RCCXGate` lowered to Clifford+T:
4 T, 3 CX, equal to CCX up to a diagonal, operator distance to CCX 2.0 (`rccx`). `RC3XGate`: 8 T, 6 CX,
equal to C3X up to a diagonal (`rc3x`). RCCX . CX(2,3) . RCCX^dagger vs CCX . CX(2,3) . CCX: 8 T vs 14 T,
distance 4.9e-16 (`rccx_pair_around_cx`).

**Citation.** D. Maslov, "Advantages of using relative-phase Toffoli gates with an application to multiple
control Toffoli optimization", *Phys. Rev. A* 93, 022311 (2016), doi:10.1103/PhysRevA.93.022311,
arXiv:1508.03273.
