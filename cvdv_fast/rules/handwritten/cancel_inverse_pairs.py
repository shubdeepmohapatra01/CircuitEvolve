from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath
INV = {("h", "h"), ("x", "x"), ("y", "y"), ("z", "z"), ("s", "sdg"), ("sdg", "s"), ("t", "tdg"), ("tdg", "t")}


def _is_cp_inv(a, b):
    def is_cp(o):
        return o.name == "CP" or (o.name == "CR" and abs(complex(o.params[0]) - math.pi) < 1e-12)

    def is_cpd(o):
        return o.name == "CR" and abs(complex(o.params[0]) + math.pi) < 1e-12
    return (is_cp(a) and is_cpd(b)) or (is_cpd(a) and is_cp(b))


def trigger(ops):
    out = []
    for i, o in enumerate(ops):
        j = same_wires_adjacent(ops, i)
        if j is None:
            continue
        if (o.name, ops[j].name) in INV or _is_cp_inv(o, ops[j]):
            out.append((i, j))
    return out


def apply(ops, m):
    i, j = m
    return i, j, list(ops[i + 1:j])


RULE = Rule(name="cancel_inverse_pairs", kind="rewrite", contract="exact", stage="both", trigger=trigger, apply=apply,
            idea="Adjacent inverse pairs on the same wires cancel: HH, XX, YY, ZZ, S Sdg, T Tdg, CP CR(-pi).",
            source="textbook gate cancellation (Genesis gate_cancel_rules extended with CP/CR(-pi))")
