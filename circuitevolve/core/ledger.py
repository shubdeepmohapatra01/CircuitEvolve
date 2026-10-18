"""Error ledger: one total algorithmic error eps per circuit.

v1 rule (DEFAULT since 2026-10-13, stage-1 runs): unspent window budget returns to rotation synthesis
-------------------------------------------------------------------------------------------------------
    window pool   W = pool_fraction * eps (cap, default eps/4); spent by ACCEPTED approximate window rewrites
    synthesis     S = eps - d_input - ceil_q(sum_w d_w)       (everything not spent on windows)
    eps_rz        = S / N_Rz for every remaining rotation

  * Every accepted window rewrite is charged its MEASURED phase-aligned operator distance d_w from the frozen
    verifier (blocks/verify_block.verify_instance); rewrites proved exact in D[omega] are charged 0.
  * ceil_q rounds the window spend UP to a multiple of q = eps * 2^-12 (only when it is > 0). This is
    conservative (S is never larger than eps - d_input - sum d_w) and makes nearby spends share one eps_rz value
    (one gridsynth cache file) instead of re-synthesising every rotation for every candidate.
  * d_input (distance of the TKET input to the original qseed circuit, floating point, ~1e-13) is taken from
    S. With no accepted rewrite, S = eps - d_input, i.e. the same eps_rz as B0 (TKET + gridsynth at eps/N_Rz)
    up to ~1e-13 relative; tests/test_core_window.py checks T == B0's t_count_canon on two circuits.
  * Allowance offered to the next rewrite: min(W - sum d_w, W * per_rewrite_fraction) (default eps/16).
  * Acceptance AND reported T both use eps_rz = S / N_Rz, so a rewrite that spends error budget must pay for the
    looser-to-tighter synthesis of every other rotation out of its own T saving (measured, not estimated).
  * Bound: d_input + sum_w d_w + N_Rz * eps_rz <= d_input + ceil_q(sum d_w) + S = eps.
    Soundness: phase-aligned operator distance is subadditive under composition (triangle inequality +
    unitary invariance), and gridsynth's eps is the same operator-norm distance per rotation.

v0 rule (rule="v0"; used by the smoke run results/window_runs/smoke_heisenberg_6_e3*)
-------------------------------------------------------------------------------------
    window pool W = eps/2, synthesis S = eps/2 fixed; d_input charged to W; allowance min(W left, W/4);
    `reclaimed_eps_synth` = eps - d_input - sum d_w was reported but never used for acceptance.

Comparison with BQSKit (alg_err_workflow.py @ 2e99ba6): its script gives the SAME eps to each of three stages
- Clifford+RZ angle collapse (eps / (num_params + 1) per parameter), DPF per block (eps / #blocks), and
gridsynth (eps / N_Rz per rotation) - so its additive bound is up to 3 eps while it is labelled eps; its
block checks use BQSKit's instantiation cost (HS), which is <= our operator distance. B0/B1 (gridsynth only)
are bounded by eps. Our bound is <= eps for the whole circuit under both rules.
"""
from __future__ import annotations

import math

from dataclasses import dataclass, field, replace


QUANTUM = 2.0 ** -12          # v1: window spend rounded up to multiples of eps * QUANTUM


@dataclass(frozen=True)
class Ledger:
    eps_total: float
    rule: str = "v1"
    window_fraction: float = 0.5           # v0 only: fixed split
    pool_fraction: float = 0.25            # v1 only: cap on the window pool
    per_rewrite_fraction: float = 0.25
    d_input: float = 0.0
    spent: float = 0.0
    entries: tuple = field(default_factory=tuple)      # (call, window_index, mode, distance)

    def __post_init__(self):
        if self.rule not in ("v0", "v1"):
            raise ValueError(f"unknown ledger rule {self.rule!r}")

    @property
    def window_pool(self) -> float:
        f = self.window_fraction if self.rule == "v0" else self.pool_fraction
        return self.eps_total * f

    @property
    def spent_rounded(self) -> float:
        """v1: window spend rounded up to a multiple of eps * QUANTUM (0 stays 0)."""
        if self.spent <= 0.0:
            return 0.0
        q = self.eps_total * QUANTUM
        return math.ceil(self.spent / q) * q

    @property
    def eps_synth(self) -> float:
        if self.rule == "v0":
            return self.eps_total * (1.0 - self.window_fraction)
        return self.eps_total - self.d_input - self.spent_rounded

    @property
    def remaining(self) -> float:
        if self.rule == "v0":
            return max(0.0, self.window_pool - self.d_input - self.spent)
        return max(0.0, self.window_pool - self.spent_rounded)

    def allowance(self) -> float:
        return min(self.remaining, self.window_pool * self.per_rewrite_fraction)

    def with_input(self, d_input: float) -> "Ledger":
        if not d_input <= self.window_pool:
            raise ValueError(f"input distance {d_input} exceeds the window pool {self.window_pool}")
        return replace(self, d_input=float(d_input))

    def can_charge(self, dist: float) -> bool:
        if self.rule == "v0":
            return dist <= self.remaining
        return replace(self, spent=self.spent + float(dist)).spent_rounded <= self.window_pool

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
        rule = ("v0: eps/2 windows, eps/2 synthesis" if self.rule == "v0" else
                f"v1: window pool cap {self.pool_fraction:g} eps, synthesis = eps - d_input - ceil_q(spent)")
        return dict(eps_total=self.eps_total, window_pool=self.window_pool, eps_synth=self.eps_synth,
                    d_input=self.d_input, window_spent=self.spent, window_spent_rounded=self.spent_rounded,
                    n_window_charges=len(self.entries),
                    eps_rz=(self.eps_synth / n_rz if n_rz else None), bound=self.bound(n_rz),
                    reclaimed_eps_synth=self.reclaimed_eps_synth, rule=rule)
