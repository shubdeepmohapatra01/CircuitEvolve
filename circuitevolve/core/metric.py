"""T-count under BQSKit's error convention (plus rotation and CNOT counts).

Convention (bqskit-ft branch algorithmic_error_dpf @ 2e99ba614d48970b9afefc0b8c32860c3a3dc9f1,
alg_err_workflow.py, `compile_rz_to_clifft`): the circuit's remaining Rz gates are synthesized one by one
with gridsynth at

    eps_rz = eps_synth / N_Rz            (BQSKit: err_per_gate = success_threshold / num_rz_gates)

where eps_synth is the error budget reserved for final rotation synthesis (core/ledger.py) and N_Rz the
number of rotations that NEED synthesis. Rz at multiples of pi/4 are exact Clifford/T gates (odd multiples
cost one T). T-count = explicit T/Tdg + 1 per odd-pi/4 Rz + sum of gridsynth T-counts at eps_rz.

Details
  * gridsynth = pygridsynth 2.0.0 `gridsynth_gates` at mpmath dps 128 (blocks/cost_model.Gridsynth; every
    word is re-multiplied and checked: phase-aligned operator distance <= eps_rz). bqskit-ft itself calls
    rsgridsynth; same algorithm, word T-counts may differ by implementation details.
  * Angles are reduced to [-pi, pi] first (rz(x - 2pi) = -rz(x), a global phase).
  * N_Rz counts only rotations that are not multiples of pi/4. BQSKit's script counts every RZGate left
    after its Clifford+RZ lowering; that lowering already turns pi/4 multiples into Clifford/T gates.
  * Cache: one JSON file per eps value, keyed by repr(eps) (not `:g`, which would merge nearby eps values):
    .cache/blocks/bqskit_conv/gs_<repr(eps)>.json. Changing N_Rz changes eps_rz and so needs new gridsynth
    runs for every angle; calls are serial (no subprocesses, see circuitevolve/locks.py).
"""
from __future__ import annotations

from ..blocks.cost_model import CACHE_DIR, Gridsynth, ops_cost, rz_angles

CONV_CACHE = CACHE_DIR / "bqskit_conv"


class BqskitTMetric:
    """cost(ops) -> {'t', 't_fixed', 't_gs', 'rz', 'cx', 'gates', 'eps_rz', 'eps_synth'}."""

    def __init__(self, eps_synth: float, cache_dir=None):
        if not eps_synth > 0:
            raise ValueError("eps_synth must be > 0")
        self.eps_synth = float(eps_synth)
        self.cache_dir = cache_dir or CONV_CACHE
        self._gs: dict[str, Gridsynth] = {}

    def gridsynth(self, eps: float) -> Gridsynth:
        k = repr(float(eps))
        if k not in self._gs:
            self._gs[k] = Gridsynth(eps=float(eps), path=self.cache_dir / f"gs_{k}.json")
        return self._gs[k]

    def eps_rz(self, n_rz: int) -> float:
        return self.eps_synth / n_rz if n_rz > 0 else self.eps_synth

    def cost(self, ops, eps_rz: float | None = None) -> dict:
        """Cost of a whole circuit. eps_rz defaults to eps_synth / N_Rz(ops) (BQSKit convention); pass it
        explicitly to price a window at the enclosing circuit's eps_rz."""
        n_rz = len(rz_angles(ops))
        e = self.eps_rz(n_rz) if eps_rz is None else float(eps_rz)
        c = ops_cost(ops, self.gridsynth(e))
        c.update(eps_rz=e, eps_synth=self.eps_synth)
        return c

    def rotation_t(self, angles, eps_rz: float) -> list:
        """gridsynth T-count of each angle at eps_rz (angles already canonical)."""
        gs = self.gridsynth(eps_rz)
        gs.ensure(angles)
        return [gs.data[repr(float(a))][0] for a in angles]


def improves(new: dict, old: dict) -> bool:
    """Acceptance by MEASURED metric (documented in docs/CORE.md):
      1. T-count (BQSKit convention) must not increase;
      2. if the number of synthesized rotations changed, it must drop;
      3. same rotations: fewer explicit T (and fewer total T);
      4. same rotations and explicit T: same total T and fewer CNOT / gates.
    A rewrite whose only effect is different angles for the same number of rotations (gridsynth word-length
    "noise", typically +-4 T) is not an improvement - it would spend error budget on luck, not structure.
    Same rule as blocks/cost_model.improves, applied to BQSKit-convention costs."""
    from ..blocks.cost_model import improves as _imp
    return _imp(new, old)
