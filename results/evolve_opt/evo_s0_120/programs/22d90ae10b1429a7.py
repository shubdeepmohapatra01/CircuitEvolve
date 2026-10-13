def optimize(circ, tools, budget):
    a = tools.canonicalize(tools.pyzx_full_reduce(tools.lower(circ)))
    b = tools.canonicalize(tools.tket(circ, "FullPeepholeOptimise"))
    c = tools.canonicalize(tools.pyzx_teleport_reduce(tools.lower(circ)))
    d = tools.canonicalize(tools.pyzx_clifford_simp(tools.lower(circ)))
    best = tools.best(a, b, c, d)

    fa = tools.canonicalize(tools.fold_resynth(a))
    fb = tools.canonicalize(tools.fold_resynth(b))
    fc = tools.canonicalize(tools.fold_resynth(c))
    fd = tools.canonicalize(tools.fold_resynth(d))
    fbest = tools.canonicalize(tools.fold_resynth(best))

    result = tools.best(best, fa, fb, fc, fd, fbest)

    if tools.time_left() > 60:
        blocked = tools.canonicalize(tools.block_optimize(result, method='fold_resynth'))
        result = tools.best(result, blocked)

    if tools.time_left() > 30:
        blocked2 = tools.canonicalize(tools.block_optimize(result, method='pyzx'))
        result = tools.best(result, blocked2)

    if tools.time_left() > 15:
        blocked3 = tools.canonicalize(tools.block_optimize(result, method='tket', passes="FullPeepholeOptimise"))
        result = tools.best(result, blocked3)

    return tools.canonicalize(result)
