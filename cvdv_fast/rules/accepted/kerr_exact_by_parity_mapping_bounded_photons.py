from cvdv_fast.api import Rule, Op
import math
import cmath


def synth(t, g, r):
    # n2: exp(-i theta n^2) on a single qumode, verified exact for n <= 3.
    # n^2 = 3n - p n + (3/2) p - 3/2 where p = (-1)^n is photon-number parity.
    # exp(-i theta n^2) = e^{i 3theta/2} R(3theta) exp(+i theta p n) exp(-i (3theta/2) p)
    # (global phase dropped; the three diagonal-in-n factors commute).
    # A local qubit ancilla coupled to the mode is parity-mapped via
    # V = H . CR(pi) . H  ==  exp(-i pi n X / 2), giving V|0,n> = c_n |n mod 2, n>.
    # On the mapped register, D = CR(-2 theta) . rz(3 theta) realises
    # exp(+i theta Z n) exp(-i (3theta/2) Z) == exp(-i theta' p) with theta' = -theta n + 3theta/2 (ancilla = p).
    # Unmapping with V^+ = H . CR(-pi) . H returns the ancilla exactly to |0> for every n
    # (the c_n phases cancel against their conjugates), leaving the mode-only operator, and R(3theta)
    # supplies the remaining 3n term.
    if t.kind != "n2":
        return None
    if len(t.m) != 1:
        return None

    theta = t.theta
    m = t.m[0]

    # Use the term's own local qubit if it carries one (already coupled to this mode, no routing needed);
    # otherwise take a fresh ancilla qubit keyed to the mode so it is guaranteed physically coupled.
    if len(t.q) >= 1:
        q = t.q[0]
    else:
        q = g.anc_qubit(m[1])

    # Parity map V = H . CR(pi) . H  (time order: H, CR, H)
    g.h(q)
    g.CR(math.pi, q, m)
    g.h(q)

    # Diagonal phase D = CR(-2 theta) . rz(3 theta), acting as exp(-i theta' Z) with Z == p on the ancilla
    g.CR(-2.0 * theta, q, m)
    g.rz(3.0 * theta, q)

    # Unmap V^+ = H . CR(-pi) . H; ancilla returns exactly to |0> for every n <= 3
    g.h(q)
    g.CR(-math.pi, q, m)
    g.h(q)

    # Remaining linear-in-n piece (will merge with adjacent R gates via merge_same_wire_rotations)
    g.R(3.0 * theta, m)


RULE = Rule(
    name="kerr_exact_by_parity_mapping_bounded_photons",
    kind="synth",
    contract="exact",
    term_kinds=("n2",),
    synth=synth,
    idea="Write p = (-1)^n for photon-number parity. On the verified subspace n in {0,1,2,3}, any function of n "
         "is a line on each parity class (two points per class), giving n^2 = 3n - p n + (3/2) p - 3/2 exactly. "
         "Hence exp(-i theta n^2) = e^{i 3theta/2} R(3theta) exp(+i theta p n) exp(-i (3theta/2) p); all three "
         "diagonal-in-n factors commute. A local qubit coupled to the mode is parity-mapped by "
         "V = H . CR(pi) . H = exp(-i pi n X/2) (exact for every n: I, -iX, -I, iX on n = 0,1,2,3), so "
         "V|0,n> = c_n |n mod 2, n> with the ancilla's Z eigenvalue equal to p. CR(-2theta) . rz(3theta) then "
         "realises exp(-i(3theta/2 - theta n) p) on the mapped register; V^+ unmaps it, the c_n phases cancel "
         "against their conjugates, and the ancilla returns exactly to |0> for every n. R(3theta) supplies the "
         "remaining 3n term and a dropped global phase completes exp(-i theta n^2). Exact only on n <= 3; beyond "
         "that the construction still realises a well-defined but different diagonal unitary.",
    source="Liu et al. 2407.10381 parity/ancilla-mapping constructions; piecewise-linear fit on bounded photon "
           "number is a from-scratch algebraic identity for this card",
)
