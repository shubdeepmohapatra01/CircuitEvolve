def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    candidates = [a, b, c]
    best = tools.best(candidates)

    folded = tools.fold_resynth(tools.canonicalize(best))
    candidates.append(folded)

    folded_lowered = tools.fold_resynth(tools.canonicalize(lowered))
    candidates.append(folded_lowered)

    e = tools.pyzx_full_reduce(b)
    folded_e = tools.fold_resynth(tools.canonicalize(e))
    candidates.append(folded_e)

    f = tools.pyzx_full_reduce(c)
    folded_f = tools.fold_resynth(tools.canonicalize(f))
    candidates.append(folded_f)

    best = tools.best(candidates)

    if tools.time_left() > 50:
        d = tools.pyzx_clifford_simp(lowered)
        folded_d = tools.fold_resynth(tools.canonicalize(d))
        candidates.append(folded_d)
        best = tools.best(candidates)

    if tools.time_left() > 35:
        blocked = tools.block_optimize(tools.canonicalize(best), method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        best = tools.best(candidates)

    if tools.time_left() > 20:
        blocked2 = tools.block_optimize(best, method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        best = tools.best(candidates)

    if tools.time_left() > 10:
        blocked3 = tools.block_optimize(best, method='tket', block_size=4, max_gates=60)
        candidates.append(blocked3)
        best = tools.best(candidates)

    return best
