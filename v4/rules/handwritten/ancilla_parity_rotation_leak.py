"""P5 control 4 (hand-written, no LLM): PLANTED BUG - the same rewrite with the ancilla left entangled.

    rz(theta) on q   ->   cx q -> a ;  rz(theta) on a                     (second cx OMITTED)

The phase applied to the data qubit is right, but the ancilla comes out holding a copy of x_q instead of
|0>. The circuit is therefore NOT equivalent to the original on any input superposition, and no amount of
error budget makes it so: the specification contract (CLAUDE.md invariant 2) requires ancillas to return
to |0>.

The verifier must REJECT this, by the ancilla-return check specifically. That matters because the leak is
the exact failure mode our own measurement of BQSKit's PKAC construction found: exact at k = 3 (state
error 2.6e-16, zero leak) but 1/sqrt(2) ancilla population left at k = 4 and ~1.0 at k = 5, because the
temporary-AND uncompute is measurement-based by construction. A verifier that accepted this rule would
accept those too.
"""
from v4.api import Precondition, Rule
from v4.api import dv


def find_matches(c):
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
    ops[i:i + 1] = [("cx", (q, a), None), ("rz", (a,), th)]      # the uncompute cx is missing
    return dv.Circuit(c.n + 1, dv.normalize(ops), dict(c.meta))


RULE = Rule(
    name="ancilla_parity_rotation_leak",
    domain="dv",
    kind="resource",
    error_class="exact",
    resource_class="ancilla",
    precondition=Precondition(families=("dv_angle",), needs=("nonclifford_rz",)),
    source="hand-written P5 planted bug",
    idea="PLANTED BUG: the cx-rz-cx parity identity with the uncompute cx omitted, so the ancilla is "
         "left holding a copy of the data bit. Must be rejected by the ancilla-return check.",
    trigger=find_matches,
    apply=apply_match,
)
