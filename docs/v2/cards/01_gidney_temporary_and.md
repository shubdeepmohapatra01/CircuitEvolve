# Temporary logical-AND adder (Gidney 2018)

**What it does.** Replaces a compute/uncompute pair of Toffolis whose target is a fresh ancilla by a
*temporary logical-AND*: compute `t = a AND b` into an ancilla that starts in |0>, using 4 T; later erase it
with an X-basis measurement of `t` and, on outcome 1, a classically controlled CZ(a, b) (0 T). Applied to
ripple-carry addition this lowers the n-bit adder from 8n + O(1) to 4n + O(1) T; the paper also gives an
n-bit controlled adder with 8n + O(1) T.

**When it applies (pattern).** `ccx(a, b, t)` with `t` a clean |0> ancilla, followed later by the mirror
`ccx(a, b, t)` with `a`, `b` unchanged in between (carry ladders, tof_n ancilla ladders, Grover
oracles). Each such pair: 14 T -> 4 T.

**Cost.** 4 T per AND, 0 T per uncompute; one clean ancilla per stored AND (O(n) for the adder); one
measurement + one classically controlled CZ per uncompute.

**Verification mode: relaxed.** Not unitary-equivalent to the Toffoli pair on all inputs: it needs the
ancilla precondition (|0>) and measurement branches. Check with the specification contract
(`circuitevolve/verify.py`, invariant 2).
In the IR: `and_compute` / `and_uncompute` (`circuitevolve/ir.py`).

**Worked example (run: `results/v2/cards_worked_examples.json`, key `temporary_and`).** `ir._AND_COMPUTE`
has 4 T and maps |a,b,0> -> |a,b,ab> on all four basis inputs; measuring `t` in the X basis and applying
CZ(a,b) on outcome 1 leaves each branch with probability 1/2 and a phase independent of (a, b). For tof_3
(ancilla q4 computed by ccz(0,1,4) and uncomputed by the mirror), the construction gives 4 + 7 = 11 T by
counting, vs 15 T for pyzx (count by construction, not yet verified; tier-1 task).

**Citation.** C. Gidney, "Halving the cost of quantum addition", *Quantum* 2, 74 (2018),
doi:10.22331/q-2018-06-18-74, arXiv:1709.06648.
