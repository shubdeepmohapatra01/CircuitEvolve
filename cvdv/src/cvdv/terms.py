"""Exact operator algebra for Trotter terms and their classification.

A term is exp(G) with G anti-Hermitian; we store H = i·G (Hermitian) as a polynomial

    H = Σ c_k · P_k ⊗ Π_m (a_m†)^{p_m} a_m^{q_m}          (normal-ordered per mode)

key = (pauli: tuple of (qubit, 'X'|'Y'|'Z') sorted, boson: tuple of (mode, p, q) sorted).
Multiplication is exact: Pauli products with phases, and per-mode normal ordering
    a†^p a^q · a†^r a^s = Σ_k C(q,k) C(r,k) k! a†^{p+r-k} a^{q+s-k}.
Coefficients are Python complex numbers (the Genesis IR carries decimal floats).

`classify(H)` maps H to a TermClass used by the rule library, e.g.
    ('n',      modes=(m,),    θ)          H = θ n_m
    ('n2',     (m,),          θ)          H = θ n_m^2   (plus any linear part split off)
    ('hop',    (j,k),         θ, φ)       H = θ (e^{iφ} a_j† a_k + h.c.)
    ('z_n',    q, (m,),       θ)          H = θ Z_q n_m
    ('z_hop',  q, (j,k),      θ, φ)       H = θ Z_q (e^{iφ} a_j† a_k + h.c.)
    ('pauli',  label,         θ)          H = θ P   (multi-qubit Pauli string)
    ('pauli_disp', label, (m,), α)        H = P ⊗ i(α a† - α* a)  i.e. exp(-iH) = exp(P(α a† - α* a))
    ('disp',   (m,),          α)
    ('sum',    parts)                     several commuting classes (e.g. n2 + n): synthesized in sequence
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from .target import parse_sexpr

TOL = 1e-12

_PMUL = {  # (a, b) -> (phase, c) with a·b = phase·c
    ("X", "X"): (1, None), ("Y", "Y"): (1, None), ("Z", "Z"): (1, None),
    ("X", "Y"): (1j, "Z"), ("Y", "X"): (-1j, "Z"), ("Y", "Z"): (1j, "X"),
    ("Z", "Y"): (-1j, "X"), ("Z", "X"): (1j, "Y"), ("X", "Z"): (-1j, "Y"),
}


def _pauli_mul(p1, p2):
    d = dict(p1)
    phase = 1
    for q, s in p2:
        if q in d:
            ph, r = _PMUL[(d[q], s)]
            phase *= ph
            if r is None:
                del d[q]
            else:
                d[q] = r
        else:
            d[q] = s
    return phase, tuple(sorted(d.items()))


def _boson_mul(b1, b2):
    """Product of two multi-mode normal-ordered monomials -> list of (coef, monomial)."""
    m1 = {m: (p, q) for m, p, q in b1}
    m2 = {m: (p, q) for m, p, q in b2}
    modes = sorted(set(m1) | set(m2))
    out = [(1.0, {})]
    for m in modes:
        p, q = m1.get(m, (0, 0))
        r, s = m2.get(m, (0, 0))
        terms = []
        for k in range(min(q, r) + 1):
            c = math.comb(q, k) * math.comb(r, k) * math.factorial(k)
            terms.append((c, (p + r - k, q + s - k)))
        new = []
        for c0, mono in out:
            for c, pq in terms:
                mm = dict(mono)
                if pq != (0, 0):
                    mm[m] = pq
                new.append((c0 * c, mm))
        out = new
    return [(c, tuple(sorted((m, p, q) for m, (p, q) in mono.items()))) for c, mono in out]


@dataclass
class Poly:
    c: dict = field(default_factory=dict)  # (pauli, boson) -> complex

    @staticmethod
    def scalar(z):
        return Poly({((), ()): complex(z)}) if abs(z) > 0 else Poly()

    @staticmethod
    def ann(m):
        return Poly({((), ((m, 0, 1),)): 1.0})

    @staticmethod
    def sig(q, s):
        return Poly({(((q, s),), ()): 1.0})

    def __add__(self, o):
        d = defaultdict(complex, self.c)
        for k, v in o.c.items():
            d[k] += v
        return Poly({k: v for k, v in d.items() if abs(v) > TOL})

    def __neg__(self):
        return Poly({k: -v for k, v in self.c.items()})

    def __sub__(self, o):
        return self + (-o)

    def scale(self, z):
        return Poly({k: v * z for k, v in self.c.items() if abs(v * z) > TOL})

    def __mul__(self, o):
        d = defaultdict(complex)
        for (p1, b1), v1 in self.c.items():
            for (p2, b2), v2 in o.c.items():
                ph, p = _pauli_mul(p1, p2)
                for cb, b in _boson_mul(b1, b2):
                    d[(p, b)] += v1 * v2 * ph * cb
        return Poly({k: v for k, v in d.items() if abs(v) > TOL})

    def dagger(self):
        return Poly({(p, tuple((m, q, pp) for m, pp, q in b)): v.conjugate()
                     for (p, b), v in self.c.items()}).canon()

    def canon(self):
        return Poly({(p, tuple(sorted(b))): v for (p, b), v in self.c.items()})

    def is_hermitian(self, tol=1e-9):
        d = self - self.dagger()
        return all(abs(v) < tol for v in d.c.values())

    def wires(self):
        w = set()
        for p, b in self.c:
            w.update(("q", q) for q, _ in p)
            w.update(("qm", m) for m, _, _ in b)
        return tuple(sorted(w))

    def __repr__(self):
        parts = []
        for (p, b), v in sorted(self.c.items(), key=str):
            ps = "".join(f"{s}{q}" for q, s in p)
            bs = "".join(f"[a†{m}^{pp} a{m}^{q}]" for m, pp, q in b)
            parts.append(f"({v:.6g}){ps}{bs}")
        return " + ".join(parts) or "0"


def from_sexpr(e) -> Poly:
    head, args = e
    if head == "const":
        return Poly.scalar(args)
    if head == "b":
        return Poly.ann(int(args[0][1].real))
    if head == "sigma":
        k, q = int(args[0][1].real), int(args[1][1].real)
        return Poly.sig(q, "XYZ"[k - 1])
    if head == "paulistring":  # paulistring(XXII): qubit i carries letter i
        label = args[0][1]
        return Poly({(tuple((i, ch) for i, ch in enumerate(label) if ch != "I"), ()): 1.0})
    vals = [from_sexpr(a) for a in args]
    if head == "dagger":
        return vals[0].dagger()
    if head == "nsign":
        return -vals[0]
    if head == "prod":
        out = Poly.scalar(1)
        for v in vals:
            out = out * v
        return out
    if head == "sum":
        out = Poly()
        for v in vals:
            out = out + v
        return out
    raise KeyError(head)


def hamiltonian_of(term) -> Poly:
    """H with exp(-iH) = the term's unitary.  `term` is a target.Term."""
    if term.pauli is not None:
        c, label = term.pauli
        P = Poly({(tuple((i, ch) for i, ch in enumerate(label) if ch != "I"), ()): 1.0})
        return P.scale(1j * c)  # exp(cP) = exp(-i (i c) P)
    G = from_sexpr(term.expr)
    return G.scale(1j)


@dataclass(frozen=True)
class TermClass:
    kind: str
    wires: tuple
    params: tuple
    label: str = ""

    def __repr__(self):
        return f"{self.kind}{self.wires}{tuple(round(complex(p).real, 6) if abs(complex(p).imag) < 1e-12 else p for p in self.params)}{(' ' + self.label) if self.label else ''}"


def classify(H: Poly):
    """Return a list of commuting TermClass parts whose exponentials multiply to exp(-iH),
    or raise ValueError if H is not a recognised shape."""
    if not H.is_hermitian():
        raise ValueError(f"non-Hermitian generator: {H}")
    items = {k: v for k, v in H.c.items() if k != ((), ())}  # drop global phase
    by_pb = defaultdict(dict)
    for (p, b), v in items.items():
        by_pb[p][b] = v
    parts = []
    # pure bosonic parts
    for p, bos in by_pb.items():
        modes = sorted({m for b in bos for m, _, _ in b})
        lab = "".join("I" for _ in range(0))
        if not p:
            if len(modes) == 1:
                m = modes[0]
                keys = {b: v for b, v in bos.items()}
                n1 = keys.pop(((m, 1, 1),), 0)
                n2 = keys.pop(((m, 2, 2),), 0)
                d1 = keys.pop(((m, 1, 0),), 0)
                d2 = keys.pop(((m, 0, 1),), 0)
                if keys:
                    raise ValueError(f"unsupported single-mode polynomial {bos}")
                # n^2 = a†²a² + n  ->  θ2 a†²a² + θ1 n = θ2 n² + (θ1 - θ2) n
                if abs(n2) > TOL:
                    parts.append(TermClass("n2", (("qm", m),), (n2.real,)))
                    n1 = n1 - n2
                if abs(n1) > TOL:
                    parts.append(TermClass("n", (("qm", m),), (n1.real,)))
                if abs(d1) > TOL or abs(d2) > TOL:
                    # H = d1 a† + d2 a (d2 = d1*) ; exp(-iH) = D(α) with α = -i d1
                    parts.append(TermClass("disp", (("qm", m),), (-1j * d1,)))
                continue
            if len(modes) == 2:
                j, k = modes
                c = bos.get(((j, 1, 0), (k, 0, 1)), 0)
                rest = {b: v for b, v in bos.items() if b not in (((j, 1, 0), (k, 0, 1)), ((j, 0, 1), (k, 1, 0)))}
                if rest or abs(c) < TOL:
                    raise ValueError(f"unsupported two-mode polynomial {bos}")
                parts.append(TermClass("hop", (("qm", j), ("qm", k)), (abs(c), math.atan2(c.imag, c.real))))
                continue
            raise ValueError(f"unsupported bosonic polynomial {bos}")
        label_q = tuple(("q", q) for q, _ in p)
        label = "".join(s for _, s in p)
        if not bos or set(bos) == {()}:
            parts.append(TermClass("pauli", label_q, (bos[()].real,), label))
            continue
        if len(modes) == 1:
            m = modes[0]
            keys = dict(bos)
            n1 = keys.pop(((m, 1, 1),), 0)
            d1 = keys.pop(((m, 1, 0),), 0)
            d2 = keys.pop(((m, 0, 1),), 0)
            if keys:
                raise ValueError(f"unsupported Pauli x boson polynomial {p} {bos}")
            if abs(n1) > TOL:
                if label != "Z" and len(p) == 1 or len(p) > 1:
                    parts.append(TermClass("pauli_n", label_q + (("qm", m),), (n1.real,), label))
                else:
                    parts.append(TermClass("z_n", label_q + (("qm", m),), (n1.real,), label))
            if abs(d1) > TOL:
                parts.append(TermClass("pauli_disp", label_q + (("qm", m),), (-1j * d1,), label))
            continue
        if len(modes) == 2:
            j, k = modes
            c = bos.get(((j, 1, 0), (k, 0, 1)), 0)
            if abs(c) < TOL or len(bos) != 2:
                raise ValueError(f"unsupported Pauli x two-mode polynomial {p} {bos}")
            kind = "z_hop" if label == "Z" else "pauli_hop"
            parts.append(TermClass(kind, label_q + (("qm", j), ("qm", k)),
                                   (abs(c), math.atan2(c.imag, c.real)), label))
            continue
        raise ValueError(f"unsupported polynomial {p} {bos}")
    return parts


def classify_term(term):
    return classify(hamiltonian_of(term))


def parse_term_text(s: str):
    """Classify a Genesis IR exponent string, e.g. 'exp(prod((-1j),dagger(b(0)),b(0)))'."""
    s = s.strip()
    assert s.startswith("exp(") and s.endswith(")")
    return classify(from_sexpr(parse_sexpr(s[4:-1])).scale(1j))
