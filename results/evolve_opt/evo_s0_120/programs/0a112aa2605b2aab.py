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

    if tools.time_left() > 60:
        blocked = tools.block_optimize(result, method='fold_resynth')
        result = tools.canonicalize(tools.best(result, blocked))

    if tools.time_left() > 30:
        blocked2 = tools.block_optimize(result, method='pyzx')
        result = tools.canonicalize(tools.best(result, blocked2))

    if tools.time_left() > 20:
        blocked3 = tools.block_optimize(result, method='tket')
        result = tools.canonicalize(tools.best(result, blocked3))

    if tools.time_left() > 10:
        extra = tools.fold_resynth(result)
        result = tools.canonicalize(tools.best(result, extra))

    if tools.time_left() > 5:
        cs = tools.pyzx_clifford_simp(result)
        result = tools.canonicalize(tools.best(result, cs))

    return tools.canonicalize(result)
