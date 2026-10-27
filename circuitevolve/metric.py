"""The metric: T-count of the FINAL Clifford+T circuit, i.e. after gridsynth, at a fixed total error budget.

Error budget (total EPS_TOTAL, the same for every arm and every baseline):
    DPF (arm L2 only)            spends at most EPS_DPF        (its own accounting, reported by dpf.dpf)
    LLM approximate rules        spend at most EPS_LLM in total (charged the verifier's MEASURED distance)
    gridsynth                    gets everything that is left, split evenly over the remaining arbitrary rz
So an approximate rule that removes rotations but spends budget can still raise the final T-count; the metric sees it.
Toffoli gates still present at the end are counted at 7 T each (their exact Clifford+T decomposition).
"""
from __future__ import annotations

from . import library
from .circuit import Circuit, counts

EPS_TOTAL = 1e-3
EPS_DPF = EPS_TOTAL / 2
EPS_LLM = EPS_TOTAL / 4


def final(c: Circuit, eps_used: float = 0.0) -> dict:
    """Synthesize c with the budget that is left and report the resources of the final circuit."""
    left = EPS_TOTAL - eps_used
    if left <= 0:
        raise ValueError(f"error budget exhausted: used {eps_used:.3e} of {EPS_TOTAL:.1e}")
    pre = counts(c)
    out = counts(library.gridsynth(c, left)) if pre["rz"] else pre
    return dict(t=out["t"] + 7 * out["toffoli"], qubits=c.n, rz=pre["rz"], measure=pre["measure"],
                eps_used=eps_used, eps_gridsynth=left if pre["rz"] else 0.0)


def t(c: Circuit, eps_used: float = 0.0) -> int:
    return final(c, eps_used)["t"]
