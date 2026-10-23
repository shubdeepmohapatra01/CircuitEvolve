"""P1 hand-written rule 3 (no LLM), deliberately WRONG: merge conditional displacements across an unconditional
one, dropping the phase. Admission must REJECT it by verification (if it fires)."""
from v3.api import Rule
from v3.api import cvdv


def find_matches(c):
    """(i, j, k): CD(a) on (q, m), then D(b) on m, then CD(g) on (q, m), nothing else on q or m in between."""
    ops = c["ops"]
    out = []
    for i, op in enumerate(ops):
        if op.get("name") != "CD":
            continue
        q, m = cvdv.wires(op)
        j = cvdv.next_on_wire(ops, i, m)
        if j is None or ops[j].get("name") != "D" or cvdv.wires(ops[j]) != (m,):
            continue
        k = cvdv.next_on_wire(ops, j, m)
        if k is None or ops[k].get("name") != "CD" or cvdv.wires(ops[k]) != (q, m):
            continue
        if cvdv.next_on_wire(ops, i, q) != k:
            continue
        out.append((i, j, k))
    return out


def apply_match(c, mt):
    i, j, k = mt
    ops = list(c["ops"])
    a, g = cvdv.param(ops[i]), cvdv.param(ops[k])
    merged = cvdv.gate("CD", [a + g], cvdv.wires(ops[i]))
    out = dict(c)
    out["ops"] = ops[:i] + ops[i + 1:j] + [ops[j]] + ops[j + 1:k] + [merged] + ops[k + 1:]
    return out


RULE = Rule(
    name="cond_displacement_merge_wrong",
    domain="cvdv",
    kind="rewrite",
    contract="exact",
    source="P1 deliberately wrong control (hand-written)",
    idea="WRONG on purpose: claims CD(g) D(b) CD(a) = CD(a + g) D(b) (operator order; time order CD(a), D(b), "
         "CD(g) -> D(b), CD(a + g)). With D(x) D(y) = exp(i Im(x y*)) D(x + y), on qubit branch z = +-1 the two "
         "sides differ by exp(2 i z Im(b a*)): a RELATIVE phase between the qubit branches (an Rz on the qubit), "
         "not a global phase. Dropping it is wrong whenever Im(b a*) != 0.",
    trigger=find_matches,
    apply=apply_match,
)
