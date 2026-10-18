# Toffoli with 4 T via measurement (Jones 2013)

**What it does.** Implements a full Toffoli `ccx(a, b, c)` with Clifford operations plus four T gates
instead of seven: compute `a AND b` into one clean ancilla (4 T), CNOT the ancilla onto `c`, then erase the
ancilla by X-basis measurement and a classically controlled CZ(a, b). Jones also shows that adding n
control inputs to a controlled gate costs 4n T (best prior 8n), and gives an error-detecting 8-T Toffoli
variant (post-selection suppresses error from 4p to 28p^2 to lowest order).

**When it applies (pattern).** Any Toffoli whose target is not a fresh ancilla (in-place targets, e.g.
the final Toffoli of a tof_n ladder, MAJ/UMA steps of a Cuccaro adder) when one clean ancilla is available.
Equivalent to card 01 used as compute + CNOT + uncompute.

**Cost.** 4 T, 1 clean ancilla, 1 measurement, 1 classically controlled CZ per Toffoli (vs 7 T, 0 ancillas).
T-depth can be 1 with the AND written in T-depth-one form (card 04).

**Verification mode: relaxed.** Uses an ancilla precondition and a measurement; check with the
specification contract (invariant 2), not unitary equality.

**Worked example (run: `results/v2/cards_worked_examples.json`).** Standard Toffoli `ir._CCX`: 7 T, 6 CX,
distance 3e-33 to CCX (`toffoli_7T`). The 4-T AND gadget and its measurement uncompute are verified under
`temporary_and`; the Jones Toffoli is AND -> CX(anc, c) -> uncompute = 4 T (`jones_toffoli`, derived count).
In the suite: every ccz in tof_n / barenco_tof_n / adders is a candidate (MANIFEST.csv `ccx_count`).

**Citation.** C. Jones, "Low-overhead constructions for the fault-tolerant Toffoli gate",
*Phys. Rev. A* 87, 022328 (2013), doi:10.1103/PhysRevA.87.022328, arXiv:1212.5069 (arXiv title: "Novel
constructions for the fault-tolerant Toffoli gate").
