"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    candidates = [a, b, c]

    best = tools.best(candidates)
    folded_best = tools.fold_resynth(tools.canonicalize(best))
    candidates.append(folded_best)

    folded_lowered = tools.fold_resynth(tools.canonicalize(lowered))
    candidates.append(folded_lowered)

    folded_c = tools.fold_resynth(tools.canonicalize(c))
    candidates.append(folded_c)

    e = tools.pyzx_full_reduce(b)
    folded_e = tools.fold_resynth(tools.canonicalize(e))
    candidates.append(folded_e)

    if tools.time_left() > 55:
        d = tools.pyzx_clifford_simp(lowered)
        folded_d = tools.fold_resynth(tools.canonicalize(d))
        candidates.append(folded_d)

    best = tools.best(candidates)

    if tools.time_left() > 45:
        blocked = tools.block_optimize(tools.canonicalize(tools.best(candidates)), method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)

    if tools.time_left() > 32:
        blocked2 = tools.block_optimize(tools.canonicalize(tools.best(candidates)), method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)

    if tools.time_left() > 20:
        blocked3 = tools.block_optimize(tools.canonicalize(tools.best(candidates)), method='tket', block_size=4, max_gates=60)
        candidates.append(blocked3)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(tools.canonicalize(tools.best(candidates)), method='resynth_1q', block_size=2, max_gates=30)
        candidates.append(blocked4)

    return tools.best(candidates)
