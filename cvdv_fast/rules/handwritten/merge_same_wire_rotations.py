from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath
ADD = {"R": 0, "rz": 0, "rx": 0, "ry": 0, "CR": 0, "D": 0, "CD": 0}


def trigger(ops):
    out = []
    for i, o in enumerate(ops):
        if o.name in ADD:
            j = same_wires_adjacent(ops, i)
            if j is not None and ops[j].name == o.name:
                out.append((i, j))
    return out


def apply(ops, m):
    i, j = m
    a, b = ops[i], ops[j]
    p = complex(a.params[0]) + complex(b.params[0])
    new = [Op(a.name, (p,), a.wires)] if abs(p) > 1e-12 else []
    # D(a)D(b) = e^{(a b* - a* b)/2} D(a+b) ... b acts after a: D(b)D(a) = e^{(b a* - b* a)/2} D(a+b): global phase
    # CD(a)CD(b) same with Z^2 = 1: phase is global. Rotations add exactly.
    return i, j, list(ops[i + 1:j]) + new


RULE = Rule(name="merge_same_wire_rotations", kind="rewrite", contract="exact", stage="both", trigger=trigger,
            apply=apply,
            idea="Two consecutive gates of the same additive family on the same wires merge: R, CR, rx/ry/rz angles "
                 "add; D(a)D(b) = phase * D(a+b); CD(a)CD(b) = phase * CD(a+b) (Z^2 = 1). Ops in between touch other "
                 "wires only.",
            source="Liu et al. 2407.10381 (Heisenberg-Weyl group law for displacements); textbook rotation merging")
