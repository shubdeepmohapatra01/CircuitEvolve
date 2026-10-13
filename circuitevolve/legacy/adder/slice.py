"""Bit-slice program representation for ripple-style adders.

A SliceProgram is three gate templates over symbolic wire roles:

    for i in 0..n-1:      apply fwd  at bit i
    once, at bit n-1:     apply top
    for i in n-1..0:      apply bwd  at bit i

Roles at bit i:
    a, b   a_i, b_i                         (data registers)
    pa     a_{i-1}; at i = 0 a clean ancilla c0
    pc     carry wire of bit i-1 (k_i); at i = 0 the same ancilla c0
    cout   carry wire k_{i+1} (a clean ancilla, allocated only if some template uses it)
    z      carry-out qubit

Template entries are (gate, roles, cond, label): `label` names the classical bit written by a
`measure`; `cond` refers to a label measured earlier in the same template instance. Because the
templates are uniform in i, a program is a construct(n) for every n, and T-count is affine in n.
"""
from __future__ import annotations

from dataclasses import dataclass

from circuitevolve.ir import Circuit, Gate

ROLES = ("a", "b", "pa", "pc", "cout", "z")


@dataclass(frozen=True)
class SliceProgram:
    fwd: tuple
    top: tuple
    bwd: tuple

    def templates(self):
        return {"fwd": self.fwd, "top": self.top, "bwd": self.bwd}

    def size(self) -> int:
        return len(self.fwd) + len(self.top) + len(self.bwd)


def G(name, *roles, cond=None, label=None):
    return (name, tuple(roles), cond, label)


def build(prog: SliceProgram, n: int) -> Circuit:
    used = {r for t in (prog.fwd, prog.top, prog.bwd) for g in t for r in g[1]}
    a = list(range(n))
    b = list(range(n, 2 * n))
    z = 2 * n
    nq = 2 * n + 1
    c0 = None
    if "pa" in used or "pc" in used:
        c0, nq = nq, nq + 1
    k = {}
    if "cout" in used or "pc" in used:
        for j in range(1, n + 1):
            k[j], nq = nq, nq + 1
    circ = Circuit(nq, registers={"a": a, "b": b, "z": [z]})

    def wires(i):
        return {"a": a[i], "b": b[i], "z": z,
                "pa": a[i - 1] if i > 0 else c0,
                "pc": k.get(i) if i > 0 else c0,
                "cout": k.get(i + 1)}

    def apply(template, i):
        w = wires(i)
        labels = {}
        for name, roles, cond, label in template:
            qs = tuple(w[r] for r in roles)
            if any(q is None for q in qs):
                raise ValueError(f"role unavailable in {name}{roles}")
            if name == "measure":
                labels[label] = circ.measure(qs[0])
                continue
            if cond is not None and cond not in labels:
                raise ValueError(f"condition {cond!r} not measured earlier in template")
            circ.gates.append(Gate(name, qs, None, labels[cond] if cond is not None else None))

    for i in range(n):
        apply(prog.fwd, i)
    apply(prog.top, n - 1)
    for i in reversed(range(n)):
        apply(prog.bwd, i)
    return circ


def to_source(prog: SliceProgram) -> str:
    """Readable form (also the format an LLM proposer will edit in P4)."""
    def fmt(t):
        rows = []
        for name, roles, cond, label in t:
            extra = (f", cond={cond!r}" if cond else "") + (f", label={label!r}" if label else "")
            rows.append(f"    G({name!r}, {', '.join(repr(r) for r in roles)}{extra}),")
        return "\n".join(rows)
    return (f"FWD = (\n{fmt(prog.fwd)}\n)\nTOP = (\n{fmt(prog.top)}\n)\nBWD = (\n{fmt(prog.bwd)}\n)\n")


# Seeds and references expressed in this representation -----------------------------------------
CUCCARO = SliceProgram(
    fwd=(G("cx", "a", "b"), G("cx", "a", "pa"), G("ccx", "pa", "b", "a")),
    top=(G("cx", "a", "z"),),
    bwd=(G("ccx", "pa", "b", "a"), G("cx", "a", "pa"), G("cx", "pa", "b")),
)

# Gidney's carry structure but with Toffolis in place of the temporary-AND gadgets (14n).
TOFFOLI_CARRY = SliceProgram(
    fwd=(G("cx", "pc", "a"), G("cx", "pc", "b"), G("ccx", "a", "b", "cout"), G("cx", "pc", "cout")),
    top=(G("cx", "cout", "z"),),
    bwd=(G("cx", "pc", "cout"), G("ccx", "a", "b", "cout"), G("cx", "pc", "a"), G("cx", "a", "b")),
)

GIDNEY_A = SliceProgram(
    fwd=(G("cx", "pc", "a"), G("cx", "pc", "b"), G("and_compute", "a", "b", "cout"), G("cx", "pc", "cout")),
    top=(G("cx", "cout", "z"),),
    bwd=(G("cx", "pc", "cout"), G("and_uncompute", "a", "b", "cout"), G("cx", "pc", "a"), G("cx", "a", "b")),
)

_AND = [("h", 2), ("t", 2), ("cx", 0, 2), ("cx", 1, 2), ("cx", 2, 0), ("cx", 2, 1), ("tdg", 0),
        ("tdg", 1), ("t", 2), ("cx", 2, 0), ("cx", 2, 1), ("h", 2), ("s", 2)]
_R = ("a", "b", "cout")
GIDNEY_B = SliceProgram(
    fwd=(G("cx", "pc", "a"), G("cx", "pc", "b"), *[G(g, *(_R[i] for i in loc)) for g, *loc in _AND],
         G("cx", "pc", "cout")),
    top=(G("cx", "cout", "z"),),
    bwd=(G("cx", "pc", "cout"), G("h", "cout"), G("measure", "cout", label="m"), G("cz", "a", "b", cond="m"),
         G("x", "cout", cond="m"), G("cx", "pc", "a"), G("cx", "a", "b")),
)
