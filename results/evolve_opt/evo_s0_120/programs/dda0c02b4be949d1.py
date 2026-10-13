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

    if tools.time_left() > 30:
        pre = tools.canonicalize(result)
        blocked = tools.block_optimize(pre, method='fold_resynth')
        result = tools.best(pre, result, blocked)

    if tools.time_left() > 20:
        pre2 = tools.canonicalize(result)
        blocked2 = tools.block_optimize(pre2, method='pyzx')
        result = tools.best(pre2, result, blocked2)

    if tools.time_left() > 15:
        pre3 = tools.canonicalize(result)
        blocked3 = tools.block_optimize(pre3, method='tket')
        result = tools.best(pre3, result, blocked3)

    if tools.time_left() > 10:
        pre4 = tools.canonicalize(result)
        cs = tools.pyzx_clifford_simp(pre4)
        result = tools.best(pre4, result, cs)

    return result
