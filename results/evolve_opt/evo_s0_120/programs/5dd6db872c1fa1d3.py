"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(tools.lower(circ))
    best = tools.best(a, b, c)
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

    return result
