"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(tools.lower(circ))
    best = tools.best(a, b, c)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fc = tools.fold_resynth(tools.canonicalize(c))
    fbest = tools.fold_resynth(tools.canonicalize(best))

    result = tools.best(best, fa, fb, fc, fbest)

    result = tools.canonicalize(result)

    if tools.time_left() > 30:
        blocked = tools.canonicalize(tools.block_optimize(result, method='fold_resynth'))
        result = tools.best(result, blocked)

    if tools.time_left() > 20:
        blocked2 = tools.canonicalize(tools.block_optimize(result, method='pyzx'))
        result = tools.best(result, blocked2)

    if tools.time_left() > 15:
        blocked3 = tools.canonicalize(tools.block_optimize(result, method='tket'))
        result = tools.best(result, blocked3)

    if tools.time_left() > 10:
        cs = tools.canonicalize(tools.pyzx_clifford_simp(result))
        result = tools.best(result, cs)

    result = tools.canonicalize(result)

    if tools.time_left() > 8:
        pre = result
        allowance = tools.error_left(pre) * 0.08
        ar = tools.canonicalize(tools.approx_round(pre, allowance))
        fr = tools.canonicalize(tools.fold_resynth(ar))
        result = tools.canonicalize(tools.best(pre, ar, fr))

    return tools.canonicalize(result)
