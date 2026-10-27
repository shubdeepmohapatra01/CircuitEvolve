"""DPF floor card (V4_README 4.2): width-4 block refit that fixes Rz onto the dyadic grid, paid for from
the error ledger.

THE MECHANISM, as measured in the arm we built (experiments/bqskit_baselines/pk/dpf_pk.py, bqskit-ft
branch greedy_ntro @ c04a3224), not as it is usually described:

  DPF's k <= 3 win is NOT "snap angles to pi/8". Snapping an angle to the pi/4 grid costs an operator
  distance of up to |sin(pi/8)| = 0.38, and the whole rule budget is 5e-4, so almost no angle can be
  snapped on purpose. What `GreedyNTROPass(max_k, success_threshold = error / num_blocks)` actually does
  is re-synthesise each width-4 block so that FEWER of its rotations need gridsynth at all, accepting the
  block when its phase-aligned distance stays under error / num_blocks. On qpe_8 that takes N_Rz from
  268 to 126 - a halving of the rotation COUNT - and every T it saves comes from that, not from cheaper
  angles (b4_baseline.csv: t_explicit = 0, t_gridsynth = 7552 over 126 rotations).

So this card:

  1. partitions to width 4, dependency-contiguous (`blocks.partition`);
  2. gives each block an equal share `budget / B` of the error still left in the ledger;
  3. keeps the block's own Clifford / CNOT skeleton and frees its rotation angles;
  4. greedily pins angles onto the pi/4 grid - coarsest level first, nearest angle first - refitting all
     remaining free angles by least squares against the block's ORIGINAL unitary after each pin, and
     keeping a pin only while the block's phase-aligned distance stays inside its share;
  5. also tries pinning to 0 (deleting the rotation outright), which is the cheapest outcome of all;
  6. draws the distance it actually used from the ledger, and emits the block.

Every pinned angle is one rotation gridsynth no longer pays for, which is the T saving. The rewrite is
`approx` (it costs error, charged to the ledger) and `unitary` (no extra qubits, no measurement) - which
is exactly why v4 needs two contract tags: v3's single word would have called a 0-ancilla DPF result
"relaxed".

KNOWN GAP, reported rather than hidden: this card keeps each block's EXISTING CNOT skeleton. BQSKit's
GreedyNTRO re-synthesises the block numerically over a free CNOT ansatz (QSearch / LEAP class), which can
find a skeleton with fewer rotation slots than the block was written with. That is where the rest of
DPF's margin lives. See v4/BUILD_LOG.md P3.
"""
import math

from v4.api import Precondition, Rule
from v4.api import angles as A, blocks as BL, budget, dv, refit, sim

KMAX = 2                     # the pi/4 grid: the only grid the frozen metric prices as free
MAX_BLOCK_QUBITS = 4
MAX_FREE = 8                 # blocks with more free angles than this are skipped (the fit gets unreliable)
MIN_SHARE = 1e-12


def _skeleton(local_ops):
    """(pattern, angles, slots): the block's gate pattern with its rotation angles pulled out.

    t / tdg are rotations too - pinning one back onto the grid is a no-op, but freeing it lets the fit
    move error onto it and off a rotation that would otherwise need gridsynth."""
    pattern, angs, slots = [], [], []
    for i, op in enumerate(local_ops):
        th = dv.rotation(op)
        if th is None:
            pattern.append((op[0], tuple(op[1])))
        else:
            slots.append(len(angs))
            angs.append(float(th))
            pattern.append(("rz", tuple(op[1])))
    return pattern, angs, slots


def _n_offgrid(angs) -> int:
    return sum(1 for a in angs if not dv.on_grid(a))


def _fit_with(template, U, k, x0, pinned):
    return refit.least_squares(template, U, x0, n=k, pinned=pinned, max_nfev=400)


def _best_for_block(b: BL.Block, share: float):
    """(new local ops, distance, rotations removed) for one block, or None if nothing fits its share."""
    pattern, angs, _slots = _skeleton(b.local_ops)
    if not angs:
        return None
    free = [i for i, a in enumerate(angs) if not dv.on_grid(a)]
    if not free or len(free) > MAX_FREE:
        return None
    k = b.k
    U = sim.unitary(list(b.local_ops), k)
    template = refit.euler_template(k, pattern)
    pinned: dict = {}
    cur_angles, cur_dist = list(angs), 0.0
    # cheapest pins first: the angle already nearest the grid (and 0 is cheaper still - it deletes the op)
    order = sorted(free, key=lambda i: min(A.dyadic(angs[i], KMAX).distance, A.rz_distance(angs[i])))
    for i in order:
        for target in (0.0, A.dyadic(cur_angles[i], KMAX).angle):
            trial = dict(pinned)
            trial[i] = target
            f = _fit_with(template, U, k, cur_angles, trial)
            if f.distance <= share and _n_offgrid(f.angles) < _n_offgrid(cur_angles):
                pinned, cur_angles, cur_dist = trial, list(f.angles), f.distance
                break
    removed = _n_offgrid(angs) - _n_offgrid(cur_angles)
    if removed <= 0:
        return None
    return list(template(cur_angles)), float(cur_dist), removed


def find_matches(c):
    """One match per block that has at least one off-grid rotation and a share of the budget to spend.

    The trigger is deliberately cheap: it does NOT fit. The expensive part runs in `apply`, which the
    runner calls one match at a time and prices before verifying."""
    if not dv.is_angle_circuit(c):
        return []
    left = budget.remaining()
    if left <= MIN_SHARE:
        return []
    bs = [b for b in BL.partition(c, MAX_BLOCK_QUBITS)
          if b.k <= MAX_BLOCK_QUBITS and any(not dv.on_grid(dv.rotation(op))
                                             for op in b.local_ops if dv.rotation(op) is not None)]
    if not bs:
        return []
    share = left / len(bs)
    if share <= MIN_SHARE:
        return []
    # most off-grid rotations first: the blocks where a refit can remove the most
    bs.sort(key=lambda b: -sum(1 for op in b.local_ops
                               if dv.rotation(op) is not None and not dv.on_grid(dv.rotation(op))))
    return [(b.index, b.lo, b.hi, b.qubits, share) for b in bs]


def apply_match(c, m):
    index, lo, hi, qubits, share = m
    bs = BL.partition(c, MAX_BLOCK_QUBITS)
    b = next((x for x in bs if x.index == index and x.lo == lo and x.hi == hi and x.qubits == qubits),
             None)
    if b is None:
        return c
    got = _best_for_block(b, share)
    if got is None:
        return c
    new_local, dist, _removed = got
    if dist > 0 and not budget.draw(dist):
        return c                                  # the ledger refused: do nothing rather than overspend
    return dv.with_ops(c, BL.splice(list(c.ops), b, new_local))


RULE = Rule(
    name="dpf_dyadic_angle_fixing",
    domain="dv",
    kind="procedure",
    error_class="approx",
    resource_class="unitary",
    tier="floor",
    precondition=Precondition(families=("dv_angle",), needs=("nonclifford_rz",),
        note="refits width-4 blocks to put rotations on the pi/4 grid; needs off-grid rz to fix"),
    source="Kalloor et al., Dyadic Phase Fixing, arXiv:2606.05397 (QCE26); measured against bqskit-ft "
           "branch greedy_ntro @ c04a32245d88a0877277dccbcb8001cd85a7eef0 (GreedyNTROPass + "
           "ConvertToPKAC), our arm experiments/bqskit_baselines/pk/dpf_pk.py",
    idea="Partition to width 4 and give each block an equal share of the remaining error budget. Keep the "
         "block's Clifford skeleton, free its rotation angles, and greedily pin angles onto the pi/4 grid "
         "(or to 0, deleting the rotation), refitting the rest by least squares against the block's "
         "original unitary after each pin and keeping a pin only while the block's phase-aligned distance "
         "stays inside its share. Each pinned angle is one rotation gridsynth no longer pays for. The "
         "distance used is drawn from the shared ledger.",
    evidence=dict(
        baseline="DPF Synth (B4)",
        mechanism="measured: DPF k<=3's win is rotation-COUNT reduction per block (qpe_8 N_Rz 268 -> 126, "
                  "t_explicit 0, t_gridsynth 7552), not cheaper angles",
        known_gap="this card keeps each block's existing CNOT skeleton; BQSKit's GreedyNTRO re-synthesises "
                  "the block over a free CNOT ansatz, which is where the rest of DPF's margin lives"),
    trigger=find_matches,
    apply=apply_match,
)
