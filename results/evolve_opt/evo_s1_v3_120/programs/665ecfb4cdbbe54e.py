def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    best = tools.best(a, b, c)

    folded_a = tools.fold_resynth(tools.canonicalize(a))
    folded_b = tools.fold_resynth(tools.canonicalize(b))
    folded_c = tools.fold_resynth(tools.canonicalize(c))
    folded_best = tools.fold_resynth(tools.canonicalize(best))

    candidate = tools.best(best, folded_a, folded_b, folded_c, folded_best)

    if tools.time_left() > 50:
        cs = tools.pyzx_clifford_simp(lowered)
        folded_cs = tools.fold_resynth(tools.canonicalize(cs))
        candidate = tools.best(candidate, folded_cs)

    if tools.time_left() > 30:
        blocked = tools.block_optimize(candidate, method='fold_resynth', block_size=3, max_gates=40)
        candidate = tools.best(candidate, blocked)

    if tools.time_left() > 25:
        blocked2 = tools.block_optimize(candidate, method='pyzx', block_size=4, max_gates=60)
        candidate = tools.best(candidate, blocked2)

    if tools.time_left() > 20:
        blocked3 = tools.block_optimize(candidate, method='tket', block_size=3, max_gates=40)
        candidate = tools.best(candidate, blocked3)

    return candidate
