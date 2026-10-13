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

    if tools.time_left() > 70:
        ffbest = tools.fold_resynth(result, max_iter=10)
        result = tools.canonicalize(tools.best(result, ffbest))

    if tools.time_left() > 60:
        pre = result
        blocked = tools.block_optimize(result, method='fold_resynth', block_size=3, max_gates=40)
        result = tools.canonicalize(tools.best(pre, blocked))

    if tools.time_left() > 30:
        pre = result
        blocked2 = tools.block_optimize(result, method='pyzx', block_size=3, max_gates=40)
        result = tools.canonicalize(tools.best(pre, blocked2))

    if tools.time_left() > 20:
        pre = result
        blocked3 = tools.block_optimize(result, method='tket', block_size=3, max_gates=40)
        result = tools.canonicalize(tools.best(pre, blocked3))

    if tools.time_left() > 10:
        pre = result
        extra = tools.fold_resynth(result)
        result = tools.canonicalize(tools.best(pre, extra))

    if tools.time_left() > 5:
        pre = result
        cs = tools.pyzx_clifford_simp(result)
        result = tools.canonicalize(tools.best(pre, cs))

    return result
