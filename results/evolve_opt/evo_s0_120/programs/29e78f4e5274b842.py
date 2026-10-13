def optimize(circ, tools, budget):
    lowered = tools.lower(circ)

    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)

    c = tools.fold_resynth(tools.canonicalize(best))
    best = tools.best(best, c)

    if tools.time_left() > 30:
        d = tools.pyzx_teleport_reduce(lowered)
        d2 = tools.fold_resynth(tools.canonicalize(d))
        best = tools.best(best, d2)

    if tools.time_left() > 20:
        e = tools.block_optimize(best, method='fold_resynth', block_size=3, max_gates=40)
        best = tools.best(best, e)

    if tools.time_left() > 15:
        f = tools.block_optimize(best, method='pyzx', block_size=4, max_gates=60)
        best = tools.best(best, f)

    return best
