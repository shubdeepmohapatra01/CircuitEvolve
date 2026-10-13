"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)
    folded = tools.fold_resynth(tools.canonicalize(best))
    candidate = tools.best(best, folded)

    if tools.time_left() > 40:
        tr = tools.pyzx_teleport_reduce(lowered)
        folded_tr = tools.fold_resynth(tools.canonicalize(tr))
        candidate = tools.best(candidate, folded_tr)

    if tools.time_left() > 45:
        cs = tools.pyzx_clifford_simp(lowered)
        folded_cs = tools.fold_resynth(tools.canonicalize(cs))
        candidate = tools.best(candidate, cs, folded_cs)

    if tools.time_left() > 30:
        blocked = tools.block_optimize(candidate, method='fold_resynth', block_size=3, max_gates=40)
        candidate = tools.best(candidate, blocked)

    if tools.time_left() > 20:
        blocked2 = tools.block_optimize(candidate, method='pyzx', block_size=4, max_gates=60)
        candidate = tools.best(candidate, blocked2)

    if tools.time_left() > 15:
        blocked3 = tools.block_optimize(candidate, method='resynth_1q', block_size=3, max_gates=40)
        candidate = tools.best(candidate, blocked3)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(candidate, method='tket', block_size=4, max_gates=60)
        candidate = tools.best(candidate, blocked4)

    if tools.time_left() > 8:
        blocked5 = tools.block_optimize(candidate, method='fold_resynth', block_size=2, max_gates=25)
        candidate = tools.best(candidate, blocked5)

    if tools.time_left() > 6:
        blocked6 = tools.block_optimize(candidate, method='pyzx', block_size=3, max_gates=50)
        candidate = tools.best(candidate, blocked6)

    return candidate
