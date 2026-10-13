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

    result = tools.canonicalize(result)

    if tools.time_left() > 80:
        ffbest = tools.fold_resynth(tools.canonicalize(result), max_iter=10)
        result = tools.canonicalize(tools.best(result, ffbest))

    if tools.time_left() > 60:
        blocked = tools.block_optimize(result, method='fold_resynth', block_size=3, max_gates=40)
        result = tools.canonicalize(tools.best(result, blocked))

    if tools.time_left() > 40:
        blocked2b = tools.block_optimize(result, method='fold_resynth', block_size=4, max_gates=60)
        result = tools.canonicalize(tools.best(result, blocked2b))

    if tools.time_left() > 30:
        blocked2 = tools.block_optimize(result, method='pyzx', block_size=3, max_gates=40)
        result = tools.canonicalize(tools.best(result, blocked2))

    if tools.time_left() > 20:
        blocked3 = tools.block_optimize(result, method='tket', block_size=3, max_gates=40)
        result = tools.canonicalize(tools.best(result, blocked3))

    if tools.time_left() > 10:
        extra = tools.fold_resynth(result)
        result = tools.canonicalize(tools.best(result, extra))

    return tools.canonicalize(result)
