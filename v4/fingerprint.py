"""The lever fingerprint - V4_README section 7. Deterministic, no LLM, once per (circuit, eps).

This is what stops the scout rediscovering a baseline. In v3's P2 it saw only a gate histogram, proposed
phase folding, and landed on pyzx's exact T-count: a correct idea with no headroom left.

Four levers, and who owns each:

  (a) **fewer rotations** - pyzx owns it. Rotations that provably merge (equal front-frame Pauli axis, or
      equal affine parity label in a Hadamard-free segment).
  (b) **cheaper angles** - DPF owns it. How many off-grid rotations sit EXACTLY on the k*pi/2^m grid.
      This is the sharp one, and measuring it explains DPF's whole result pattern:

        qft_8   45 of 48 off-grid angles exactly on the pi/2^7 grid  -> DPF 1064 at K*=7
        qae_13  85 at K=7, 112 of 145 at K=10                        -> DPF 4264 at K*=10
        qpe_8    6 of 257                                            -> K*=3, no angle lever at all
        hhl_8   24 of 583 (and 528 of them distinct)                 -> K*=3, no angle lever at all
        tfim_6   0 of 160 (only 5 distinct angles)                   -> DPF LOSES here (9600 vs 8560)

      So DPF's advantage on qft_8 and qae_13 does not come from snapping angles at all - their angles are
      already dyadic, because both circuits are built from controlled-phase ladders. Fixing is free; the
      T saving comes from lowering a FIXED dyadic Rz onto a phase-gradient register instead of sending it
      to gridsynth, which is the PKAC card (V4_README 4.2b) and needs `resource_class='measured'`.
      On qpe_8 and hhl_8 there is no angle lever, and DPF's win there is rotation-COUNT reduction per
      block. Two circuits, two different mechanisms, one baseline.
  (c) **algebraic structure** - NOBODY owns it. Majorana / free-fermion structure, and the dimension of
      the Lie algebra the rotation axes generate against the number of rotations.
  (d) **ancilla reconstruction** - relaxed rules only. CCZ count and shared control pairs.

    report(label, eps, book=None)  -> LeverReport     (on the circuit AFTER the book, which is what the
                                                       scout is shown)
    prefilter(card, report)        -> '' or the reason the card is rejected before any code is written
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field

from .api import dv, fermion, pauli, phasepoly
from .judge import dv as J

LEVERS = ("rotation_count", "angle_cost", "algebraic_structure", "ancilla_reconstruction")
GRID_TOL = 1e-9


@dataclass
class LeverReport:
    label: str
    eps: float
    family: str
    qubits: int
    n_ops: int
    current_t: int

    # (a) fewer rotations - pyzx owns this
    rotations: int = 0
    offgrid_rotations: int = 0
    distinct_angles: int = 0
    pauli_axis_classes: int = 0
    parity_classes: int = 0
    foldable: int = 0
    foldable_remaining: int = 0

    # (b) cheaper angles - DPF owns this
    exactly_dyadic: dict = field(default_factory=dict)      # level m -> how many off-grid angles land on it
    dyadic_fraction: dict = field(default_factory=dict)
    fixable_at_k: dict = field(default_factory=dict)        # level m -> how many fit inside eps/2 per angle

    # (c) algebraic structure - nobody owns this
    free_fermion: bool = False
    majorana_planes: int = 0
    generator_algebra_rank: int = 0

    # (d) ancilla reconstruction
    ccz_count: int = 0
    shared_control_pairs: int = 0

    # attribution
    best_baseline: str = ""
    best_baseline_t: int = 0
    lever_consumed_by: dict = field(default_factory=dict)
    residual: dict = field(default_factory=dict)

    def headroom(self, lever: str) -> int:
        """How much of `lever` is LEFT. A card whose lever has zero headroom cannot pay."""
        if lever == "rotation_count":
            return self.foldable_remaining
        if lever == "angle_cost":
            return max(self.exactly_dyadic.values(), default=0) + max(self.fixable_at_k.values(), default=0)
        if lever == "algebraic_structure":
            return max(0, self.offgrid_rotations - self.generator_algebra_rank) + (
                self.majorana_planes if self.free_fermion else 0)
        if lever == "ancilla_reconstruction":
            return self.ccz_count
        raise ValueError(f"unknown lever {lever!r}")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["headroom"] = {lv: self.headroom(lv) for lv in LEVERS}
        return d


def _angle_levers(angs, eps_each: float, levels=(2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14)) -> tuple:
    """(exactly_dyadic, dyadic_fraction, fixable_at_k) over the off-grid angles."""
    off = [a for a in angs if not dv.on_grid(a)]
    exact, frac, fix = {}, {}, {}
    for m in levels:
        step = math.pi / (1 << m)
        e = sum(1 for a in off if abs(a / step - round(a / step)) * step <= GRID_TOL)
        f = sum(1 for a in off
                if abs(math.sin((round(a / step) * step - a) / 2)) <= eps_each)
        exact[m], frac[m] = e, (e / len(off) if off else 0.0)
        fix[m] = f
    return exact, frac, fix


def _measured_foldable(circuit, fallback: int) -> int:
    """How many rotation merges the floor's own merge rules still find on THIS circuit.

    Measured, not estimated: the trigger pre-pass over the whole suite costs 0.48 s, so there is no
    reason to guess. Falls back to the class-size bound only if the floor cannot be loaded."""
    from . import book as B
    try:
        rules = [r for r in B.floor_tier() if "merge" in r.name]
        if not rules:
            return fallback
        return max(len(r.trigger(circuit)) for r in rules)
    except Exception:                                      # noqa: BLE001 (a missing floor is not fatal)
        return fallback


def report(label: str, eps: float = 1e-3, book=None, circuit=None, cost=None) -> LeverReport:
    """The fingerprint of the circuit AFTER `book` (default: the live book)."""
    from . import baselines as Ba, book as B
    from .memo import residual as _residual
    if circuit is None:
        bk = B.book() if book is None else book
        circuit, cost, _led = _residual(label, bk, eps)
    if cost is None:
        cost = J.measure(circuit) if J.is_exact(circuit) else J.measure(circuit, eps)
    d = __import__("v4.api", fromlist=["describe"]).describe(circuit)
    r = LeverReport(label=label, eps=eps, family=d.family, qubits=d.qubits, n_ops=d.n_ops,
                    current_t=int(cost["t_count"]))

    if d.family == "dv_angle":
        ops = list(circuit.ops)
        angs = [dv.rotation(op) for op in ops if dv.rotation(op) is not None]
        r.rotations = len(angs)
        r.offgrid_rotations = sum(1 for a in angs if not dv.on_grid(a))
        r.distinct_angles = len({round(dv.reduce_angle(a), 10) for a in angs if not dv.on_grid(a)})

        # ---- (a) rotation count. Two numbers, and they are not the same kind of thing.
        #
        # `foldable` is an UPPER BOUND from class sizes: a set of k rotations about one front-frame axis
        # can lose at most k-1 of them. It is loose, because merging two also needs everything between
        # them to commute with that axis.
        #
        # `foldable_remaining` is MEASURED: it runs the floor's own merge triggers on this circuit and
        # counts the matches they actually find. That is what "how much of this lever is left" means, and
        # it is what `headroom` uses. The estimate and the measurement disagree sharply, which is why the
        # measurement is the one that counts: on tfim_6 the class-size bound says 152 and the truth is 0 -
        # its axes repeat, but non-commuting rotations sit between every pair, so nothing merges. That 0
        # is the whole reason tfim_6 is the project's thesis row, and an estimate of 152 would have sent
        # the scout at the one lever that is empty there.
        #
        # Labels are also only comparable WITHIN one Hadamard-free segment - an earlier version pooled
        # them across segments, which is what produced the 152.
        recs = pauli.frames(ops)
        if recs is not None:
            axes = {}
            for rec in recs:
                axes.setdefault(rec.key, []).append(rec)
            r.pauli_axis_classes = len(axes)
            r.foldable = sum(len(v) - 1 for v in axes.values() if len(v) > 1)
        seg_classes, seg_foldable = 0, 0
        for lo, hi in dv.segments(ops, cut=("h",)):
            rl = phasepoly.rotation_labels(ops[lo:hi])
            if not rl:
                continue
            labs: dict = {}
            for _pos, _th, lab in rl:
                if lab[0]:
                    labs[lab] = labs.get(lab, 0) + 1
            seg_classes += len(labs)
            seg_foldable += sum(v - 1 for v in labs.values() if v > 1)
        r.parity_classes = seg_classes
        r.foldable_remaining = _measured_foldable(circuit, seg_foldable)

        # (b) angle cost - per-angle allowance if the whole rule share went to one angle each
        r.exactly_dyadic, r.dyadic_fraction, r.fixable_at_k = _angle_levers(
            angs, (eps / 2) / max(1, r.offgrid_rotations))

        # (c) algebraic structure
        r.free_fermion = fermion.is_gaussian(ops, d.qubits)
        r.majorana_planes = fermion.majorana_rank(ops, d.qubits)
        r.generator_algebra_rank = r.pauli_axis_classes          # distinct axes bound the algebra's rank
    else:
        r.ccz_count = d.toffoli
        pairs = {}
        for g in circuit.gates:
            if g.name in ("ccx", "ccz") and len(g.qubits) == 3:
                pairs.setdefault(tuple(sorted(g.qubits[:2])), 0)
                pairs[tuple(sorted(g.qubits[:2]))] += 1
        r.shared_control_pairs = sum(v - 1 for v in pairs.values() if v > 1)

    try:
        bb = Ba.best_baseline(label, eps)
        r.best_baseline, r.best_baseline_t = bb["method"], bb["t_count"]
    except KeyError:
        pass
    r.lever_consumed_by = dict(rotation_count="pyzx (and the floor tier reproduces it)",
                               angle_cost="DPF Synth", algebraic_structure="nobody",
                               ancilla_reconstruction="relaxed rules only")
    r.residual = dict(t_gap_to_best=r.current_t - r.best_baseline_t if r.best_baseline_t else None,
                      headroom={lv: r.headroom(lv) for lv in LEVERS})
    return r


# ------------------------------------------------------------------------------------------ prefilter
def prefilter(card: dict, rep: LeverReport) -> str:
    """'' if the card is worth implementing, else the reason - free, before any code is written.

    V4_README section 7: reject a card whose lever has zero remaining headroom; whose predicted gain
    exceeds the lever's computed upper bound; that duplicates an existing (lever, precondition)
    signature; or that proposes to improve rotation synthesis (gridsynth is within a small additive
    constant of optimal, so that lever has zero headroom by construction)."""
    lever = card.get("lever")
    if lever not in LEVERS:
        return f"card does not name one of the four levers {LEVERS} (got {lever!r})"
    if rep.headroom(lever) <= 0:
        return (f"lever {lever!r} has no headroom left on {rep.label} "
                f"(consumed by {rep.lever_consumed_by.get(lever)})")
    why = _proposes_better_synthesis(card)
    if why:
        return why
    est = card.get("expected_t_saving_on_target")
    if isinstance(est, (int, float)) and est > 0:
        if est > rep.current_t:
            return f"predicted saving {est} exceeds the circuit's whole T-count {rep.current_t}"
        bound = _lever_t_bound(lever, rep)
        if bound is not None and est > bound:
            return (f"predicted saving {est} exceeds the computed upper bound {bound} for lever "
                    f"{lever!r} on {rep.label}")
    return ""


# Improving the ROTATION SYNTHESISER has zero headroom (gridsynth is within a small additive constant of
# optimal), so V4_README section 7 asks the prefilter to reject cards that propose it. The test has to be
# precise, and the first version was not: it rejected any card whose text CONTAINED "gridsynth", which
# killed the best card the scout produced in the smoke run - the tfim_6 free-fermion idea, the one that
# gave -60.8% in v3 - because its cost estimate said "gridsynth's ~3*log2(1/eps_rz) cost per rotation
# falls slightly too". Merely reasoning about what gridsynth costs is not proposing to replace it.
#
# The asymmetry matters: a false positive burns a whole attempt AND loses a good idea, while a false
# negative costs one implementation attempt that the judge will settle. So this leans towards letting
# cards through: it fires only when an improvement verb sits next to the synthesiser, and never on a
# card whose lever is not `angle_cost` (the synthesiser IS the angle-cost lever).
_IMPROVE = r"(?:improv\w*|better|beat\w*|replac\w*|outperform\w*|superior|cheaper|optimal\w*|" \
           r"optimis\w*|optimiz\w*|our own|custom|new|hand-?written)"
_SYNTH = r"(?:grid\s?synth\w*|ross[-\s]?selinger|rotation synthesi[sz]\w*|synthesi[sz]\w* of (?:the )?" \
         r"(?:rz|rotations?)|rz synthesi[sz]\w*)"


def _proposes_better_synthesis(card: dict) -> str:
    import re
    if card.get("lever") != "angle_cost":
        return ""                      # the synthesiser is the angle-cost lever and nothing else
    text = " ".join(str(card.get(k, "")) for k in
                    ("identity", "idea", "expected_effect", "trigger", "correctness"))
    low = " ".join(text.lower().split())
    for pat in (rf"{_IMPROVE}\W{{0,24}}{_SYNTH}", rf"{_SYNTH}\W{{0,24}}(?:is |are )?{_IMPROVE}"):
        m = re.search(pat, low)
        if m:
            return ("proposes to improve rotation synthesis itself (matched "
                    f"{m.group(0)[:60]!r}): gridsynth is within a small additive constant of optimal, so "
                    "that lever has zero headroom by construction. Propose a rule that removes or "
                    "cheapens ROTATIONS, not one that synthesises them better.")
    return ""


def _lever_t_bound(lever: str, rep: LeverReport):
    """An upper bound on the T a lever can still save, from the fingerprint alone."""
    if not rep.offgrid_rotations:
        return 0
    per_rotation = rep.current_t / rep.offgrid_rotations          # mean T per synthesized rotation
    h = rep.headroom(lever)
    if lever in ("rotation_count", "angle_cost", "algebraic_structure"):
        return int(math.ceil(min(h, rep.offgrid_rotations) * per_rotation))
    return None


def signature(card: dict) -> tuple:
    """(lever, precondition) - two cards with the same signature are duplicates."""
    return (card.get("lever"), str(card.get("precondition", "")).strip().lower())


def write(label: str, path, eps: float = 1e-3, book=None) -> dict:
    d = report(label, eps, book).to_dict()
    from pathlib import Path
    Path(path).write_text(json.dumps(d, default=str, indent=1) + "\n")
    return d
