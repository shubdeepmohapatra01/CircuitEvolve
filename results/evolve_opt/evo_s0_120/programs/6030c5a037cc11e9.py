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

    d = tools.pyzx_clifford_simp(tools.lower(circ))
    fd = tools.fold_resynth(tools.canonicalize(d))

    result = tools.best(best, fa, fb, fc, fbest, d, fd)

    if tools.time_left() > 60:
        blocked = tools.block_optimize(tools.canonicalize(result), method='fold_resynth')
        result = tools.best(result, blocked)

    if tools.time_left() > 30:
        blocked2 = tools.block_optimize(tools.canonicalize(result), method='pyzx')
        result = tools.best(result, blocked2)

    if tools.time_left() > 20:
        blocked3 = tools.block_optimize(tools.canonicalize(result), method='tket', passes="FullPeepholeOptimise")
        result = tools.best(result, blocked3)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(tools.canonicalize(result), method='resynth_1q')
        result = tools.best(result, blocked4)

    return result
