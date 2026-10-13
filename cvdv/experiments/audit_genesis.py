"""Audit Genesis' synthesis rules and gadgets against the truncated-Fock simulator.

Writes results/genesis_audit.json.  Run from cvdv/ with env `cvdv-opt`:
    python experiments/audit_genesis.py
Checks:
  1. multi-Pauli exponential gadget (circuits.PauliNode.map_to_coupling_graph) for strings of
     weight 1-4: does every ancilla qumode return to vacuum, and which rotation angle results;
  2. per-term L1 synthesis (pattern_match_apply.main) for each distinct term shape of the small
     benchmarks, vs exp(term) at cutoffs 8 and 12;
  3. error scaling of the n^2 rule with angle (leading-order correctness).
"""
import contextlib
import io
import json
import os
import re
import sys

import numpy as np
from scipy.linalg import expm

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, os.path.join(HERE, "third_party", "genesis"))
from cvdv import qasm, sim, target, verify  # noqa: E402
import src.circuits as gc  # noqa: E402  (Genesis)
import src.graph_mapping as gm  # noqa: E402
import src.pattern_match_apply as pma  # noqa: E402


def gadget_ops(pstr, disp):
    g = gm.make_rectangle_graph(2, 2)
    mp = gm.Mapping(g)
    for i in range(4):
        mp.map_qubit(("q", i), ("q", i))
        mp.map_qubit(("qm", i), ("qm", i))
    out = gc.PauliNode(pstr, disp).map_to_coupling_graph(mp)
    return [qasm.parse_line(n.to_instr()) for n in out.get_sequence()]


def eff_qubit_unitary(ops, nq, N=12):
    wires = sorted({w for o in ops for w in o.wires} | {("q", i) for i in range(nq)})
    reg = sim.Register(wires, N)
    qax = [reg.index[("q", i)] for i in range(nq)]
    cols, vac = [], []
    for b in range(2 ** nq):
        psi = np.zeros(reg.dims, complex)
        idx = [0] * len(wires)
        for k in range(nq):
            idx[qax[k]] = (b >> (nq - 1 - k)) & 1
        psi[tuple(idx)] = 1
        out = sim.run(reg, psi, ops)
        v = out[tuple(slice(None) if w[0] == "q" else 0 for w in wires)]
        cols.append(v.reshape(-1))
        vac.append(float(np.linalg.norm(v) ** 2))
    return np.array(cols).T, vac


def audit_gadget(c=0.3j):
    rows = []
    for ps in ["ZIII", "ZZII", "ZZZI", "ZZZZ", "XIII", "XXII", "XXXI", "YYII", "YZII", "XYZI"]:
        nq = len(ps.rstrip("I"))
        U, vac = eff_qubit_unitary(gadget_ops(ps, c), nq)
        P = sim.kron(*[sim.PAULI[ch] for ch in ps[:nq]])
        row = {"pauli": ps, "min_vacuum_return": min(vac)}
        if min(vac) > 1 - 1e-9:
            cands = {"exp(c P) [spec]": expm(c * P),
                     "exp(+2i|c|^2 P)": expm(2j * abs(c) ** 2 * P),
                     "exp(-2i|c|^2 P)": expm(-2j * abs(c) ** 2 * P)}
            row["process_overlap"] = {k: float(abs(np.trace(v.conj().T @ U)) / 2 ** nq)
                                      for k, v in cands.items()}
        rows.append(row)
        print("gadget", row, flush=True)
    return rows


def genesis_term(expr, qb):
    with contextlib.redirect_stdout(io.StringIO()):
        res = pma.main(expr, qb)
    return [o for o in (qasm.parse_line(l) for l in res[1]) if o is not None]


def audit_terms(names, root):
    out = []
    for name in names:
        terms = target.read_intermediate(f"{root}/{name}/intermediate_{name}.cvdvqasm")
        nsysq = max([w[1] + 1 for t in terms for w in t.wires if w[0] == "q"], default=0)
        seen = set()
        for t in terms:
            if t.pauli is not None:
                continue
            expr = t.text.split(":", 1)[1].strip().rstrip(";")
            shape = re.sub(r"b\(\d+\)", "b(i)", re.sub(r"sigma\((\d), \d+\)", r"sigma(\1,q)", expr))
            if shape in seen:
                continue
            seen.add(shape)
            ops = genesis_term(expr, nsysq)
            res = {}
            for N in (8, 12):
                r = verify.verify([t], ops, N=N, n_probes=2, n_probe=2)
                res[N] = {k: r[k] for k in ("max_infid_strict", "max_infid_sys", "max_leak")}
            out.append({"benchmark": name, "term": expr, "n_ops": len(ops),
                        "two_op": sum(len(o.wires) > 1 for o in ops), "check": res})
            print(name, shape[:80], len(ops), res[12]["max_infid_strict"], flush=True)
    return out


def audit_n2_scaling():
    rows = []
    for th in [0.4, 0.2, 0.1, 0.05, 0.025]:
        expr = f"exp(prod(({-th}j),dagger(b(0)),b(0),dagger(b(0)),b(0)))"
        ops = genesis_term(expr, 1)
        t = target.Term((("qm", 0),), target.parse_sexpr(expr[4:-1]), None, expr)
        r = verify.verify([t], ops, N=12, n_probes=2, n_probe=2)
        rows.append({"theta": th, "infid_strict": r["max_infid_strict"], "infid_sys": r["max_infid_sys"]})
        print("n2", rows[-1], flush=True)
    return rows


if __name__ == "__main__":
    root = os.path.join(HERE, "results", "genesis_seeded_s0")
    report = {"gadget": audit_gadget(),
              "n2_scaling": audit_n2_scaling(),
              "terms": audit_terms(["boseHubbard_small", "z2Higgs_small"], root)}
    with open(os.path.join(HERE, "results", "genesis_audit.json"), "w") as f:
        json.dump(report, f, indent=1, default=str)
    print("wrote results/genesis_audit.json")
