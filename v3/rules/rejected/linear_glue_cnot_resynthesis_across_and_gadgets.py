"""Resynthesize maximal CX/X blocks (grown across wire-disjoint gates) as one F2 affine map; T-count untouched."""
import numpy as np

from v3.api import Rule
from v3.api import dv


def _view(c):
    """[(name, qubits, plain)] where plain = unconditional cx / x."""
    if dv.is_angle_circuit(c):
        if any(op[0] == "rz" for op in c.ops):
            return None  # relaxed-mode literal check cannot certify continuous-Rz circuits
        return [(op[0], tuple(op[1]), op[0] in ("cx", "x")) for op in c.ops]
    if dv.is_ir_circuit(c):
        return [(g.name, tuple(g.qubits), g.name in ("cx", "x") and g.cond is None and g.cbit is None)
                for g in c.gates]
    return None


def _blocks(view):
    out = []
    blk, W, S = [], set(), set()
    for i, (name, qs, plain) in enumerate(view):
        wires = set(qs)
        if plain:
            if blk and wires & S:
                out.append(blk)
                blk, W, S = [], set(), set()
            blk.append(i)
            W |= wires
        elif blk:
            if wires & W:
                out.append(blk)
                blk, W, S = [], set(), set()
            else:
                S |= wires
    if blk:
        out.append(blk)
    return out


def _affine(block, view, wires):
    idx = {w: k for k, w in enumerate(wires)}
    m = len(wires)
    M = np.eye(m, dtype=np.uint8)
    cvec = np.zeros(m, dtype=np.uint8)
    for i in block:
        name, qs, _ = view[i]
        if name == "cx":
            a, b = idx[qs[0]], idx[qs[1]]
            M[b] ^= M[a]
            cvec[b] ^= cvec[a]
        else:
            cvec[idx[qs[0]]] ^= 1
    return M, cvec


def _lower(mat, sec):
    n = mat.shape[0]
    ops = []
    for s in range((n + sec - 1) // sec):
        lo, hi = s * sec, min((s + 1) * sec, n)
        patt = {}
        for row in range(lo, n):
            sub = tuple(mat[row, lo:hi])
            if not any(sub):
                continue
            if sub in patt:
                mat[row] ^= mat[patt[sub]]
                ops.append((patt[sub], row))
            else:
                patt[sub] = row
        for col in range(lo, hi):
            diag = mat[col, col] == 1
            for row in range(col + 1, n):
                if mat[row, col]:
                    if not diag:
                        mat[col] ^= mat[row]
                        ops.append((row, col))
                        diag = True
                    mat[row] ^= mat[col]
                    ops.append((col, row))
    return ops


def _pmh(M):
    """CX sequence (application order) realising M, as (control, target) pairs."""
    n = M.shape[0]
    sec = max(1, int(round(np.log2(n) / 2))) if n > 1 else 1
    A = M.copy()
    low = _lower(A, sec)                       # E_k..E_1 M = U
    ups = _lower(A.T.copy(), sec)              # U^T eliminated; swap pairs
    return [(t, c) for c, t in ups] + low[::-1]


def _gj(M):
    A = M.copy()
    n = A.shape[0]
    ops = []
    for col in range(n):
        if not A[col, col]:
            r = next((r for r in range(col + 1, n) if A[r, col]), None)
            if r is None:
                return None
            A[col] ^= A[r]
            ops.append((r, col))
        for row in range(n):
            if row != col and A[row, col]:
                A[row] ^= A[col]
                ops.append((col, row))
    return ops[::-1]


def _greedy(M):
    n = M.shape[0]
    if n > 24:
        return None
    A = [int("".join(str(int(v)) for v in row), 2) for row in M]
    pc = [bin(r).count("1") for r in A]
    ops = []
    for _ in range(4 * n * n):
        if sum(pc) == n and all(A[k] == 1 << (n - 1 - k) for k in range(n)):
            return ops[::-1]
        best = None
        for i in range(n):
            for j in range(n):
                if i != j:
                    d = bin(A[j] ^ A[i]).count("1") - pc[j]
                    if d < 0 and (best is None or d < best[0]):
                        best = (d, i, j)
        if best is None:
            return None
        d, i, j = best
        A[j] ^= A[i]
        pc[j] += d
        ops.append((i, j))
    return None


def _realises(ops, M):
    n = M.shape[0]
    S = np.eye(n, dtype=np.uint8)
    for c, t in ops:
        S[t] ^= S[c]
    return (S == M).all()


def _resynth(M):
    best = None
    for f in (_pmh, _gj, _greedy):
        try:
            ops = f(M)
        except Exception:
            ops = None
        if ops is not None and _realises(ops, M) and (best is None or len(ops) < len(best)):
            best = ops
    return best


def find_matches(c):
    view = _view(c)
    if view is None:
        return []
    out = []
    for blk in _blocks(view):
        if len(blk) < 2:
            continue
        wires = sorted({q for i in blk for q in view[i][1]})
        if len(wires) < 2:
            continue
        M, cvec = _affine(blk, view, wires)
        ops = _resynth(M)
        if ops is None:
            continue
        old_cx = sum(1 for i in blk if view[i][0] == "cx")
        old_x = len(blk) - old_cx
        new_x = int(cvec.sum())
        if len(ops) < old_cx and len(ops) + new_x <= len(blk):
            repl = tuple(("cx", (wires[a], wires[b])) for a, b in ops) + \
                   tuple(("x", (wires[j],)) for j in range(len(wires)) if cvec[j])
            out.append((tuple(blk), repl))
    return out


def apply_match(c, m):
    view = _view(c)
    blk, repl = m
    if view is None or any(not view[i][2] for i in blk):
        return c
    bset = set(blk)
    lo, hi = blk[0], blk[-1]
    if dv.is_angle_circuit(c):
        items = list(c.ops)
        new = [(n, q, None) for n, q in repl]
        out = items[:lo] + [items[i] for i in range(lo, hi + 1) if i not in bset] + new + items[hi + 1:]
        return dv.with_ops(c, out)
    items = list(c.gates)
    new = [dv.IRGate(n, q) for n, q in repl]
    out = items[:lo] + [items[i] for i in range(lo, hi + 1) if i not in bset] + new + items[hi + 1:]
    return dv.ir_with_gates(c, out)


RULE = Rule(
    name="linear_glue_cnot_resynthesis_across_and_gadgets",
    domain="dv",
    kind="procedure",
    contract="relaxed",
    source="Patel-Markov-Hayes 2008 (linear reversible synthesis); Aaronson-Gottesman 2004 (CX/X = affine group over F2)",
    idea="A maximal block of cx/x gates (grown across gates on disjoint wires) is an affine map (M, c) over F2; "
         "resynthesize M by PMH / Gauss-Jordan / greedy elimination, keep the shortest CX list, emit X for c. "
         "Unload/reload networks around AND gadgets fuse into one block. T-count untouched; exact.",
    trigger=find_matches,
    apply=apply_match,
)
