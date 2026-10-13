"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    best = tools.best(a, b, c)
    folded = tools.fold_resynth(tools.canonicalize(best))
    candidates = [best, folded]

    e = tools.pyzx_full_reduce(b)
    folded_e = tools.fold_resynth(tools.canonicalize(e))
    candidates.append(folded_e)

    top = tools.best(candidates)

    if tools.time_left() > 65:
        d = tools.pyzx_clifford_simp(lowered)
        folded_d = tools.fold_resynth(tools.canonicalize(d))
        candidates.append(folded_d)
        top = tools.best(candidates)

    if tools.time_left() > 55:
        blocked = tools.block_optimize(tools.canonicalize(top), method='fold_resynth')
        candidates.append(blocked)
        top = tools.best(candidates)

    if tools.time_left() > 38:
        blocked2 = tools.block_optimize(top, method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        top = tools.best(candidates)

    if tools.time_left() > 22:
        blocked3 = tools.block_optimize(top, method='tket', block_size=4, max_gates=60)
        candidates.append(blocked3)
        top = tools.best(candidates)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(top, method='resynth_1q', block_size=2, max_gates=30)
        candidates.append(blocked4)

    return tools.best(candidates)
