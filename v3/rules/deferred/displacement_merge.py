"""P1 hand-written rule 2 (no LLM): merge two adjacent displacements on the same qumode."""
from v3.api import Rule
from v3.api import cvdv


def find_matches(c):
    """(i, j): ops i and j are both D on the same single qumode, with nothing on that wire in between."""
    ops = c["ops"]
    out = []
    for i, op in enumerate(ops):
        if op.get("name") != "D":
            continue
        (w,) = cvdv.wires(op)
        j = cvdv.next_on_wire(ops, i, w)
        if j is not None and ops[j].get("name") == "D" and cvdv.wires(ops[j]) == (w,):
            out.append((i, j))
    return out


def apply_match(c, m):
    i, j = m
    a, b = cvdv.param(c["ops"][i]), cvdv.param(c["ops"][j])
    ops = list(c["ops"])
    merged = cvdv.gate("D", [a + b], cvdv.wires(ops[i]))
    rest = ops[i + 1:j]
    out = dict(c)
    out["ops"] = ops[:i] + rest + [merged] + ops[j + 1:]
    return out


RULE = Rule(
    name="displacement_merge",
    domain="cvdv",
    kind="rewrite",
    contract="exact",
    source="textbook (Weyl relation of displacement operators)",
    idea="D(b) D(a) = exp((b a* - b* a)/2) D(a + b) with D(x) = exp(x a^dag - x* a): the prefactor is a scalar "
         "phase (a c-number, since [a, a^dag] = 1), i.e. a GLOBAL phase when both displacements are unconditional. "
         "Two adjacent D on the same qumode become one D(a + b). Exact up to global phase.",
    trigger=find_matches,
    apply=apply_match,
)
