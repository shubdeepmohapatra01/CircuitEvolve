"""Literal text format for block programs, its parser, and numerical instantiation of free parameters.

Format (one gate per line; '#' starts a comment; the header line is optional):

    qubits 3
    cx q0 q1
    rz(a0 + a3) q1          # exact rewrite: expression over the instance's input angles a0..ak
    rz(-a1/2 + pi/4) q2
    rz(p0) q0               # free parameter: fitted per instance by numerical instantiation
    h q2

Gates: h s sdg x z t tdg cx cz rz on local qubits q0..q{n-1}. Angle expressions are parsed with
`ast` and evaluated by a whitelist walker: numbers, pi, a<i>, p<j>, unary +/-, binary + - * /.
Nothing is ever exec'd or eval'd.
"""
from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass

import numpy as np

from circuitevolve.blocks.circuit_io import emit_rz

GATES_1Q = {"h", "s", "sdg", "x", "z", "t", "tdg"}
GATES_2Q = {"cx", "cz"}
GATES = GATES_1Q | GATES_2Q | {"rz"}
MAX_EXPR_CHARS = 200
MAX_LINES = 120
_NAME = re.compile(r"^(a|p)(\d{1,3})$")


class ParseError(ValueError):
    pass


# ------------------------------------------------------------------------------ expressions
def parse_expr(text: str):
    """Angle expression -> tree of tuples: ('num', x) | ('a', i) | ('p', j) | ('neg', t) |
    ('+'|'-'|'*'|'/', l, r)."""
    text = text.strip()
    if not text or len(text) > MAX_EXPR_CHARS:
        raise ParseError(f"bad expression length: {text[:40]!r}")
    try:
        node = ast.parse(text, mode="eval").body
    except SyntaxError as e:
        raise ParseError(f"syntax error in {text!r}") from e

    def walk(n, depth=0):
        if depth > 40:
            raise ParseError("expression too deep")
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return ("num", float(n.value))
        if isinstance(n, ast.Name):
            if n.id == "pi":
                return ("num", math.pi)
            m = _NAME.match(n.id)
            if m:
                return (m.group(1), int(m.group(2)))
            raise ParseError(f"unknown name {n.id!r}")
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            t = walk(n.operand, depth + 1)
            return ("neg", t) if isinstance(n.op, ast.USub) else t
        if isinstance(n, ast.BinOp) and type(n.op) in _BINOPS:
            return (_BINOPS[type(n.op)], walk(n.left, depth + 1), walk(n.right, depth + 1))
        raise ParseError(f"disallowed syntax {type(n).__name__} in {text!r}")

    return walk(node)


_BINOPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}


def eval_expr(t, a, p) -> float:
    k = t[0]
    if k == "num":
        return t[1]
    if k == "a":
        return float(a[t[1]])
    if k == "p":
        return float(p[t[1]])
    if k == "neg":
        return -eval_expr(t[1], a, p)
    x, y = eval_expr(t[1], a, p), eval_expr(t[2], a, p)
    if k == "+":
        return x + y
    if k == "-":
        return x - y
    if k == "*":
        return x * y
    if y == 0:
        raise ZeroDivisionError("division by zero in angle expression")
    return x / y


def expr_vars(t, kind: str) -> set:
    if t[0] == kind:
        return {t[1]}
    if t[0] in ("num", "a", "p"):
        return set()
    return set().union(*(expr_vars(s, kind) for s in t[1:]))


def expr_str(t) -> str:
    k = t[0]
    if k == "num":
        return "pi" if t[1] == math.pi else repr(t[1])
    if k in ("a", "p"):
        return f"{k}{t[1]}"
    if k == "neg":
        return f"-({expr_str(t[1])})"
    return f"({expr_str(t[1])} {k} {expr_str(t[2])})"


# ------------------------------------------------------------------------------ programs
@dataclass
class Program:
    n: int
    ops: list            # (gate, local qubits, expr tree | None)
    text: str = ""

    @property
    def a_used(self) -> set:
        return set().union(set(), *(expr_vars(e, "a") for _, _, e in self.ops if e is not None))

    @property
    def n_params(self) -> int:
        ps = set().union(set(), *(expr_vars(e, "p") for _, _, e in self.ops if e is not None))
        return (max(ps) + 1) if ps else 0

    @property
    def kind(self) -> str:
        return "parametric" if self.n_params else "exact"

    def materialize(self, a, p=()) -> list:
        """Concrete local ops; rz angles that are multiples of pi/4 become Clifford/T gates."""
        out = []
        for g, qs, e in self.ops:
            if g == "rz":
                emit_rz(out, qs[0], eval_expr(e, a, p))
            else:
                out.append((g, qs, None))
        return out

    def to_text(self) -> str:
        lines = [f"qubits {self.n}"]
        for g, qs, e in self.ops:
            q = " ".join(f"q{x}" for x in qs)
            lines.append(f"rz({expr_str(e)}) {q}" if g == "rz" else f"{g} {q}")
        return "\n".join(lines)


_LINE = re.compile(r"^([a-z]+)\s*(?:\((.*)\))?\s+(q\d+)(?:\s*[, ]\s*(q\d+))?\s*;?$")
_ALIASES = {"cnot": "cx", "tdag": "tdg", "sdag": "sdg", "t†": "tdg", "s†": "sdg"}


def parse_program(text: str, n: int, k_angles: int) -> Program:
    """Parse one block program for an n-qubit block whose instance has k_angles input angles."""
    ops = []
    lines = [ln.split("#", 1)[0].strip() for ln in text.strip().splitlines()]
    lines = [ln for ln in lines if ln]
    if len(lines) > MAX_LINES:
        raise ParseError(f"program too long ({len(lines)} lines)")
    for ln in lines:
        m = re.match(r"^qubits\s+(\d+)$", ln)
        if m:
            if int(m.group(1)) != n:
                raise ParseError(f"header says {m.group(1)} qubits, block has {n}")
            continue
        m = _LINE.match(ln.lower())
        if not m:
            raise ParseError(f"cannot parse line {ln!r}")
        g = _ALIASES.get(m.group(1), m.group(1))
        if g not in GATES:
            raise ParseError(f"gate {g!r} not allowed")
        qs = tuple(int(x[1:]) for x in (m.group(3), m.group(4)) if x)
        if any(q >= n for q in qs):
            raise ParseError(f"qubit out of range in {ln!r}")
        arity = 2 if g in GATES_2Q else 1
        if len(qs) != arity or len(set(qs)) != len(qs):
            raise ParseError(f"wrong qubits for {g} in {ln!r}")
        if g == "rz":
            if m.group(2) is None:
                raise ParseError("rz needs an angle")
            e = parse_expr(m.group(2))
            bad = [i for i in expr_vars(e, "a") if i >= k_angles]
            if bad:
                raise ParseError(f"a{bad[0]} does not exist (block has {k_angles} angles)")
            ops.append(("rz", qs, e))
        else:
            if m.group(2) is not None:
                raise ParseError(f"{g} takes no angle")
            ops.append((g, qs, None))
    return Program(n=n, ops=ops, text=text)


def block_program(local_ops, n: int) -> Program:
    """The identity program of a block: its rz angles become a0, a1, ... in order."""
    ops, k = [], 0
    for g, qs, _ in local_ops:
        if g == "rz":
            ops.append(("rz", qs, ("a", k)))
            k += 1
        else:
            ops.append((g, qs, None))
    return Program(n=n, ops=ops)


def looks_like_program(body: str) -> bool:
    """True if every non-empty, non-comment line is a gate line or the 'qubits N' header."""
    lines = [ln.split("#", 1)[0].strip().lower() for ln in body.splitlines()]
    lines = [ln for ln in lines if ln]
    return bool(lines) and all(_LINE.match(ln) or re.match(r"^qubits\s+\d+$", ln) for ln in lines)


def extract_programs(text: str, max_programs: int = 8, counts: dict | None = None) -> list[str]:
    """Bodies of ```block fenced code blocks, in order. Untagged / text / qasm fences are kept only if
    they look like a program (models sometimes print simulated tool output such as '(8, 8)' in bare
    fences); skipped fences are counted in counts['non_program_block']."""
    raw = _fences(text)
    out = []
    for tag, body in raw:
        if tag == "block" or (tag in ("", "text", "qasm") and looks_like_program(body)):
            out.append(body)
        elif counts is not None:
            counts["non_program_block"] = counts.get("non_program_block", 0) + 1
    return out[:max_programs]


def _fences(text: str) -> list:
    out, cur, fence, tag = [], [], False, ""
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("```"):
            if fence:                      # closing fence
                out.append((tag, "\n".join(cur)))
                cur, fence = [], False
            else:
                fence, tag = True, s[3:].strip().lower()
            continue
        if fence:
            cur.append(ln)
    return out


# ------------------------------------------------------------------------------ fitting
def _fast_unitary_factory(prog: Program, a):
    """Return V(p) for fixed instance angles a: product of 2^n x 2^n factors, rz ops parameterised."""
    from circuitevolve.blocks import verify_block as vb
    n, dim = prog.n, 1 << prog.n
    bits = [np.array([(x >> (n - 1 - q)) & 1 for x in range(dim)]) for q in range(n)]
    factors = []
    for g, qs, e in prog.ops:
        if g == "rz":
            factors.append(("rz", qs[0], e))
        else:
            factors.append(("M", vb.unitary([(g, qs, None)], n)))

    def V(p):
        U = np.eye(dim, dtype=complex)
        for f in factors:
            if f[0] == "M":
                U = f[1] @ U
            else:
                th = eval_expr(f[2], a, p)
                d = np.where(bits[f[1]] == 1, np.exp(0.5j * th), np.exp(-0.5j * th))
                U = d[:, None] * U
        return U
    return V


def fit_params(prog: Program, target: np.ndarray, a, restarts: int = 6, seed: int = 0,
               tol: float = 1e-10, snap: bool = True, x0=None, max_nfev: int = 1500):
    """Least-squares instantiation of p (Levenberg-Marquardt on the phase-aligned residual).
    Returns (p, dist_frobenius_estimate) for the best restart; snapping tries to set parameters to
    multiples of pi/4 (free in Clifford+T) when the fit stays within tol."""
    from scipy.optimize import least_squares
    m = prog.n_params
    V = _fast_unitary_factory(prog, a)
    if m == 0:
        return [], _pdist(V([]), target)
    rng = np.random.default_rng(seed)

    def resid(x):
        D = V(list(x[:-1])) - np.exp(1j * x[-1]) * target
        return np.concatenate([D.real.ravel(), D.imag.ravel()])

    best = (None, float("inf"))
    starts = []
    if x0 is not None and len(x0) == m:            # warm start (e.g. the fit of a sibling instance)
        U0 = V(list(x0))
        starts.append(np.concatenate([np.asarray(x0, float), [float(np.angle(np.trace(target.conj().T @ U0)))]]))
    while len(starts) < restarts + (1 if starts else 0):
        starts.append(np.concatenate([rng.uniform(-math.pi, math.pi, m), [rng.uniform(-math.pi, math.pi)]]))
    for xs in starts:
        sol = least_squares(resid, xs, method="lm", xtol=1e-15, ftol=1e-15, gtol=1e-15, max_nfev=max_nfev)
        p = list(sol.x[:-1])
        d = _pdist(V(p), target)
        if d < best[1]:
            best = (p, d)
        if d < tol:
            break
    p, d = best
    if snap and d < tol:
        p, d = _snap(V, target, p, d, tol)
    # canonical representatives in (-pi, pi] (rz(x + 2pi) = -rz(x): same unitary up to phase)
    p = [math.remainder(x, 2 * math.pi) for x in p]
    return p, _pdist(V(p), target)


def _merge(free, fixed, m):
    it = iter(free)
    return [fixed[i] if i in fixed else next(it) for i in range(m)]


def _pdist(U, T) -> float:
    tr = np.trace(T.conj().T @ U)
    ph = tr / abs(tr) if abs(tr) > 1e-300 else 1.0
    return float(np.linalg.norm(U - ph * T, 2))


def _snap(V, target, p, d, tol):
    from scipy.optimize import least_squares
    m = len(p)
    fixed: dict[int, float] = {}
    order = sorted(range(m), key=lambda i: abs(p[i] / (math.pi / 4) - round(p[i] / (math.pi / 4))))
    cur = list(p)
    for i in order:
        q = round(cur[i] / (math.pi / 4)) * (math.pi / 4)
        if abs(cur[i] - q) > 0.3:
            continue
        trial = dict(fixed)
        trial[i] = q
        free_idx = [j for j in range(m) if j not in trial]

        def resid(x):
            pp = _merge(x[:-1], trial, m)
            D = V(pp) - np.exp(1j * x[-1]) * target
            return np.concatenate([D.real.ravel(), D.imag.ravel()])
        U0 = V(cur)
        tr = np.trace(target.conj().T @ U0)
        x0 = np.array([cur[j] for j in free_idx] + [float(np.angle(tr))])
        if free_idx:
            sol = least_squares(resid, x0, method="lm", xtol=1e-15, ftol=1e-15, gtol=1e-15, max_nfev=600)
            pp = _merge(sol.x[:-1], trial, m)
        else:
            pp = _merge([], trial, m)
        dd = _pdist(V(pp), target)
        if dd < tol:
            fixed, cur, d = trial, pp, dd
    return cur, d


def potential_rz(prog: Program, a) -> int:
    """Upper bound on the synthesised rz of `prog` on angles a: rz with a free parameter count 1; rz
    with an a_i-only expression count 1 unless it evaluates to a multiple of pi/4."""
    from circuitevolve.blocks.circuit_io import classify_angle
    n = 0
    for g, _, e in prog.ops:
        if g != "rz":
            continue
        if expr_vars(e, "p"):
            n += 1
        else:
            try:
                n += classify_angle(eval_expr(e, a, ())) is None
            except (ZeroDivisionError, OverflowError, IndexError):
                n += 1
    return n
