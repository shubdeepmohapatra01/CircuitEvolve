"""Shared setup for interactive runs: paths, loaders, benchmark compile helper."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from cvdv import compiler as CO, library as L, metrics, qasm, target, terms as T  # noqa: E402

RES = os.path.join(ROOT, "results")
BASE = os.path.join(RES, "genesis_baseline")
SEEDED = os.path.join(RES, "genesis_seeded_s0")
SEED_LIB = os.path.join(ROOT, "libraries", "seed.py")
SMALL = ["kerr_small", "boseHubbard_small", "z2Higgs_small", "heisenberg_small",
         "electronicVibration_small", "hubbardHolstein_small"]


def intermediate(name):
    root = SEEDED if os.path.exists(f"{SEEDED}/{name}/intermediate_{name}.cvdvqasm") else BASE
    return target.read_intermediate(f"{root}/{name}/intermediate_{name}.cvdvqasm")


def sys_sizes(tl):
    ws = {w for t in tl for w in t.wires}
    nq = max([w[1] + 1 for w in ws if w[0] == "q"], default=0)
    nm = max([w[1] + 1 for w in ws if w[0] == "qm"], default=0)
    return nq, nm


def load_rules(path=SEED_LIB):
    return L.load(open(path).read())


def compile_bench(name, rules, eps=1e-3, n_max=2, r_max=4096, log=None, isa=None):
    tl = intermediate(name)
    nq, nm = sys_sizes(tl)
    kw = {} if isa is None else {"isa": isa}
    comp = CO.Compiler(rules, n_max=n_max, n_sys_q=nq, n_sys_m=nm, r_max=r_max, log=log, **kw)
    ops, rep = comp.compile_step(tl, eps_total=eps)
    return tl, ops, rep, comp
