def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    best = tools.best(a, b, c)

    candidates = [best]
    folded_a = tools.fold_resynth(tools.canonicalize(a))
    folded_b = tools.fold_resynth(tools.canonicalize(b))
    folded_c = tools.fold_resynth(tools.canonicalize(c))
    folded_best = tools.fold_resynth(tools.canonicalize(best))
    candidates.append(folded_a)
    candidates.append(folded_b)
    candidates.append(folded_c)
    candidates.append(folded_best)

    top = tools.best(candidates)

    if tools.time_left() > 60:
        d = tools.pyzx_clifford_simp(lowered)
        folded_d = tools.fold_resynth(tools.canonicalize(d))
        candidates.append(folded_d)
        top = tools.best(candidates)

    if tools.time_left() > 40:
        blocked1 = tools.block_optimize(top, method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked1)
        top = tools.best(candidates)

    if tools.time_left() > 30:
        blocked2 = tools.block_optimize(top, method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        top = tools.best(candidates)

    if tools.time_left() > 20:
        blocked3 = tools.block_optimize(top, method='resynth_1q', block_size=3, max_gates=40)
        candidates.append(blocked3)

    return tools.best(candidates)
