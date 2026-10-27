"""One circuit format for the whole project. Gate semantics (names, matrices) live HERE and nowhere else.

A Circuit is n qubits + a list of Gates. Qubit 0 is the most significant bit of a basis index.
Gate set:
    1q unitary : h x y z s sdg t tdg sx sxdg rz(theta)      theta in radians
    2q unitary : cx cz swap
    3q unitary : ccx ccz
    non-unitary: measure q -> c       reset q (to |0>)
    any unitary gate may carry cond=c : applied only if classical bit c == 1
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace

import numpy as np

PI = math.pi
_S2 = 1 / math.sqrt(2)
_FIXED = {
    "h": np.array([[1, 1], [1, -1]]) * _S2,
    "x": np.array([[0, 1], [1, 0]]),
    "y": np.array([[0, -1j], [1j, 0]]),
    "z": np.diag([1, -1]),
    "s": np.diag([1, 1j]),
    "sdg": np.diag([1, -1j]),
    "t": np.diag([1, np.exp(1j * PI / 4)]),
    "tdg": np.diag([1, np.exp(-1j * PI / 4)]),
    "sx": np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]]) / 2,
    "sxdg": np.array([[1 - 1j, 1 + 1j], [1 + 1j, 1 - 1j]]) / 2,
    "cx": np.eye(4)[[0, 1, 3, 2]],
    "cz": np.diag([1, 1, 1, -1]),
    "swap": np.eye(4)[[0, 2, 1, 3]],
    "ccx": np.eye(8)[[0, 1, 2, 3, 4, 5, 7, 6]],
    "ccz": np.diag([1, 1, 1, 1, 1, 1, 1, -1]),
}
ARITY = {g: int(round(math.log2(m.shape[0]))) for g, m in _FIXED.items()} | {"rz": 1, "measure": 1, "reset": 1}
UNITARY = set(_FIXED) | {"rz"}


@dataclass(frozen=True)
class Gate:
    name: str
    qubits: tuple
    theta: float | None = None   # rz only
    cbit: int | None = None      # measure: target classical bit
    cond: int | None = None      # classically controlled: apply iff bit `cond` == 1

    def __post_init__(self):
        assert self.name in ARITY, f"unknown gate {self.name}"
        assert len(self.qubits) == ARITY[self.name], f"{self.name} needs {ARITY[self.name]} qubits"
        assert len(set(self.qubits)) == len(self.qubits), f"repeated qubit in {self}"
        assert (self.theta is not None) == (self.name == "rz"), "theta is for rz only"


def matrix(g: Gate) -> np.ndarray:
    """Unitary of a gate on its own qubits (first listed qubit = most significant)."""
    if g.name == "rz":
        return np.diag([np.exp(-0.5j * g.theta), np.exp(0.5j * g.theta)])
    return _FIXED[g.name].astype(complex)


@dataclass
class Circuit:
    n: int
    gates: list = field(default_factory=list)
    nc: int = 0                  # classical bits

    def copy(self) -> "Circuit":
        return Circuit(self.n, list(self.gates), self.nc)

    def is_unitary(self) -> bool:
        return all(g.name in UNITARY and g.cond is None for g in self.gates)

    def __len__(self):
        return len(self.gates)


# ---- counts ------------------------------------------------------------------------------------
def _quarter_turns(theta: float, tol=1e-9):
    """theta / (pi/4) mod 8 if it is an integer within tol, else None."""
    k = theta / (PI / 4)
    return int(round(k)) % 8 if abs(k - round(k)) < tol else None


def is_t_like(g: Gate) -> bool:
    if g.name in ("t", "tdg"):
        return True
    return g.name == "rz" and _quarter_turns(g.theta) in (1, 3, 5, 7)


def is_arbitrary_rz(g: Gate) -> bool:
    return g.name == "rz" and _quarter_turns(g.theta) is None


def counts(c: Circuit) -> dict:
    """Explicit T (incl. rz at odd multiples of pi/4), arbitrary rz, ccx/ccz, cx, qubits, measurements."""
    return dict(
        t=sum(is_t_like(g) for g in c.gates),
        rz=sum(is_arbitrary_rz(g) for g in c.gates),
        toffoli=sum(g.name in ("ccx", "ccz") for g in c.gates),
        cx=sum(g.name == "cx" for g in c.gates),
        qubits=c.n,
        measure=sum(g.name == "measure" for g in c.gates),
        gates=len(c.gates),
    )


# ---- QASM (our gate set only; foreign QASM goes through library.load) --------------------------
def to_qasm(c: Circuit) -> str:
    out = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{c.n}];"]
    if c.nc:
        out.append(f"creg c[{c.nc}];")
    for g in c.gates:
        qs = ",".join(f"q[{q}]" for q in g.qubits)
        if g.name == "measure":
            s = f"measure {qs} -> c[{g.cbit}];"
        elif g.name == "rz":
            s = f"rz({g.theta!r}) {qs};"
        else:
            s = f"{g.name} {qs};"
        out.append(f"if(c[{g.cond}]==1) {s}" if g.cond is not None else s)
    return "\n".join(out) + "\n"


_ALIAS = {"u1": "rz", "p": "rz", "cnot": "cx", "toffoli": "ccx", "tdag": "tdg", "sdag": "sdg"}


def _angle(expr: str) -> float:
    expr = expr.replace("pi", "PI")
    if not re.fullmatch(r"[0-9eE.+\-*/() PI]+", expr):
        raise ValueError(f"bad angle {expr!r}")
    return float(eval(expr, {"__builtins__": {}}, {"PI": PI}))


def from_qasm(text: str) -> Circuit:
    """Parse OPENQASM 2 in our gate set (also accepts pyzx/tket output: u1/p as rz, angles with pi).
    rz/u1/p differ only by a global phase, which the verifier ignores. Several named qreg/creg are
    concatenated in declaration order (e.g. qreg eval[3]; qreg q[3]; -> eval = 0..2, q = 3..5)."""
    qoff, coff, n, nc, gates = {}, {}, 0, 0, []
    for name in re.findall(r"gate\s+(\w+)[^{]*\{[^}]*\}", text):      # definitions of our own native gates
        if name not in ARITY:
            raise ValueError(f"custom gate {name!r} is not in the gate set")
    text = re.sub(r"gate\s+\w+[^{]*\{[^}]*\}", "", text)
    ref = re.compile(r"(\w+)\[(\d+)\]")
    for raw in re.sub(r"//.*", "", text).split(";"):
        line = " ".join(raw.split())
        if not line or line.startswith(("OPENQASM", "include", "barrier")):
            continue
        if line.startswith(("qreg", "creg")):
            name, size = ref.search(line).groups()
            if line.startswith("qreg"):
                qoff[name], n = n, n + int(size)
            else:
                coff[name], nc = nc, nc + int(size)
            continue
        m = re.match(r"^(?:if\((\w+)\[(\d+)\]==1\)\s*)?(\w+)(?:\(([^)]*)\))?\s+(.+?)(?:\s*->\s*(\w+)\[(\d+)\])?$", line)
        if not m:
            raise ValueError(f"cannot parse: {line!r}")
        creg, cidx, name, arg, qs, mreg, midx = m.groups()
        name = _ALIAS.get(name.lower(), name.lower())
        qubits = tuple(qoff[r] + int(i) for r, i in ref.findall(qs))
        gates.append(Gate(name, qubits, theta=_angle(arg) if name == "rz" else None,
                          cbit=coff[mreg] + int(midx) if mreg else None,
                          cond=coff[creg] + int(cidx) if creg else None))
    return Circuit(n, gates, nc)


def load(path: str) -> Circuit:
    with open(path) as f:
        return from_qasm(f.read())


def save(c: Circuit, path: str) -> None:
    with open(path, "w") as f:
        f.write(to_qasm(c))


def remap(c: Circuit, n: int, qmap: dict) -> Circuit:
    """Embed c into an n-qubit circuit, sending qubit i to qmap[i]."""
    return Circuit(n, [replace(g, qubits=tuple(qmap[q] for q in g.qubits)) for g in c.gates], c.nc)
