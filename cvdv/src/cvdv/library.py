"""Rule libraries: the object the LLM mutator edits.

A library is Python source containing only literal constants and functions named
`rule_<kind>__<name>(t, g, r)`.  A rule emits gates for one classified term `t` through the gate
builder `g`; `r >= 1` is a repetition/precision knob the compiler may raise (exact rules ignore it).
The compiler trusts nothing a rule claims: every emitted instance is certified (certify.py).

Static rules (checked before exec): no imports, no dunder names, no attribute access except on
`g`, `t`, `m` (math namespace); no while loops; builtins limited to SAFE_BUILTINS.  The library
runs with restricted globals.  `t` exposes: kind, theta, phi, alpha, label, q (qubit wires),
m (qumode wires).  `g` exposes the ISA gates plus anc_qubit() / anc_mode().
"""
from __future__ import annotations

import ast
import cmath
import math
from types import SimpleNamespace

from .qasm import Op

SAFE_BUILTINS = {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k)
                 for k in ("range", "len", "abs", "min", "max", "float", "int", "complex", "round",
                           "enumerate", "zip", "list", "tuple", "sum", "reversed", "ValueError")}
MATH = SimpleNamespace(pi=math.pi, sqrt=math.sqrt, sin=math.sin, cos=math.cos, tan=math.tan,
                       atan2=math.atan2, exp=math.exp, log=math.log, acos=math.acos,
                       asin=math.asin, cexp=cmath.exp, phase=cmath.phase, conj=lambda z: complex(z).conjugate(),
                       floor=math.floor, ceil=math.ceil)
ALLOWED_ATTR_BASES = {"g", "t", "m"}


class LibraryError(Exception):
    pass


def static_check(src: str):
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # docstring
        if isinstance(node, ast.Assign) and all(isinstance(n, ast.Name) for n in node.targets) \
                and isinstance(node.value, (ast.Constant, ast.Tuple, ast.List, ast.Dict)):
            continue
        if isinstance(node, ast.FunctionDef) and node.name.startswith("rule_") and "__" in node.name[5:]:
            if [a.arg for a in node.args.args] != ["t", "g", "r"] or node.decorator_list:
                raise LibraryError(f"{node.name}: signature must be (t, g, r), no decorators")
            continue
        raise LibraryError(f"line {node.lineno}: only constants and rule_<kind>__<name> functions allowed")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.While, ast.Global, ast.Nonlocal,
                             ast.Lambda, ast.ClassDef, ast.AsyncFunctionDef, ast.Try, ast.With)):
            raise LibraryError(f"line {getattr(node, 'lineno', '?')}: {type(node).__name__} not allowed")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise LibraryError(f"line {node.lineno}: dunder name")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                raise LibraryError(f"line {node.lineno}: private attribute {node.attr}")
            if not (isinstance(node.value, ast.Name) and node.value.id in ALLOWED_ATTR_BASES):
                raise LibraryError(f"line {node.lineno}: attribute access only on g, t, m")
    return tree


def load(src: str) -> dict:
    """Return {kind: [(name, fn), ...]} in source order."""
    static_check(src)
    env = {"__builtins__": SAFE_BUILTINS, "m": MATH}
    exec(compile(src, "<rule-library>", "exec"), env)
    rules = {}
    for k, v in env.items():
        if k.startswith("rule_") and callable(v):
            kind, name = k[5:].split("__", 1)
            rules.setdefault(kind, []).append((name, v))
    return rules


class TermView:
    def __init__(self, tc):
        self.kind = tc.kind
        self.label = tc.label
        self.q = [w for w in tc.wires if w[0] == "q"]
        self.m = [w for w in tc.wires if w[0] == "qm"]
        p = tc.params
        self.theta = float(complex(p[0]).real) if tc.kind not in ("disp", "pauli_disp") else None
        self.phi = float(p[1]) if len(p) > 1 else 0.0
        self.alpha = complex(p[0]) if tc.kind in ("disp", "pauli_disp") else None


class Builder:
    """Gate builder handed to rules.  Ancillas: qubit co-located with a qumode site / qumode
    co-located with a qubit site, numbered above the system registers."""
    MAX_OPS = 200000

    def __init__(self, anc_q_base: int, anc_m_base: int):
        self.ops = []
        self.anc_q_base = anc_q_base
        self.anc_m_base = anc_m_base
        self._site_m = 0
        self._site_q = 0
        self.fresh_base = max(anc_q_base, anc_m_base)

    def _add(self, name, params, *wires):
        if len(self.ops) >= self.MAX_OPS:
            raise LibraryError("op budget exceeded")
        for w in wires:
            if not (isinstance(w, tuple) and len(w) == 2 and w[0] in ("q", "qm") and isinstance(w[1], int)):
                raise LibraryError(f"bad wire {w!r}")
        self.ops.append(Op(name, tuple(complex(p) for p in params), tuple(wires)))

    # ancillas
    def anc_qubit(self, k: int = 0):
        """k-th ancilla qubit for the term's first qumode site: the site's own qubit when it is not
        a system qubit (k = 0), otherwise a fresh index above every system register."""
        if k == 0 and self._site_m >= self.anc_q_base:
            return ("q", self._site_m)
        return ("q", self.fresh_base + 4 * self._site_m + k)

    def anc_mode(self, k: int = 0):
        """k-th ancilla qumode for the term's first qubit site (same policy as anc_qubit)."""
        if k == 0 and self._site_q >= self.anc_m_base:
            return ("qm", self._site_q)
        return ("qm", self.fresh_base + 4 * self._site_q + k)

    # qubit gates
    def h(self, q): self._add("h", (), q)
    def x(self, q): self._add("x", (), q)
    def y(self, q): self._add("y", (), q)
    def z(self, q): self._add("z", (), q)
    def s(self, q): self._add("s", (), q)
    def sdg(self, q): self._add("sdg", (), q)
    def t(self, q): self._add("t", (), q)
    def tdg(self, q): self._add("tdg", (), q)
    def rx(self, th, q): self._add("rx", (th,), q)
    def ry(self, th, q): self._add("ry", (th,), q)
    def rz(self, th, q): self._add("rz", (th,), q)
    def r(self, th, ph, q): self._add("r", (th, ph), q)
    # bosonic / hybrid gates (operand order: qubit first, then qumodes)
    def R(self, th, qm): self._add("R", (th,), qm)
    def D(self, al, qm): self._add("D", (al,), qm)
    def BS(self, th, ph, a, b): self._add("BS", (th, ph), a, b)
    def CR(self, th, q, qm): self._add("CR", (th,), q, qm)
    def CP(self, q, qm): self._add("CP", (), q, qm)
    def CD(self, al, q, qm): self._add("CD", (al,), q, qm)
