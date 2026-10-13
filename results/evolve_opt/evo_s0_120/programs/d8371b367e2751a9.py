"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(tools.lower(circ))
    d = tools.pyzx_clifford_simp(tools.lower(circ))
    best = tools.best(a, b, c, d)
    folded = tools.fold_resynth(tools.canonicalize(best))
    result = tools.canonicalize(tools.best(best, folded))

    if tools.time_left() > 60:
        pre = result
        blocked = tools.block_optimize(pre, method='fold_resynth')
        result = tools.canonicalize(tools.best(pre, blocked))

    if tools.time_left() > 30:
        pre = result
        blocked2 = tools.block_optimize(pre, method='pyzx')
        result = tools.canonicalize(tools.best(pre, blocked2))

    if tools.time_left() > 15:
        pre = result
        extra = tools.fold_resynth(pre)
        result = tools.canonicalize(tools.best(pre, extra))

    if tools.time_left() > 10:
        pre = result
        allowance = tools.error_left(pre) * 0.3
        ar = tools.canonicalize(tools.approx_round(pre, allowance))
        fr = tools.fold_resynth(ar)
        result = tools.canonicalize(tools.best(pre, ar, fr))

    return result
