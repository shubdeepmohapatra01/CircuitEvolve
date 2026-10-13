"""Specification side: the term exponentials of one Trotter step, as Genesis' intermediate file
lists them (`bosonic: exp(...)`, `hybrid: exp(...)`, `pauli(c): STRING`).

Each term becomes `Term(wires, generator)` where `generator` builds the anti-Hermitian exponent G
on padded local dimensions; `unitary(N)` returns expm(G) restricted to N levels per mode.

Expression grammar (Genesis' operator s-expressions):
    prod(x, y, ...)  ordered product     sum(x, y, ...)   sum
    dagger(x)        adjoint             nsign(x)         negation
    b(i)             annihilation on qumode i
    sigma(k, q)      Pauli k in {1,2,3} = X,Y,Z on qubit q
    (c) | c          complex constant, e.g. (-1.5707963j)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm

from .qasm import parse_number
from .sim import PAULI, ann, keep_block, kron

_TOK = re.compile(r"\s*([A-Za-z_][A-Za-z_0-9]*|\(|\)|,|[^(),\s]+)")


def tokenize(s):
    pos, out = 0, []
    while pos < len(s):
        m = _TOK.match(s, pos)
        if not m:
            raise ValueError(f"bad token at {s[pos:]!r}")
        if m.group(1):
            out.append(m.group(1))
        pos = m.end()
    return out


def parse_sexpr(s):
    toks = tokenize(s)
    i = 0

    def expr():
        nonlocal i
        t = toks[i]
        if t == "(":  # parenthesised constant
            depth, j = 0, i
            while True:
                if toks[j] == "(":
                    depth += 1
                elif toks[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            txt = "".join(toks[i + 1:j])
            i = j + 1
            return ("const", parse_number(txt))
        i += 1
        if i < len(toks) and toks[i] == "(" and re.match(r"[A-Za-z_]", t):
            i += 1
            args = []
            while toks[i] != ")":
                args.append(expr())
                if toks[i] == ",":
                    i += 1
            i += 1
            return (t, args)
        try:
            return ("const", parse_number(t))
        except Exception:
            return ("atom", t)

    e = expr()
    assert i == len(toks), f"trailing tokens in {s!r}"
    return e


def _wires(e, acc):
    head, args = e
    if head == "b":
        acc.add(("qm", int(args[0][1].real)))
    elif head == "sigma":
        acc.add(("q", int(args[1][1].real)))
    elif head == "paulistring":
        acc.update(("q", i) for i, ch in enumerate(args[0][1]) if ch != "I")
    elif isinstance(args, list):
        for a in args:
            _wires(a, acc)
    return acc


@dataclass
class Term:
    wires: tuple            # sorted local wires
    expr: object            # parsed exponent (for exp lines) or None
    pauli: tuple = None     # (coef, label) for pauli lines
    text: str = ""

    def generator(self, N: int, pad: int):
        dims = [2 if w[0] == "q" else N + pad for w in self.wires]
        pos = {w: k for k, w in enumerate(self.wires)}

        def embed(local, w):
            mats = [np.eye(d, dtype=complex) for d in dims]
            mats[pos[w]] = local
            return kron(*mats)

        def ev(e):
            head, args = e
            if head == "const":
                return args
            if head == "b":
                w = ("qm", int(args[0][1].real))
                return embed(ann(N + pad), w)
            if head == "sigma":
                k, q = int(args[0][1].real), int(args[1][1].real)
                return embed(PAULI["XYZ"[k - 1]], ("q", q))
            if head == "paulistring":
                out = None
                for i, ch in enumerate(args[0][1]):
                    if ch != "I":
                        m = embed(PAULI[ch], ("q", i))
                        out = m if out is None else out @ m
                return out
            vals = [ev(a) for a in args]
            if head == "dagger":
                v = vals[0]
                return np.conj(v) if np.isscalar(v) else v.conj().T
            if head == "nsign":
                return -vals[0]
            if head == "prod":
                out = 1
                for v in vals:
                    out = out * v if (np.isscalar(out) or np.isscalar(v)) else out @ v
                return out
            if head == "sum":
                out = 0
                for v in vals:
                    out = out + v
                return out
            raise KeyError(f"unknown operator head {head!r}")

        return ev(self.expr), dims

    def unitary(self, N: int, pad: int = 12) -> np.ndarray:
        if self.pauli is not None:
            c, label = self.pauli
            return expm(c * kron(*[PAULI[ch] for ch in label if ch != "I"]))
        G, dims = self.generator(N, pad)
        U = expm(G)
        keep = [2 if w[0] == "q" else N for w in self.wires]
        return keep_block(U, dims, keep)


def read_intermediate(path):
    terms = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            m = re.match(r"pauli\((.*)\):?\s*([IXYZ]+);?$", line)
            if m:
                c, s = parse_number(m.group(1)), m.group(2)
                w = tuple(("q", i) for i, ch in enumerate(s) if ch != "I")
                terms.append(Term(w, None, (c, s), line))
                continue
            m = re.match(r"(bosonic|hybrid):\s*exp\((.*)\);?$", line)
            if not m:
                raise ValueError(f"unrecognised intermediate line {line!r}")
            e = parse_sexpr(m.group(2))
            terms.append(Term(tuple(sorted(_wires(e, set()))), e, None, line))
    return terms
