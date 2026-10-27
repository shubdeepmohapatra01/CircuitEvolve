"""FROZEN verifier for cvdv_fast (window checks per rule application + whole-circuit check).

window_check(H, ops)            synthesis: gate list `ops` vs exp(-iH) on S = {term qubits arbitrary, term modes
                                with total photons <= N_PROBE, every other wire |0>/vacuum}; phase-aligned operator
                                distance (spectral norm on S) at K in CUTOFFS; result = max over K.
rewrite_check(old, new)         rewrite: new op list vs old op list on S = {all window wires, total photons <=
                                N_PROBE}; same distance.
whole_check(terms, ops, fmap)   whole circuit vs ordered Trotter product prod_k exp(-iH_k) (first term acts first),
                                N_HAAR Haar-random probes in S (seeded), ancillas must return to |0>/vacuum; the
                                physical circuit's output is compared after the router's final logical->physical
                                map. Infidelity per probe = 1 - |<expected|out>|^2; report mean and max per K.
"""
from __future__ import annotations

import numpy as np

from .enr import Space, basis_block, haar_block, phase_aligned_dist, probe_subspace

CUTOFFS = (12, 16)          # window checks (total-photon cutoff K); measured truncation on the ZZ bus gadget: 8.2e-7 (K=12), 1.9e-9 (K=16); dist = max over K, so <= ~1e-6 = runner EXACT_TOL
WHOLE_CUTOFFS = (10, 12)    # whole-circuit default; lowered per benchmark only if memory requires (recorded)
N_PROBE = 3
N_HAAR = 8
SEED = 20261021


NONCONSERVING = {"D", "CD", "RB"}


def _conserving(Hs, ops):
    """True if every gate and every spec monomial conserves total photon number: then the <= N_PROBE-photon sector
    is invariant and cutoff K = N_PROBE is EXACT (no truncation)."""
    if any(o.name in NONCONSERVING for o in ops):
        return False
    return all(sum(pd for _, pd, _ in bo) == sum(pn for _, _, pn in bo) for H in Hs for (_pa, bo) in H.c)


def _wires(ops):
    ws = []
    for o in ops:
        for w in o.wires:
            if w not in ws:
                ws.append(w)
    return ws


def _split(ws):
    q = sorted({w for w in ws if w[0] == "q"}, key=lambda w: w[1])
    m = sorted({w for w in ws if w[0] == "qm"}, key=lambda w: w[1])
    return q, m


def window_check(H, ops, cutoffs=CUTOFFS, n_probe=N_PROBE):
    if _conserving([H], ops):
        cutoffs = (n_probe,)
    sysw = [("q", q) for q in sorted({q for (pa, _bo) in H.c for q, _ in pa})] + \
           [("qm", m) for m in sorted({m for (_pa, bo) in H.c for m, _, _ in bo})]
    qs, ms = _split(list(sysw) + _wires(ops))
    out = {}
    for K in cutoffs:
        S = Space(qs, ms, K)
        cols = probe_subspace(S, [w for w in sysw if w[0] == "q"], [w for w in sysw if w[0] == "qm"], n_probe)
        psi = basis_block(S, cols)
        W = S.run(psi, ops)
        X = S.apply_term(psi, S.term_generator(H))
        out[K] = dict(dist=phase_aligned_dist(W, X), leak=S.top_leak(W), dim=S.D * S.Q, cols=len(cols))
    return dict(dist=max(v["dist"] for v in out.values()), per_K=out)


def rewrite_check(old, new, cutoffs=CUTOFFS, n_probe=N_PROBE):
    if _conserving([], list(old) + list(new)):
        cutoffs = (n_probe,)
    ws = _wires(old) + [w for w in _wires(new) if w not in _wires(old)]
    qs, ms = _split(ws)
    out = {}
    for K in cutoffs:
        S = Space(qs, ms, K)
        cols = probe_subspace(S, qs, ms, n_probe)
        psi = basis_block(S, cols)
        out[K] = dict(dist=phase_aligned_dist(S.run(psi, new), S.run(psi, old)), dim=S.D * S.Q, cols=len(cols))
    return dict(dist=max(v["dist"] for v in out.values()), per_K=out)


def _embed_index(src: Space, dst: Space, wmap):
    """Flat index in dst (d*Q+q) of every src basis state (d*Q+q); wire w of src sits at wmap[w] in dst."""
    mpos = [dst.mi[wmap[w]] for w in src.modes]
    qpos = [dst.qi[wmap[w]] for w in src.qubits]
    out = np.empty(src.D * src.Q, dtype=np.int64)
    for d, s in enumerate(src.states):
        occ = [0] * dst.M
        for i, n in zip(mpos, s):
            occ[i] = n
        dd = dst.idx[tuple(occ)]
        for q in range(src.Q):
            bits = [(q >> (src.nq - 1 - j)) & 1 for j in range(src.nq)]
            qb = 0
            for j, b in zip(qpos, bits):
                if b:
                    qb |= 1 << (dst.nq - 1 - j)
            out[d * src.Q + q] = dd * dst.Q + qb
    return out


def whole_check(Hs, ops, final_map=None, cutoffs=WHOLE_CUTOFFS, n_probe=N_PROBE, n_haar=N_HAAR, seed=SEED):
    """Hs: list of term Hamiltonians (cvdv.terms.Poly) in Trotter order; ops: synthesized circuit (no placeholders).
    final_map: {logical wire: physical wire} after routing (missing entries = identity)."""
    sysw = []
    for H in Hs:
        for (pa, bo) in H.c:
            for q, _ in pa:
                if ("q", q) not in sysw:
                    sysw.append(("q", q))
            for m, _, _ in bo:
                if ("qm", m) not in sysw:
                    sysw.append(("qm", m))
    sq, sm = _split(sysw)
    exact_sector = _conserving(Hs, ops)
    if exact_sector:
        cutoffs = (n_probe,)
    fmap = {w: w for w in sysw}
    if final_map:
        fmap.update({tuple(k): tuple(v) for k, v in final_map.items() if tuple(k) in fmap})
    cq, cm = _split(_wires(ops) + sysw + list(fmap.values()))
    res = {}
    for K in cutoffs:
        A = Space(sq, sm, K)          # spec space (system wires only)
        C = Space(cq, cm, K)          # circuit space
        cols = probe_subspace(A, sq, sm, n_probe)
        probes = haar_block(A, cols, n_haar, seed)
        spec = probes
        for H in Hs:
            spec = A.apply_term(spec, A.term_generator(H))
        ein = _embed_index(A, C, {w: w for w in sysw})
        eout = _embed_index(A, C, fmap)
        P = probes.shape[-1]
        psi = np.zeros((C.D * C.Q, P), dtype=complex)
        psi[ein] = probes.reshape(A.D * A.Q, P)
        out = C.run(psi.reshape(C.D, C.Q, P), ops).reshape(C.D * C.Q, P)
        exp = np.zeros_like(out)
        exp[eout] = spec.reshape(A.D * A.Q, P)
        ov = np.abs(np.einsum("ip,ip->p", exp.conj(), out)) ** 2
        inf = 1 - ov
        res[K] = dict(mean_infid=float(inf.mean()), max_infid=float(inf.max()),
                      leak=C.top_leak(out.reshape(C.D, C.Q, P)), dim=C.D * C.Q, probes=P, probe_dim=len(cols))
    worst = max(v["max_infid"] for v in res.values())
    agree = abs(res[cutoffs[0]]["max_infid"] - res[cutoffs[-1]]["max_infid"])
    return dict(max_infid=worst, mean_infid=max(v["mean_infid"] for v in res.values()), cutoff_gap=agree, per_K=res,
                exact_sector=exact_sector, cutoffs=list(cutoffs))
