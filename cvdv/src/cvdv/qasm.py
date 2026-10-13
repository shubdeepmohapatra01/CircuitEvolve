"""CVDV-QASM reader/writer (the format Genesis emits).

An instruction is `Op(name, params, wires)` with wires as ('q', i) qubits and ('qm', j) qumodes in
operand order.  `pauli(c) STRING` lines (logical circuits) become Op('pauli', (c,), qubit wires)
with the string kept in `label`.  Parameters are parsed with a literal-only evaluator (numbers,
complex literals, `pi`, + - * /), never `eval`.
"""
from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field

Wire = tuple  # ('q', i) | ('qm', j)


@dataclass(frozen=True)
class Op:
    name: str
    params: tuple = ()
    wires: tuple = ()
    label: str = ""  # Pauli string for name == 'pauli'

    @property
    def qubits(self):
        return tuple(w for w in self.wires if w[0] == "q")

    @property
    def qumodes(self):
        return tuple(w for w in self.wires if w[0] == "qm")


@dataclass
class Circuit:
    ops: list = field(default_factory=list)
    n_q: int = 0  # register sizes from `qreg` (0 if absent)
    n_qm: int = 0

    def wires(self):
        s = set()
        for o in self.ops:
            s.update(o.wires)
        return sorted(s)


_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Add, ast.Sub,
            ast.Mult, ast.Div, ast.USub, ast.UAdd, ast.Pow, ast.Load)


def parse_number(s: str) -> complex:
    s = s.strip()
    tree = ast.parse(s, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"disallowed token in parameter {s!r}")
        if isinstance(node, ast.Name) and node.id != "pi":
            raise ValueError(f"unknown name {node.id!r} in parameter {s!r}")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            return complex(n.value)
        if isinstance(n, ast.Name):
            return complex(math.pi)
        if isinstance(n, ast.UnaryOp):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        a, b = ev(n.left), ev(n.right)
        if isinstance(n.op, ast.Add):
            return a + b
        if isinstance(n.op, ast.Sub):
            return a - b
        if isinstance(n.op, ast.Mult):
            return a * b
        if isinstance(n.op, ast.Div):
            return a / b
        return a ** b

    return ev(tree)


_WIRE = re.compile(r"(qm|q)\[(\d+)\]")


def parse_line(line: str):
    line = line.split("//", 1)[0].split("#", 1)[0].strip().rstrip(";").strip()
    if not line or line.startswith("CVDVQASM") or line.startswith("include"):
        return None
    if line.startswith("qreg"):
        return ("qreg", [(k, int(n)) for k, n in _WIRE.findall(line)])
    m = re.match(r"pauli\((.*)\):?\s*([IXYZ]+)$", line)
    if m:
        c = parse_number(m.group(1))
        s = m.group(2)
        wires = tuple(("q", i) for i, ch in enumerate(s) if ch != "I")
        return Op("pauli", (c,), wires, s)
    m = re.match(r"([A-Za-z_]+)\s*(\((.*?)\))?\s*(.*)$", line)
    if not m:
        raise ValueError(f"cannot parse {line!r}")
    name, _, ptxt, rest = m.groups()
    params = tuple(parse_number(p) for p in ptxt.split(",")) if ptxt else ()
    wires = tuple((k, int(n)) for k, n in _WIRE.findall(rest))
    return Op(name, params, wires)


def read(path) -> Circuit:
    c = Circuit()
    with open(path) as f:
        for raw in f:
            r = parse_line(raw)
            if r is None:
                continue
            if isinstance(r, tuple) and r[0] == "qreg":
                for k, n in r[1]:
                    if k == "q":
                        c.n_q = n
                    else:
                        c.n_qm = n
                continue
            c.ops.append(r)
    return c


def _fmt(p: complex) -> str:
    p = complex(p)
    if abs(p.imag) < 1e-15:
        return repr(p.real)
    return repr(p).strip("()")


def format_op(o: Op) -> str:
    if o.name == "pauli":
        return f"pauli({_fmt(o.params[0])}) {o.label};"
    head = o.name + (f"({', '.join(_fmt(p) for p in o.params)})" if o.params else "")
    qs = [f"q[{w[1]}]" for w in o.wires if w[0] == "q"]
    ms = [f"qm[{w[1]}]" for w in o.wires if w[0] == "qm"]
    return f"{head} {', '.join(qs + ms)};"


def write(c: Circuit, path):
    with open(path, "w") as f:
        f.write("CVDVQASM 1.0;\n")
        if c.n_q or c.n_qm:
            f.write(f"qreg q[{c.n_q}] qm[{c.n_qm}];\n")
        for o in c.ops:
            f.write(format_op(o) + "\n")
