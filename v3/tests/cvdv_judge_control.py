"""Positive control for the CV-DV judge (run in env cvdv-opt; called by tests/test_p0.py).

    <cvdv-opt python> v3/tests/cvdv_judge_control.py <label> <out.cvdvqasm>

Compiles <label> with the cvdv project's certified term-by-term compiler (rulebook/rules.py, eps 1e-3, unrouted,
logical wires) and writes the circuit. This is NOT a baseline and not "ours": it only checks that a circuit known
to implement the Trotter step scores err_trotter ~ 0 under the judge.
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "cvdv")
sys.path.insert(0, os.path.join(ROOT, "experiments"))
import common as X  # noqa: E402
from cvdv import isa as ISA, qasm  # noqa: E402

label, out = sys.argv[1], sys.argv[2]
rules = X.load_rules(os.path.join(ROOT, "rulebook", "rules.py"))
_, ops, rep, _ = X.compile_bench(label, rules, eps=1e-3, n_max=3, isa=ISA.GENESIS)
qasm.write(qasm.Circuit(ops=list(ops)), out)
print(rep["eps_bound"])
