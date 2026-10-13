"""Whole-circuit verifier (L3): compiled circuit vs the ordered product of Trotter terms.

Contract checked on probe states:
  * system wires = wires used by the specification terms; they start in a random state supported
    on Fock levels <= n_probe (qumodes) and arbitrary qubit states;
  * every other wire the circuit touches is an ancilla, starting in |0> / vacuum;
  * the circuit output must equal (Π_k U_k)|ψ> ⊗ |ancillas = 0> up to one global phase that is the
    same for every probe (checked by using random superposition probes and comparing per-probe
    phases).
For physical circuits, logical wire w starts on physical wire w (Genesis' initial index mapping)
and ends on `final_map[w]`.

Reported per probe: `infid_strict` = 1 - |<target|out>|^2, `infid_sys` = 1 - <ψ_t|ρ_sys|ψ_t>
(tolerates ancilla garbage), `leak` = top-Fock-level population (truncation indicator), and the
phase spread across probes.  Run at two cutoffs; a result is trusted only if both agree.
"""
from __future__ import annotations

import numpy as np

from .sim import Register, run


def _random_probe(reg: Register, sys_wires, n_probe, rng):
    psi = np.zeros(reg.dims, dtype=complex)
    sub_dims = [2 if w[0] == "q" else n_probe + 1 for w in sys_wires]
    amp = rng.normal(size=sub_dims) + 1j * rng.normal(size=sub_dims)
    amp /= np.linalg.norm(amp)
    idx = [slice(None)] * len(reg.dims)
    for w, d in zip(sys_wires, sub_dims):
        idx[reg.index[w]] = slice(0, d)
    for i, w in enumerate(reg.wires):
        if w not in sys_wires:
            idx[i] = 0
    # place amp in the sub-block: system axes in register order
    order = [reg.index[w] for w in sys_wires]
    perm = np.argsort(order)
    psi[tuple(idx)] = np.transpose(amp, perm)
    return psi


def verify(terms, circ_ops, N: int, n_probe: int = 1, n_probes: int = 3, pad: int = 12,
           r_with_qubit: str = "cr", final_map=None, seed: int = 0, extra_wires=()):
    sys_wires = sorted({w for t in terms for w in t.wires} | set(extra_wires))
    circ_wires = sorted({w for o in circ_ops for w in o.wires})
    wires = sorted(set(sys_wires) | set(circ_wires) | set((final_map or {}).values()))
    reg = Register(wires, N)
    rng = np.random.default_rng(seed)
    Us = [(t.unitary(N, pad), t.wires) for t in terms]
    out = []
    for _ in range(n_probes):
        psi0 = _random_probe(reg, sys_wires, n_probe, rng)
        tgt = psi0
        for U, ws in Us:
            tgt = reg.apply(tgt, U, ws)
        got = run(reg, psi0, circ_ops, pad, r_with_qubit)
        leak = reg.leak(got)
        if final_map:
            # move logical wire w (now at physical final_map[w]) back to axis of w
            src = [reg.index[final_map[w]] for w in wires if w in final_map]
            dst = [reg.index[w] for w in wires if w in final_map]
            perm = [None] * len(wires)
            for s, d in zip(src, dst):
                perm[d] = s
            rest_src = [i for i in range(len(wires)) if i not in src]
            rest_dst = [i for i in range(len(wires)) if perm[i] is None]
            for s, d in zip(rest_src, rest_dst):  # unmapped (ancilla) wires: any bijection
                perm[d] = s
            got = np.transpose(got, perm)
        ov = np.vdot(tgt, got)
        # system-only fidelity: project ancillas onto anything, compare reduced system state
        sys_ax = [reg.index[w] for w in sys_wires]
        anc_ax = [i for i in range(len(wires)) if i not in sys_ax]
        t_sys = np.transpose(tgt, sys_ax + anc_ax).reshape(int(np.prod([reg.dims[i] for i in sys_ax])), -1)[:, 0]
        g = np.transpose(got, sys_ax + anc_ax).reshape(len(t_sys), -1)
        f_sys = float(np.sum(np.abs(t_sys.conj() @ g) ** 2))
        out.append({"infid_strict": float(1 - abs(ov) ** 2), "infid_sys": 1 - f_sys,
                    "phase": float(np.angle(ov)), "leak": leak,
                    "norm_out": float(np.linalg.norm(got))})
    phases = np.unwrap([o["phase"] for o in out])
    return {"N": N, "n_probe": n_probe, "wires": len(wires), "probes": out,
            "max_infid_strict": max(o["infid_strict"] for o in out),
            "max_infid_sys": max(o["infid_sys"] for o in out),
            "max_leak": max(o["leak"] for o in out),
            "phase_spread": float(np.ptp(phases)) if len(phases) > 1 else 0.0}
