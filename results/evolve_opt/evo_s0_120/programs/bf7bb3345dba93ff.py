def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(tools.lower(circ))
    d = tools.pyzx_clifford_simp(tools.lower(circ))
    best = tools.best(a, b, c, d)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fc = tools.fold_resynth(tools.canonicalize(c))
    fd = tools.fold_resynth(tools.canonicalize(d))
    fbest = tools.fold_resynth(tools.canonicalize(best))

    result = tools.best(best, fa, fb, fc, fd, fbest)

    if tools.time_left() > 60:
        blocked = tools.block_optimize(result, method='fold_resynth')
        result = tools.best(result, blocked)

    if tools.time_left() > 30:
        pre_blocked2 = tools.canonicalize(result)
        blocked2 = tools.block_optimize(pre_blocked2, method='pyzx')
        result = tools.best(pre_blocked2, result, blocked2)

    if tools.time_left() > 20:
        pre_blocked3 = tools.canonicalize(result)
        blocked3 = tools.block_optimize(pre_blocked3, method='tket', block_size=3)
        result = tools.best(pre_blocked3, result, blocked3)

    if tools.time_left() > 10:
        extra = tools.fold_resynth(tools.canonicalize(result))
        result = tools.best(result, extra)

    return tools.canonicalize(result)
