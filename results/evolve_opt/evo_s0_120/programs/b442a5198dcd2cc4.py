"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.canonicalize(tools.pyzx_full_reduce(tools.lower(circ)))
    b = tools.canonicalize(tools.tket(circ, "FullPeepholeOptimise"))
    c = tools.canonicalize(tools.pyzx_teleport_reduce(tools.lower(circ)))
    best = tools.best(a, b, c)

    fa = tools.canonicalize(tools.fold_resynth(a))
    fb = tools.canonicalize(tools.fold_resynth(b))
    fc = tools.canonicalize(tools.fold_resynth(c))
    fbest = tools.canonicalize(tools.fold_resynth(best))

    result = tools.best(best, fa, fb, fc, fbest)

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

    return tools.canonicalize(result)
