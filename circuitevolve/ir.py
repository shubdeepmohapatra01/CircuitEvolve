"""Circuit intermediate representation.

A Circuit is a list of Gates over `n_qubits` qubits and `n_cbits` classical bits, plus named
registers. Gates may be classically controlled (`cond=c`: applied iff classical bit c is 1).

Gate vocabulary
---------------
primitives : x z h s sdg t tdg cx cz measure
native     : ccx ccz                      (exact Toffoli / CCZ; cost = their 7-T expansion)
gadgets    : and_compute(a, b, t)         (Gidney temporary AND; requires t = |0>; 4 T)
             and_uncompute(a, b, t)       (measurement-based uncompute; requires t = a·b; 0 T)

`expand("gadgets")` rewrites gadgets into primitives; `expand("clifford_t")` additionally rewrites
ccx/ccz, giving a circuit over primitives only (the form that is costed and exported).
"""
from __future__ import annotations

from dataclasses import dataclass, field

ONE_QUBIT = {"x", "z", "h", "s", "sdg", "t", "tdg"}
TWO_QUBIT = {"cx", "cz"}
NATIVE = {"ccx", "ccz"}
GADGETS = {"and_compute", "and_uncompute"}
PRIMITIVES = ONE_QUBIT | TWO_QUBIT | {"measure"}
ARITY = {**{g: 1 for g in ONE_QUBIT}, **{g: 2 for g in TWO_QUBIT}, "measure": 1,
         "ccx": 3, "ccz": 3, "and_compute": 3, "and_uncompute": 3}

# Gate vocabularies for the two IR tiers of the experiment (docs/TEST_PLAN.md, section 2).
TIER_A = {"x", "cx", "ccx", "and_compute", "and_uncompute"}
TIER_B = ONE_QUBIT | TWO_QUBIT | {"measure", "ccx"}


@dataclass(frozen=True)
class Gate:
    name: str
    qubits: tuple
    cbit: int | None = None   # measure: classical bit written
    cond: int | None = None   # classical control: apply iff cbits[cond] == 1


# Expansions over local qubit indices (0, 1, 2) = (control a, control b, target t). -------------
_CCX = [("h", 2), ("cx", 1, 2), ("tdg", 2), ("cx", 0, 2), ("t", 2), ("cx", 1, 2), ("tdg", 2),
        ("cx", 0, 2), ("t", 1), ("t", 2), ("h", 2), ("cx", 0, 1), ("t", 0), ("tdg", 1), ("cx", 0, 1)]
_CCZ = [g for g in _CCX if not (g[0] == "h" and g[1] == 2)]
# Temporary logical AND (Gidney 2018, Fig. 3): t must start in |0>; 4 T gates.
_AND_COMPUTE = [("h", 2), ("t", 2), ("cx", 0, 2), ("cx", 1, 2), ("cx", 2, 0), ("cx", 2, 1),
                ("tdg", 0), ("tdg", 1), ("t", 2), ("cx", 2, 0), ("cx", 2, 1), ("h", 2), ("s", 2)]


@dataclass
class Circuit:
    n_qubits: int
    n_cbits: int = 0
    gates: list = field(default_factory=list)
    registers: dict = field(default_factory=dict)

    # building -------------------------------------------------------------------------------
    def add(self, name: str, *qubits: int, cond: int | None = None) -> "Circuit":
        if name == "measure":
            raise ValueError("use Circuit.measure(q)")
        self.gates.append(Gate(name, tuple(qubits), None, cond))
        return self

    def measure(self, q: int) -> int:
        c = self.n_cbits
        self.n_cbits += 1
        self.gates.append(Gate("measure", (q,), c, None))
        return c

    def new_qubit(self) -> int:
        self.n_qubits += 1
        return self.n_qubits - 1

    def copy(self) -> "Circuit":
        return Circuit(self.n_qubits, self.n_cbits, list(self.gates),
                       {k: list(v) for k, v in self.registers.items()})

    def ancillas(self) -> list:
        used = {q for reg in self.registers.values() for q in reg}
        return [q for q in range(self.n_qubits) if q not in used]

    # expansion ------------------------------------------------------------------------------
    def expand(self, level: str = "clifford_t") -> "Circuit":
        if level not in {"gadgets", "clifford_t"}:
            raise ValueError(level)
        out = Circuit(self.n_qubits, self.n_cbits, [], {k: list(v) for k, v in self.registers.items()})
        for g in self.gates:
            if g.name == "and_compute":
                _emit(out, _AND_COMPUTE, g.qubits, g.cond, level)
            elif g.name == "and_uncompute":
                a, b, t = g.qubits
                out.gates.append(Gate("h", (t,), None, g.cond))
                c = out.n_cbits
                out.n_cbits += 1
                if g.cond is not None:
                    raise ValueError("conditional and_uncompute is not supported")
                out.gates.append(Gate("measure", (t,), c, None))
                out.gates.append(Gate("cz", (a, b), None, c))
                out.gates.append(Gate("x", (t,), None, c))
            elif g.name in NATIVE and level == "clifford_t":
                _emit(out, _CCX if g.name == "ccx" else _CCZ, g.qubits, g.cond, level)
            else:
                # source cbits keep their indices: gadget expansion only appends cbits
                # beyond src.n_cbits, so no renumbering is needed
                out.gates.append(g)
        return out

    def __len__(self):
        return len(self.gates)

    def count(self) -> dict:
        d: dict = {}
        for g in self.gates:
            d[g.name] = d.get(g.name, 0) + 1
        return d


def _emit(out: Circuit, template, qubits, cond, level):
    for name, *loc in template:
        out.gates.append(Gate(name, tuple(qubits[i] for i in loc), None, cond))


def to_qasm3(circ: Circuit) -> str:
    """OpenQASM 3 export of the gadget-expanded circuit (ccx/ccz kept as stdgates)."""
    c = circ.expand("gadgets")
    lines = ["OPENQASM 3.0;", 'include "stdgates.inc";', f"qubit[{c.n_qubits}] q;"]
    if c.n_cbits:
        lines.append(f"bit[{c.n_cbits}] c;")
    for name, regs in c.registers.items():
        lines.append(f"// register {name}: " + " ".join(f"q[{i}]" for i in regs))
    for g in c.gates:
        args = ", ".join(f"q[{i}]" for i in g.qubits)
        if g.name == "measure":
            stmt = f"c[{g.cbit}] = measure {args};"
        else:
            stmt = f"{g.name} {args};"
        if g.cond is not None:
            stmt = f"if (c[{g.cond}]) {{ {stmt} }}"
        lines.append(stmt)
    return "\n".join(lines) + "\n"
