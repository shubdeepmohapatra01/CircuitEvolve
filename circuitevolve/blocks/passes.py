"""Deterministic classical in-block passes (run before any LLM call; no LLM).

phase_fold  : phase-polynomial rotation merging (Nam et al. 2018 style, sum-over-paths form). Each wire
              carries an affine parity (mask over path variables, constant); H starts a fresh variable,
              CX xors parities, X flips the constant, CZ is diagonal and changes nothing. Every phase gate
              (rz, t, tdg, s, sdg, z) on a wire with the same parity mask is a term of the same phase
              polynomial, so all of them merge into one rz placed at the first occurrence. Exact up to
              global phase.
resynth_1q  : every maximal run of 1q gates on a qubit is replaced by its minimal-RZ Clifford+RZ form
              (circuit_io.decompose_1q) when that lowers the number of synthesised rz.
classical_pass alternates the two until the cost stops changing.
"""
from __future__ import annotations

import math

import numpy as np

from . import verify_block as vb
from .circuit_io import classify_angle, decompose_1q, emit_rz, seq_to_ops

PHASE = {"t": math.pi / 4, "tdg": -math.pi / 4, "s": math.pi / 2, "sdg": -math.pi / 2, "z": math.pi}


def _norm(a: float) -> float:
    t = math.fmod(a, 2 * math.pi)
    if t <= -math.pi:
        t += 2 * math.pi
    elif t > math.pi:
        t -= 2 * math.pi
    return t


def phase_fold(ops, n: int) -> list:
    wire = [(1 << q, 0) for q in range(n)]
    nvar = n
    out: list = []
    terms: dict[int, dict] = {}
    for g, qs, a in ops:
        if g in PHASE or g == "rz":
            th = PHASE[g] if g in PHASE else float(a)
            q = qs[0]
            mask, c = wire[q]
            f_angle = -th if c else th          # rz(th) on (mask, 1) = rz(-th) on (mask, 0) * phase
            if mask in terms:
                terms[mask]["sum"].append(f_angle)
            else:
                terms[mask] = dict(sum=[f_angle], pos=len(out), q=q, c=c, raw=th)
                out.append(None)                 # placeholder
            continue
        if g == "cx":
            ca, cb = wire[qs[0]], wire[qs[1]]
            wire[qs[1]] = (ca[0] ^ cb[0], ca[1] ^ cb[1])
        elif g == "x":
            m, c = wire[qs[0]]
            wire[qs[0]] = (m, c ^ 1)
        elif g == "h":
            wire[qs[0]] = (1 << nvar, 0)
            nvar += 1
        elif g == "cz":
            pass
        else:
            raise ValueError(f"phase_fold: unsupported gate {g}")
        out.append((g, qs, a))
    slots: dict[int, list] = {}
    for t in terms.values():
        if len(t["sum"]) == 1:
            ang = t["raw"]                       # untouched rotation: keep the identical float
        else:
            tot = _norm(math.fsum(t["sum"]))
            ang = -tot if t["c"] else tot
        seg: list = []
        emit_rz(seg, t["q"], ang)
        slots[t["pos"]] = seg
    res = []
    for i, op in enumerate(out):
        if op is None:
            res.extend(slots[i])
        else:
            res.append(op)
    return res


def _n_rz(ops) -> int:
    return sum(1 for g, _, a in ops if g == "rz" and classify_angle(float(a)) is None)


def resynth_1q(ops, n: int) -> list:
    out: list = []
    run: dict[int, list] = {q: [] for q in range(n)}

    def flush(q):
        r = run[q]
        run[q] = []
        if not r:
            return
        r0 = [(g, (0,), a) for g, _, a in r]
        U = vb.unitary(r0, 1)
        _, seq = decompose_1q(U)
        new = seq_to_ops(seq, q)
        old_t = sum(1 for g, _, _ in r if g in ("t", "tdg"))
        new_t = sum(1 for g, _, _ in new if g in ("t", "tdg"))
        if (_n_rz(new), new_t, len(new)) < (_n_rz(r), old_t, len(r)):
            out.extend(new)
        else:
            out.extend(r)

    for op in ops:
        if len(op[1]) == 1:
            run[op[1][0]].append(op)
        else:
            for q in op[1]:
                flush(q)
            out.append(op)
    for q in range(n):
        flush(q)
    return out


def classical_pass(ops, n: int, max_iter: int = 6) -> list:
    cur = list(ops)
    key = (_n_rz(cur), sum(g in ("t", "tdg") for g, _, _ in cur), len(cur))
    for _ in range(max_iter):
        nxt = resynth_1q(phase_fold(cur, n), n)
        k2 = (_n_rz(nxt), sum(g in ("t", "tdg") for g, _, _ in nxt), len(nxt))
        if k2 >= key:
            break
        cur, key = nxt, k2
    return cur
