def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)
    candidates = [a, b]

    folded = tools.fold_resynth(tools.canonicalize(best))
    candidates.append(folded)

    if tools.time_left() > 60:
        tr = tools.pyzx_teleport_reduce(lowered)
        folded_tr = tools.fold_resynth(tools.canonicalize(tr))
        candidates.append(tr)
        candidates.append(folded_tr)

    if tools.time_left() > 45:
        cs = tools.pyzx_clifford_simp(lowered)
        folded_cs = tools.fold_resynth(tools.canonicalize(cs))
        candidates.append(cs)
        candidates.append(folded_cs)

    top = tools.best(candidates)

    if tools.time_left() > 30:
        blocked = tools.block_optimize(top, method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        top = tools.best(candidates)

    if tools.time_left() > 20:
        blocked2 = tools.block_optimize(top, method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        top = tools.best(candidates)

    if tools.time_left() > 15:
        blocked3 = tools.block_optimize(top, method='resynth_1q', block_size=3, max_gates=40)
        candidates.append(blocked3)
        top = tools.best(candidates)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(top, method='tket', block_size=4, max_gates=60)
        candidates.append(blocked4)
        top = tools.best(candidates)

    if tools.time_left() > 8:
        blocked5 = tools.block_optimize(top, method='fold_resynth', block_size=2, max_gates=30)
        candidates.append(blocked5)

    return tools.best(candidates)
