"""Benchmark specs: Genesis *_small IR (one Trotter step, t = 1, IR term order)."""
from . import paths  # noqa: F401  (sys.path shim for cvdv)
from cvdv import target, terms


def load_terms(label):
    return target.read_intermediate(str(paths.V3_INPUTS / f"{label}.ir.cvdvqasm"))


def hamiltonians(label):
    return [terms.hamiltonian_of(t) for t in load_terms(label)]
