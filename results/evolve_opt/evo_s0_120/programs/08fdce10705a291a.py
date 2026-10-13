"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


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

    if tools.time_left() > 30:
        pre = result
        blocked = tools.canonicalize(tools.block_optimize(pre, method='fold_resynth', block_size=3, max_gates=60))
        result = tools.best(pre, blocked)

    if tools.time_left() > 20:
        pre = result
        blocked2 = tools.canonicalize(tools.block_optimize(pre, method='pyzx', block_size=2, max_gates=40))
        result = tools.best(pre, blocked2)

    if tools.time_left() > 15:
        pre = result
        blocked3 = tools.canonicalize(tools.block_optimize(pre, method='tket', block_size=3, max_gates=90))
        result = tools.best(pre, blocked3)

    if tools.time_left() > 10:
        pre = result
        cs = tools.canonicalize(tools.pyzx_clifford_simp(pre))
        result = tools.best(pre, cs)

    if tools.time_left() > 15:
        pre = result
        tr = tools.pyzx_teleport_reduce(pre)
        trf = tools.fold_resynth(tools.canonicalize(tr))
        result = tools.best(pre, trf)

    if tools.time_left() > 10:
        pre = result
        allowance = tools.error_left(pre) * 0.05
        ar = tools.canonicalize(tools.approx_round(pre, allowance))
        fr = tools.fold_resynth(ar)
        result = tools.canonicalize(tools.best(pre, ar, fr))

    return tools.canonicalize(result)
