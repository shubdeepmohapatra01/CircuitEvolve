def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(tools.lower(circ))
    d = tools.pyzx_clifford_simp(tools.lower(circ))

    ca = tools.canonicalize(a)
    cb = tools.canonicalize(b)
    cc = tools.canonicalize(c)
    cd = tools.canonicalize(d)

    best = tools.best(ca, cb, cc, cd)

    fa = tools.fold_resynth(ca)
    fb = tools.fold_resynth(cb)
    fc = tools.fold_resynth(cc)
    fd = tools.fold_resynth(cd)
    fbest = tools.fold_resynth(best)

    result = tools.best(best, fa, fb, fc, fd, fbest)
    result = tools.canonicalize(result)

    if tools.time_left() > 60:
        blocked = tools.block_optimize(result, method='fold_resynth', block_size=3, max_gates=40)
        result = tools.best(result, tools.canonicalize(blocked))

    if tools.time_left() > 30:
        blocked2 = tools.block_optimize(result, method='pyzx', block_size=3, max_gates=40)
        result = tools.best(result, tools.canonicalize(blocked2))

    if tools.time_left() > 20:
        extra = tools.fold_resynth(result)
        result = tools.best(result, tools.canonicalize(extra))

    return tools.canonicalize(result)
