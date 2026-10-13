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

    if tools.time_left() > 25:
        pre = result
        tr = tools.pyzx_teleport_reduce(pre)
        trf = tools.fold_resynth(tools.canonicalize(tr))
        result = tools.canonicalize(tools.best(pre, trf))

    if tools.time_left() > 20:
        pre = result
        blocked4 = tools.canonicalize(tools.block_optimize(pre, method='fold_resynth', block_size=2, max_gates=40))
        result = tools.canonicalize(tools.best(pre, blocked4))

    if tools.time_left() > 15:
        pre = result
        pr = tools.pyzx_full_reduce(pre)
        prf = tools.fold_resynth(tools.canonicalize(pr))
        result = tools.canonicalize(tools.best(pre, pr, prf))

    return tools.canonicalize(result)
