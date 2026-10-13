def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    t = tools.pyzx_teleport_reduce(lowered)
    c = tools.pyzx_clifford_simp(lowered)
    best = tools.best([a, b, t, c])

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    ft = tools.fold_resynth(tools.canonicalize(t))
    fc = tools.fold_resynth(tools.canonicalize(c))
    fl = tools.fold_resynth(tools.canonicalize(lowered))
    fbest = tools.fold_resynth(tools.canonicalize(best))

    candidate = tools.best([a, b, t, c, fa, fb, ft, fc, fl, fbest])

    if tools.time_left() > 60:
        blocked1 = tools.block_optimize(candidate, method='fold_resynth', block_size=3, max_gates=40)
        candidate = tools.best([candidate, blocked1])

    if tools.time_left() > 50:
        blocked2 = tools.block_optimize(candidate, method='tket', block_size=4, max_gates=60)
        candidate = tools.best([candidate, blocked2])

    if tools.time_left() > 40:
        blocked3 = tools.block_optimize(candidate, method='pyzx', block_size=3, max_gates=40)
        candidate = tools.best([candidate, blocked3])

    if tools.time_left() > 30:
        blocked4 = tools.block_optimize(candidate, method='resynth_1q', block_size=3, max_gates=40)
        candidate = tools.best([candidate, blocked4])

    return candidate
