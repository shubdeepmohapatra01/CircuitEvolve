def optimize(circ, tools, budget):
    lowered = tools.lower(circ)

    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)

    best = tools.best([a, b, c])

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fc = tools.fold_resynth(tools.canonicalize(c))
    fbest = tools.fold_resynth(tools.canonicalize(best))

    candidate = tools.best([a, b, c, fa, fb, fc, fbest])

    if tools.time_left() > 60:
        blocked1 = tools.block_optimize(candidate, method='fold_resynth', block_size=3, max_gates=40)
        candidate = tools.best(candidate, blocked1)

    if tools.time_left() > 60:
        blocked2 = tools.block_optimize(candidate, method='tket', block_size=4, max_gates=60)
        candidate = tools.best(candidate, blocked2)

    if tools.time_left() > 60:
        blocked3 = tools.block_optimize(candidate, method='pyzx', block_size=3, max_gates=40)
        candidate = tools.best(candidate, blocked3)

    if tools.time_left() > 30:
        blocked4 = tools.block_optimize(candidate, method='resynth_1q', block_size=2, max_gates=20)
        candidate = tools.best(candidate, blocked4)

    return candidate
