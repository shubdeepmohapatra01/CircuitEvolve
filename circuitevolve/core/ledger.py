"""Error ledger: one total algorithmic error eps per circuit, split by a fixed, documented v0 rule.

v0 rule
-------
    window pool   W = eps / 2     spent by ACCEPTED approximate window rewrites (and the input's distance)
    synthesis     S = eps / 2     final rotation synthesis, eps_rz = S / N_Rz per remaining rotation

  * Every accepted window rewrite is charged its MEASURED phase-aligned operator distance d_w from the frozen
    verifier (blocks/verify_block.verify_instance), not its allowance. Rewrites proved exact in D[omega]
    (verify_exact) are charged 0.
  * The distance of the TKET input to the original qseed circuit (measured by verify_block.circuit_check,
    ~1e-13, floating point only) is charged to W up front.
  * Allowance offered to the next rewrite: eps_w = min(remaining W, W * per_rewrite_fraction)
    (per_rewrite_fraction = 1/4 by default, so at least four approximate rewrites can be accepted).
  * Bound reported for a circuit:  d_input + sum_w d_w + N_Rz * eps_rz  <=  W + S = eps.
    Soundness: phase-aligned operator distance is subadditive under composition (triangle inequality +
    unitary invariance), and gridsynth's eps is the same operator-norm distance per rotation.
  * `reclaimed_eps_synth` = eps - d_input - sum_w d_w is what a final synthesis could use instead of S
    (returning unspent window budget); reported separately, never used for acceptance.

Comparison with BQSKit (alg_err_workflow.py @ 2e99ba6): its script gives the SAME eps to each of three stages
- Clifford+RZ angle collapse (eps / (num_params + 1) per parameter), DPF per block (eps / #blocks), and
gridsynth (eps / N_Rz per rotation) - so its additive bound is up to 3 eps while it is labelled eps; its
block checks use BQSKit's instantiation cost, which is <= our operator distance. B0/B1 (gridsynth only) are
bounded by eps. Our v0 bound is <= eps for the whole circuit, i.e. never looser than any of B0-B3.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Ledger:
    eps_total: float
    window_fraction: float = 0.5
    per_rewrite_fraction: float = 0.25
    d_input: float = 0.0
    spent: float = 0.0
    entries: tuple = field(default_factory=tuple)      # (call, window_index, mode, distance)

    @property
    def window_pool(self) -> float:
        return self.eps_total * self.window_fraction

    @property
    def eps_synth(self) -> float:
        return self.eps_total * (1.0 - self.window_fraction)

    @property
    def remaining(self) -> float:
        return max(0.0, self.window_pool - self.d_input - self.spent)

    def allowance(self) -> float:
        return min(self.remaining, self.window_pool * self.per_rewrite_fraction)

    def with_input(self, d_input: float) -> "Ledger":
        if not d_input <= self.window_pool:
            raise ValueError(f"input distance {d_input} exceeds the window pool {self.window_pool}")
        return replace(self, d_input=float(d_input))

    def can_charge(self, dist: float) -> bool:
        return dist <= self.remaining

    def charge(self, dist: float, call: int = -1, window: int = -1, mode: str = "") -> "Ledger":
        if not self.can_charge(dist):
            raise ValueError(f"charge {dist} exceeds remaining window budget {self.remaining}")
        return replace(self, spent=self.spent + float(dist), entries=self.entries + ((call, window, mode, float(dist)),))

    def bound(self, n_rz: int) -> float:
        """d_input + sum d_w + N_Rz * eps_rz with eps_rz = eps_synth / N_Rz."""
        return self.d_input + self.spent + (self.eps_synth if n_rz > 0 else 0.0)

    @property
    def reclaimed_eps_synth(self) -> float:
        return self.eps_total - self.d_input - self.spent

    def summary(self, n_rz: int) -> dict:
        return dict(eps_total=self.eps_total, window_pool=self.window_pool, eps_synth=self.eps_synth,
                    d_input=self.d_input, window_spent=self.spent, n_window_charges=len(self.entries),
                    eps_rz=(self.eps_synth / n_rz if n_rz else None), bound=self.bound(n_rz),
                    reclaimed_eps_synth=self.reclaimed_eps_synth, rule="v0: eps/2 windows, eps/2 synthesis")
