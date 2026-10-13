"""Certified term-by-term synthesis.

compile_step(terms, rules, eps_total, n_max) compiles one Trotter step (ordered product of the
term exponentials in Genesis' intermediate IR) into PS_BS gates such that

    || V - e^{iφ} Π_k exp(-i H_k) ||_S  <=  Σ_k eps_k  <=  eps_total

on S = {total photon number <= n_max} ⊗ qubits, with every eps_k a certificate (certify.py) for
the exact instance emitted.  Policy (this function is the evolvable "path policy", v0):
  1. classify each term into commuting parts;
  2. for each part and each library rule of its kind, evaluate r = 1; parts whose best rule is exact
     (eps <= EXACT_TOL) consume no budget;
  3. the remaining budget is split equally over the inexact parts; for each, every rule is driven to
     the smallest r (doubling, then bisection, r <= r_max) meeting its share, and the rule with the
     lowest local (duration, two_op, one_op) wins.
Certificates are cached on (relabelled H, relabelled ops): reused only for an identical gate list.
"""
from __future__ import annotations

import time

from . import certify as C
from . import isa as ISA
from . import metrics as M
from .library import Builder, LibraryError, TermView
from .terms import Poly, classify, hamiltonian_of

EXACT_TOL = 1e-9


def _relabel(H: Poly, ops):
    mp = {}
    for w in H.wires():
        mp[w] = (w[0], sum(1 for v in mp if v[0] == w[0]))
    for o in ops:
        for w in o.wires:
            if w not in mp:
                mp[w] = (w[0], 1000 + sum(1 for v in mp if v[0] == w[0]))
    hk = tuple(sorted((tuple((mp[("q", q)][1], s) for q, s in p),
                       tuple((mp[("qm", m)][1], a, b) for m, a, b in bb), round(c.real, 12), round(c.imag, 12))
                      for (p, bb), c in H.c.items()))
    ok = tuple((o.name, tuple(complex(round(complex(x).real, 12), round(complex(x).imag, 12)) for x in o.params),
                tuple(mp[w] for w in o.wires)) for o in ops)
    return hk, ok


class Compiler:
    def __init__(self, rules, n_max=4, n_sys_q=0, n_sys_m=0, r_max=4096, isa=ISA.PS_BS, log=None):
        self.rules, self.n_max, self.r_max, self.isa = rules, n_max, r_max, isa
        self.anc_q_base, self.anc_m_base = n_sys_q, n_sys_m
        self.cache = {}
        self.n_cert = 0
        self.t_cert = 0.0
        self.log = log or (lambda *a: None)

    def emit(self, part, fn, r):
        g = Builder(self.anc_q_base, self.anc_m_base)
        g._site_m = next((w[1] for w in part.wires if w[0] == "qm"), 0)
        g._site_q = next((w[1] for w in part.wires if w[0] == "q"), 0)
        fn(TermView(part), g, r)
        return g.ops

    def evaluate(self, part, H, fn, r):
        """-> (ops, cert, cost) or None if the rule declines / emits invalid gates."""
        try:
            ops = self.emit(part, fn, r)
        except (ValueError, LibraryError, ZeroDivisionError, TypeError, IndexError, KeyError):
            return None
        if not ops or ISA.check(ops, self.isa):
            return None
        sysw = set(H.wires())
        for o in ops:  # rules may only touch the term's wires and their own ancillas
            for w in o.wires:
                if w not in sysw and not ((w[0] == "q" and w[1] >= self.anc_q_base) or
                                          (w[0] == "qm" and w[1] >= self.anc_m_base)):
                    return None
        key = _relabel(H, ops)
        cert = self.cache.get(key)
        if cert is None:
            t0 = time.time()
            cert = C.certify(H, ops, part.kind, n_max=self.n_max)
            self.t_cert += time.time() - t0
            self.n_cert += 1
            self.cache[key] = cert
        if not cert["reliable"]:
            return None
        m = M.metrics(ops)
        return ops, cert, (m["duration"], m["two_op"], m["one_op"])

    def best_r(self, part, H, fn, budget):
        ev = self.evaluate(part, H, fn, 1)
        if ev is None:
            return None
        if ev[1]["eps"] <= budget:
            return 1, ev
        lo, hi, evhi = 1, 2, None
        while hi <= self.r_max:
            evhi = self.evaluate(part, H, fn, hi)
            if evhi is None:
                return None
            if evhi[1]["eps"] <= budget:
                break
            lo, hi = hi, hi * 2
        else:
            return None
        while hi - lo > 1:
            mid = (lo + hi) // 2
            evm = self.evaluate(part, H, fn, mid)
            if evm is not None and evm[1]["eps"] <= budget:
                hi, evhi = mid, evm
            else:
                lo = mid
        return hi, evhi

    def compile_step(self, terms, eps_total):
        items = []
        for k, t in enumerate(terms):
            Hk = hamiltonian_of(t)
            parts = classify(Hk)
            Hs = [part_hamiltonian(p) for p in parts]
            recon = Poly()
            for h in Hs:
                recon = recon + h
            drift = {kk: v for kk, v in (recon - Hk).c.items() if kk != ((), ()) and abs(v) > 1e-9}
            if drift:
                raise RuntimeError(f"term {k}: parts do not sum to H ({drift})")
            for a in range(len(Hs)):
                for b in range(a + 1, len(Hs)):
                    comm = Hs[a] * Hs[b] - Hs[b] * Hs[a]
                    if any(abs(v) > 1e-9 for v in comm.c.values()):
                        raise RuntimeError(f"term {k}: non-commuting parts {parts[a]} / {parts[b]}")
            for part, h in zip(parts, Hs):
                items.append((k, part, h))
        # pass 1: exact parts
        choice = {}
        inexact = []
        for i, (k, part, H) in enumerate(items):
            best = None
            for name, fn in self.rules.get(part.kind, []):
                ev = self.evaluate(part, H, fn, 1)
                if ev and ev[1]["eps"] <= EXACT_TOL and (best is None or ev[2] < best[2][2]):
                    best = (name, 1, ev)
            if best:
                choice[i] = best
            else:
                inexact.append(i)
        used = sum(choice[i][2][1]["eps"] for i in choice)
        share = (eps_total - used) / max(1, len(inexact))
        for i in inexact:
            k, part, H = items[i]
            best = None
            for name, fn in self.rules.get(part.kind, []):
                res = self.best_r(part, H, fn, share)
                if res and (best is None or res[1][2] < best[2][2]):
                    best = (name, res[0], res[1])
            if best is None:
                raise RuntimeError(f"no rule meets eps share {share:.2e} for {part}")
            choice[i] = best
            self.log(f"  {part} -> {best[0]} r={best[1]} eps={best[2][1]['eps']:.2e}")
        ops, report = [], []
        for i, (k, part, H) in enumerate(items):
            name, r, (o, cert, cost) = choice[i]
            ops.extend(o)
            report.append({"term": k, "part": repr(part), "kind": part.kind, "rule": name, "r": r,
                           "eps": cert["eps"], "invariant": cert["invariant"], "n_ops": len(o)})
        bound = sum(x["eps"] for x in report)
        return ops, {"parts": report, "eps_bound": bound,
                     "bound_valid": all(x["invariant"] for x in report), "eps_target": eps_total,
                     "n_max": self.n_max, "n_cert": self.n_cert}


def part_hamiltonian(part) -> Poly:
    """Hermitian H of one classified part (inverse of terms.classify for that part)."""
    import cmath
    k, w, p = part.kind, part.wires, part.params
    qs = [x[1] for x in w if x[0] == "q"]
    ms = [x[1] for x in w if x[0] == "qm"]
    P = tuple((q, s) for q, s in zip(qs, part.label))
    if k == "n":
        return Poly({((), ((ms[0], 1, 1),)): p[0]})
    if k == "n2":
        n = Poly({((), ((ms[0], 1, 1),)): 1.0})
        return (n * n).scale(p[0])
    if k in ("hop", "z_hop", "pauli_hop"):
        c = p[0] * cmath.exp(1j * p[1])
        j, l = ms
        return Poly({(P, ((j, 1, 0), (l, 0, 1))): c, (P, ((j, 0, 1), (l, 1, 0))): c.conjugate()})
    if k in ("z_n", "pauli_n"):
        return Poly({(P, ((ms[0], 1, 1),)): p[0]})
    if k == "pauli":
        return Poly({(P, ()): p[0]})
    if k in ("disp", "pauli_disp"):
        a = complex(p[0])
        return Poly({(P, ((ms[0], 1, 0),)): 1j * a, (P, ((ms[0], 0, 1),)): -1j * a.conjugate()})
    raise KeyError(k)
