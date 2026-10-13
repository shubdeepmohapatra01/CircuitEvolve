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

    if tools.time_left() > 60:
        pre = result
        blocked = tools.block_optimize(pre, method='fold_resynth')
        result = tools.canonicalize(tools.best(pre, blocked))

    if tools.time_left() > 40:
        pre = result
        blocked2 = tools.block_optimize(pre, method='pyzx')
        result = tools.canonicalize(tools.best(pre, blocked2))


    if tools.time_left() > 15:
        pre = result
        extra = tools.fold_resynth(pre)
        result = tools.canonicalize(tools.best(pre, extra))

    if tools.time_left() > 8:
        pre = tools.canonicalize(result)
        cs = tools.canonicalize(tools.pyzx_clifford_simp(pre))
        result = tools.canonicalize(tools.best(pre, cs))

    if tools.time_left() > 20:
        pre = tools.canonicalize(result)
        tr = tools.pyzx_teleport_reduce(pre)
        trf = tools.fold_resynth(tools.canonicalize(tr))
        result = tools.canonicalize(tools.best(pre, tools.canonicalize(trf)))

    if tools.time_left() > 15:
        pre = tools.canonicalize(result)
        pr = tools.canonicalize(tools.pyzx_full_reduce(pre))
        prf = tools.fold_resynth(pr)
        result = tools.canonicalize(tools.best(pre, pr, tools.canonicalize(prf)))

    if tools.time_left() > 10:
        pre = tools.canonicalize(result)
        allowance = tools.error_left(pre) * 0.05
        ar = tools.canonicalize(tools.approx_round(pre, allowance))
        fr = tools.canonicalize(tools.fold_resynth(ar))
        result = tools.canonicalize(tools.best(pre, ar, fr))

    return tools.canonicalize(result)
