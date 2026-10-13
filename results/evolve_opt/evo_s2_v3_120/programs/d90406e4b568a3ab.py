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

    folded_a = tools.fold_resynth(tools.canonicalize(a))
    candidates.append(folded_a)

    folded_c = tools.fold_resynth(tools.canonicalize(c))
    candidates.append(folded_c)

    e = tools.pyzx_full_reduce(b)
    folded_e = tools.fold_resynth(tools.canonicalize(e))
    candidates.append(folded_e)

    f = tools.tket(c, "FullPeepholeOptimise")
    folded_f = tools.fold_resynth(tools.canonicalize(f))
    candidates.append(folded_f)

    best = tools.best(candidates)

    if tools.time_left() > 60:
        d = tools.pyzx_clifford_simp(lowered)
        folded_d = tools.fold_resynth(tools.canonicalize(d))
        candidates.append(folded_d)
        best = tools.best(candidates)

    if tools.time_left() > 45:
        blocked = tools.block_optimize(tools.canonicalize(best), method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        best = tools.best(candidates)

    if tools.time_left() > 30:
        blocked2 = tools.block_optimize(best, method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        best = tools.best(candidates)

    if tools.time_left() > 18:
        blocked3 = tools.block_optimize(best, method='tket', block_size=4, max_gates=60)
        candidates.append(blocked3)
        best = tools.best(candidates)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(best, method='resynth_1q', block_size=2, max_gates=30)
        candidates.append(blocked4)
        best = tools.best(candidates)

    return tools.best(candidates)
