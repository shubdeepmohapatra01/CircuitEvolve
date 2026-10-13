"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)

    folded_a = tools.fold_resynth(tools.canonicalize(a))
    folded_b = tools.fold_resynth(tools.canonicalize(b))
    folded_best = tools.fold_resynth(tools.canonicalize(best))

    candidate = tools.best(best, folded_a, folded_b, folded_best)

    if tools.time_left() > 40:
        tr = tools.pyzx_teleport_reduce(tools.lower(circ))
        folded_tr = tools.fold_resynth(tools.canonicalize(tr))
        candidate = tools.best(candidate, tr, folded_tr)

    if tools.time_left() > 20:
        blocked = tools.block_optimize(candidate, method='fold_resynth', block_size=3, max_gates=40)
        candidate = tools.best(candidate, blocked)

    if tools.time_left() > 15:
        blocked2 = tools.block_optimize(candidate, method='pyzx', block_size=4, max_gates=60)
        candidate = tools.best(candidate, blocked2)

    if tools.time_left() > 10:
        blocked3 = tools.block_optimize(candidate, method='resynth_1q', block_size=2, max_gates=20)
        candidate = tools.best(candidate, blocked3)

    return candidate
