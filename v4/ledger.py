"""The shared error budget, per (circuit, eps) - V4_README section 8.

v3's accepted approx rules hard-coded TOL = 1e-10 and never spent the allowance they were given: one
five-millionth of eps/2 = 5e-4. DPF's whole advantage is that it *does* spend - snapping an angle onto the
dyadic grid is legal only because error was paid for it. So in v4 the budget is an object rules draw from,
the draw is recorded per rule per circuit, and how the 5e-4 is divided between rules becomes part of the
search space.

    led = Ledger(total=eps)                  # rule_share = synth_share = eps/2
    led.remaining                            # rule budget left
    led.draw('rule_name', amount)  -> bool   # True and recorded if it fits, False and unchanged if not
    led.refund('rule_name', amount)          # give back a draw whose application was reverted
    led.bound(n_rz)                          # sum(draws) + n_rz * eps_rz   = the number we report
    led.report()                             # per-rule draws, for the admission json

The bound is the triangle inequality over accepted rewrites (as in v3), so it is an upper bound on the
distance of the reported circuit from the original, and `bound(n_rz) <= eps` by construction.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class Overdraft(ValueError):
    pass


@dataclass
class Ledger:
    total: float
    rule_share: float = None            # type: ignore[assignment]
    synth_share: float = None           # type: ignore[assignment]
    draws: dict = field(default_factory=dict)

    def __post_init__(self):
        self.total = float(self.total)
        if self.rule_share is None:
            self.rule_share = self.total / 2
        if self.synth_share is None:
            self.synth_share = self.total - self.rule_share
        if self.rule_share < 0 or self.synth_share < 0 or self.rule_share + self.synth_share > self.total * (1 + 1e-12):
            raise ValueError("rule_share + synth_share must fit inside total")

    # ------------------------------------------------------------------ state
    @property
    def spent(self) -> float:
        return float(sum(self.draws.values()))

    @property
    def remaining(self) -> float:
        return max(0.0, self.rule_share - self.spent)

    def fits(self, amount: float) -> bool:
        return float(amount) <= self.remaining + 1e-18

    # ------------------------------------------------------------------ transactions
    def draw(self, rule: str, amount: float) -> bool:
        """Charge `amount` to `rule`. True if it fit (and was recorded), False if it did not (unchanged)."""
        a = float(amount)
        if a < 0:
            raise Overdraft(f"negative draw {a!r}")
        if not self.fits(a):
            return False
        self.draws[rule] = self.draws.get(rule, 0.0) + a
        return True

    def refund(self, rule: str, amount: float) -> None:
        """Return a draw whose application was reverted (the runner does this when a pass is bisected back)."""
        a = float(amount)
        have = self.draws.get(rule, 0.0)
        if a > have + 1e-18:
            raise Overdraft(f"refund {a!r} > {rule} draws {have!r}")
        left = have - a
        if left <= 1e-18:
            self.draws.pop(rule, None)
        else:
            self.draws[rule] = left

    # ------------------------------------------------------------------ reporting
    def eps_rz(self, n_rz: int) -> float | None:
        """Per-rotation synthesis budget: the UNSPENT part of the whole budget, split over n_rz rotations."""
        if not n_rz:
            return None
        return (self.total - self.spent) / int(n_rz)

    def bound(self, n_rz: int = 0) -> float:
        """sum(rule draws) + n_rz * eps_rz. Equals `total` when rotations remain, `spent` when none do."""
        if not n_rz:
            return self.spent
        return self.spent + int(n_rz) * self.eps_rz(n_rz)

    def report(self) -> dict:
        return dict(total=self.total, rule_share=self.rule_share, synth_share=self.synth_share,
                    spent=self.spent, remaining=self.remaining,
                    draws={k: v for k, v in sorted(self.draws.items())})

    def copy(self) -> "Ledger":
        return Ledger(self.total, self.rule_share, self.synth_share, dict(self.draws))
