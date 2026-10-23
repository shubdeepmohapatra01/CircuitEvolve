"""CV-DV judge worker (FROZEN). Runs in env cvdv-opt; called only through v3/judge/cvdv.py (subprocess, JSON).

    <cvdv-opt python> v3/judge/cvdv_worker.py '<json request>'      -> one JSON object on stdout

Request: {"label", "circuit": path to a .cvdvqasm or v3 JSON op list (may hold IR-term placeholders),
          "mapping": optional run_genesis.py mapping.json, "reference": optional circuit (then err_ref = process
          infidelity of circuit vs reference on the probe subspace of the reference's wires), "what": ["metrics",
          "errors"]}. Metrics count synthesized gates only; placeholders are reported as `unsynthesized`.  Simulation parameters (spec IR, n_probe, cutoffs, exact_pad, probes)
come from v3/suite/manifest.json, never from the request, so every method is judged with the same probes.

Measure: cvdv/src/cvdv/metrics.py (1-op, 2-op, total, duration; equals Genesis --stats).
Errors, per cutoff N, both process infidelities 1 - |Tr(V^dag P0 U)/d|^2 on the probe subspace
S (system qumodes in Fock levels <= n_probe, system qubits arbitrary; d = dim S), P0 = every ancilla wire back
in |0> / vacuum (an ancilla left dirty lowers the fidelity):
  err_trotter : V = ordered product of the IR term unitaries (cvdv Term.unitary, as cvdv/verify.py);
  err_exact   : V = exp(sum_k G_k) = exp(-i H t) of the full Hamiltonian (sum of the IR term generators, t and r
                as in the IR), applied with scipy expm_multiply in a space with N + exact_pad levels per system
                qumode, then truncated to N levels.
d <= exact_basis_max_dim: exact, by enumerating the basis of S. Otherwise estimated over n_random seeded Haar
probes on S: |mean_k <t_k|P0 g_k>|^2 (unbiased for Tr(V^dag P0 U)/d up to the modulus). Also reported: worst
per-probe state infidelity, top-Fock leak. Results at the two cutoffs must agree (`cutoffs_agree`, rel. 10 %
or abs 1e-6) to be trusted.
"""
from __future__ import annotations

import itertools
import math
import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import expm_multiply

V3 = Path(__file__).resolve().parents[1]
REPO = V3.parent
sys.path.insert(0, str(REPO / "cvdv" / "src"))

from cvdv import metrics as M, qasm, target  # noqa: E402
from cvdv.sim import PAULI, Register, gate_matrix  # noqa: E402

MAX_AMPS = 1 << 25          # dense register limit (complex128: 512 MB per state)
PAD = 12                    # term / gate padding, as cvdv/verify.py


def _probes(sys_wires, n_probe, cfg):
    dims = [2 if w[0] == "q" else n_probe + 1 for w in sys_wires]
    d = int(np.prod(dims))
    if d <= cfg["exact_basis_max_dim"]:
        vecs = []
        for idx in itertools.product(*[range(k) for k in dims]):
            v = np.zeros(dims, dtype=complex)
            v[idx] = 1
            vecs.append(v)
        return dims, d, vecs, "basis-exact"
    rng = np.random.default_rng(cfg["seed"])
    vecs = []
    for _ in range(cfg["n_random"]):
        a = rng.normal(size=dims) + 1j * rng.normal(size=dims)
        vecs.append(a / np.linalg.norm(a))
    return dims, d, vecs, f"haar-{cfg['n_random']}"


def _embed(local, sys_wires, reg: Register, dims_local):
    """Place a system-only array (axes = sys_wires, dims_local) into the register (ancillas at 0)."""
    psi = np.zeros(reg.dims, dtype=complex)
    idx = [0] * len(reg.dims)
    for w, k in zip(sys_wires, dims_local):
        idx[reg.index[w]] = slice(0, k)
    order = [reg.index[w] for w in sys_wires]
    psi[tuple(idx)] = np.transpose(local, np.argsort(order))
    return psi


def _total_generator(terms, sys_wires, Mlev):
    """Sparse sum of term generators on the system space (axes = sys_wires, Mlev levels per qumode)."""
    dims = [2 if w[0] == "q" else Mlev for w in sys_wires]
    pos = {w: i for i, w in enumerate(sys_wires)}
    G = None
    for t in terms:
        if t.pauli is not None:
            c, label = t.pauli
            local = c * _kron([PAULI[ch] for ch in label if ch != "I"])
            ws = t.wires
        else:
            local, _ = t.generator(Mlev, 0)
            ws = t.wires
        # embed local operator on wires ws (sorted, as Term.wires) into the system space
        perm_axes = [pos[w] for w in ws]
        rest = [i for i in range(len(dims)) if i not in perm_axes]
        op = sp.kron(sp.csr_matrix(local), sp.identity(int(np.prod([dims[i] for i in rest])) if rest else 1,
                                                        dtype=complex, format="csr"), format="csr")
        # op acts on axis order perm_axes + rest; build permutation to natural order
        order = perm_axes + rest
        P = _perm_matrix(dims, order)
        op = P.T @ op @ P
        G = op if G is None else G + op
    return G.tocsr(), dims


def _kron(ms):
    out = np.array([[1.0 + 0j]])
    for m in ms:
        out = np.kron(out, m)
    return out


def _perm_matrix(dims, order):
    """Sparse P with P @ vec(natural order) = vec(axes permuted to `order`)."""
    n = int(np.prod(dims))
    idx = np.arange(n).reshape(dims)
    src = np.transpose(idx, order).reshape(-1)
    return sp.csr_matrix((np.ones(n), (np.arange(n), src)), shape=(n, n))


def _unpermute(got, reg, wires, final_map):
    """Move logical wire w (now on physical final_map[w]) back to the axis of w (as cvdv/verify.py)."""
    src = [reg.index[final_map[w]] for w in wires if w in final_map]
    dst = [reg.index[w] for w in wires if w in final_map]
    perm = [None] * len(wires)
    for s, d in zip(src, dst):
        perm[d] = s
    rest_src = [i for i in range(len(wires)) if i not in src]
    rest_dst = [i for i in range(len(wires)) if perm[i] is None]
    for s, d in zip(rest_src, rest_dst):
        perm[d] = s
    return np.transpose(got, perm + list(range(len(wires), got.ndim)))   # batch axes stay last


class TermOp:
    """Unsynthesized IR term placeholder (v3 JSON circuits): simulated exactly as the term's unitary."""

    def __init__(self, idx, terms):
        self.idx, self.name, self.wires = int(idx), "term", tuple(terms[int(idx)].wires)


def load_ops(path, terms):
    """.cvdvqasm (Genesis / ours, may hold Genesis `pauli` placeholders) or v3 JSON
    {"ops": [{"name", "params": [[re, im], ...], "wires": [["q"|"qm", i], ...]} | {"term": idx}]}."""
    if str(path).endswith(".json"):
        out = []
        for o in json.loads(Path(path).read_text())["ops"]:
            if "term" in o:
                out.append(TermOp(o["term"], terms))
            else:
                out.append(qasm.Op(o["name"], tuple(complex(a, b) for a, b in o.get("params", [])),
                                   tuple((w[0], int(w[1])) for w in o["wires"]), o.get("label", "")))
        return out
    return list(qasm.read(path).ops)


def metrics_of(ops) -> dict:
    """Genesis metrics over synthesized gates; `pauli` / term placeholders are counted, not priced."""
    native = [o for o in ops if o.name not in ("pauli", "term")]
    m = M.metrics(native)
    m["unsynthesized"] = len(ops) - len(native)
    m["complete"] = m["unsynthesized"] == 0
    return m


def simulate(reg, psi, ops, N, term_U):
    for o in ops:
        U = term_U[o.idx] if o.name == "term" else gate_matrix(o, N, PAD)
        psi = reg.apply(psi, U, o.wires)
    return psi


def errors(c, terms, ops, final_map, N, ref_ops=None):
    sys_wires = sorted({w for t in terms for w in t.wires}) if ref_ops is None else \
        sorted({w for o in ref_ops for w in o.wires})
    circ_wires = sorted({w for o in ops for w in o.wires})
    wires = sorted(set(sys_wires) | set(circ_wires) | set((final_map or {}).values()))
    reg = Register(wires, N)
    n_amps = math.prod(reg.dims)                 # python ints: np.prod overflows int64 here
    if n_amps > MAX_AMPS:
        return dict(N=N, status="too_large", amplitudes=n_amps, wires=len(wires))
    dims_p, d, probes, method = _probes(sys_wires, c["n_probe"], c["probes"])
    Us = [(t.unitary(N, PAD), t.wires) for t in terms]
    term_U = [U for U, _ in Us]
    if ref_ops is not None:          # reference-circuit mode: candidate vs another circuit on the same probes
        dims_p, d, probes, method = _probes(sys_wires, c["n_probe"], c["probes"])
        K = len(probes)
        psi0 = np.stack([_embed(v, sys_wires, reg, dims_p) for v in probes], axis=-1)
        t_ref = simulate(reg, psi0, ref_ops, N, term_U)
        got = simulate(reg, psi0, ops, N, term_U)
        o = np.einsum("ik,ik->k", t_ref.reshape(-1, K).conj(), got.reshape(-1, K))
        err = float(1 - abs(np.sum(o) / d) ** 2) if method == "basis-exact" else float(1 - abs(np.mean(o)) ** 2)
        return dict(N=N, status="ok", err_ref=err, worst_state_infid_ref=float(np.max(1 - np.abs(o) ** 2)),
                    probe_method=method, probe_dim=d, n_probes=K, amplitudes=n_amps, wires=len(wires))
    Mlev = N + c["exact_pad"]
    G, gdims = _total_generator(terms, sys_wires, Mlev)
    keep = tuple(slice(0, 2) if w[0] == "q" else slice(0, N) for w in sys_wires)
    # all probes at once: a trailing batch axis (Register.apply / run reshape to (d, -1), so it passes through)
    K = len(probes)
    psi0 = np.stack([_embed(v, sys_wires, reg, dims_p) for v in probes], axis=-1)
    t_tr = psi0
    for U, ws in Us:
        t_tr = reg.apply(t_tr, U, ws)
    big = np.zeros(tuple(gdims) + (K,), dtype=complex)
    big[tuple(slice(0, k) for k in dims_p)] = np.stack(probes, axis=-1)
    ex = expm_multiply(G, big.reshape(-1, K)).reshape(tuple(gdims) + (K,))[keep]
    ndims = [2 if w[0] == "q" else N for w in sys_wires]
    t_ex = np.stack([_embed(ex[..., k], sys_wires, reg, ndims) for k in range(K)], axis=-1)
    got = simulate(reg, psi0, ops, N, term_U)
    leak = reg.leak(got) / K                       # mean over probes of the top-Fock population
    if final_map:
        got = _unpermute(got, reg, wires, final_map)
    flat = lambda x: x.reshape(-1, K)
    o_tr = np.einsum("ik,ik->k", flat(t_tr).conj(), flat(got))
    o_ex = np.einsum("ik,ik->k", flat(t_ex).conj(), flat(got))
    worst_tr = float(np.max(1 - np.abs(o_tr) ** 2))
    worst_ex = float(np.max(1 - np.abs(o_ex) ** 2))
    f = (lambda o: float(1 - abs(np.sum(o) / d) ** 2)) if method == "basis-exact" else \
        (lambda o: float(1 - abs(np.mean(o)) ** 2))
    return dict(N=N, status="ok", err_trotter=f(o_tr), err_exact=f(o_ex), worst_state_infid_trotter=worst_tr,
                worst_state_infid_exact=worst_ex, mean_top_fock_leak=leak, probe_method=method, probe_dim=d,
                n_probes=len(probes), amplitudes=n_amps, wires=len(wires), exact_levels=Mlev)


def _agree(x, y):
    return abs(x - y) <= max(1e-6, 0.1 * max(abs(x), abs(y)))


def main():
    req = json.loads(sys.argv[1])
    man = json.loads((V3 / "suite" / "manifest.json").read_text())
    c = next(x for x in man["circuits"] if x["label"] == req["label"])
    terms = target.read_intermediate(str(V3 / c["spec"]))
    ops = load_ops(req["circuit"], terms)
    out = dict(label=req["label"], circuit=req["circuit"])
    if "metrics" in req.get("what", ["metrics"]):
        out["metrics"] = metrics_of(ops)
    if "errors" in req.get("what", []):
        fmap = None
        if req.get("mapping"):
            pairs = json.loads(Path(req["mapping"]).read_text())["final_log_to_phys"]
            fmap = {tuple(l): tuple(p) for l, p in pairs}
        ref_ops = load_ops(req["reference"], terms) if req.get("reference") else None
        res = [errors(c, terms, ops, fmap, N, ref_ops) for N in c["cutoffs"]]
        out["errors"] = res
        ok = [r for r in res if r["status"] == "ok"]
        keys = ("err_ref",) if ref_ops is not None else ("err_trotter", "err_exact")
        if len(ok) == len(res):
            a, b = ok
            out["cutoffs_agree"] = bool(all(_agree(a[k], b[k]) for k in keys))
            out.update({k: b[k] for k in keys})            # larger cutoff
        else:
            out["cutoffs_agree"] = None
        if any(o.name in ("pauli", "term") for o in ops):
            out["note"] = "circuit holds unsynthesized placeholders (simulated exactly as their term)"
    print(json.dumps(out))


if __name__ == "__main__":
    main()
