"""P5 control 3 (hand-written, no LLM): CORRECT, and unverifiable before P5.

    rz(theta) on q   ==   cx q -> a ;  rz(theta) on a ;  cx q -> a        (a a clean ancilla)

because cx takes |x_q, 0> to |x_q, x_q>, the rotation then applies e^{-i theta/2 (-1)^{x_q}}, and the
second cx returns the ancilla to |0>. Exact up to nothing at all - it is the same operator - with a
clean ancilla |0> -> |0> and a CONTINUOUS angle.

That combination is exactly what `circuitevolve/v2/verify.py::relaxed` cannot express: it routes through
`_norm_angle_gates`, which raises `NotExact` for any angle off the pi/4 grid. Eight of v3's rejected
rules died on that one message, including both phase-gradient cards. So this rule is the positive control
for the P5 change: the verifier must now VERIFY it. It does not lower the T-count (same rotations, two
more CX, one more qubit), so admission still rejects it on improvement - which is the right answer, and
a different answer from "cannot be checked".

tags: error_class='exact' (it is the identity), resource_class='ancilla' (clean ancilla, no measurement).
"""
from v4.api import Precondition, Rule
from v4.api import dv


def find_matches(c):
    """The first off-grid rotation on a wire, at most one match: this is a control, not an optimiser."""
    if not dv.is_angle_circuit(c):
        return []
    for i, op in enumerate(c.ops):
        th = dv.rotation(op)
        if th is not None and not dv.on_grid(th):
            return [(i, op[1][0], float(th))]
    return []


def apply_match(c, m):
    i, q, th = m
    a = c.n
    ops = list(c.ops)
    ops[i:i + 1] = [("cx", (q, a), None), ("rz", (a,), th), ("cx", (q, a), None)]
    return dv.Circuit(c.n + 1, dv.normalize(ops), dict(c.meta))


RULE = Rule(
    name="ancilla_parity_rotation_lowering",
    domain="dv",
    kind="resource",
    error_class="exact",
    resource_class="ancilla",
    precondition=Precondition(families=("dv_angle",), needs=("nonclifford_rz",),
        note="moves one off-grid rotation onto a clean ancilla"),
    source="hand-written P5 control (the cx-rz-cx parity identity)",
    idea="rz(theta) on q = cx q,a ; rz(theta) on a ; cx q,a for a clean ancilla a. Exact, continuous "
         "angle, ancilla returned to |0>. The positive control for the branch_kraus verifier change.",
    trigger=find_matches,
    apply=apply_match,
)
