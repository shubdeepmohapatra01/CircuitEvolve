"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(tools.lower(circ))
    best = tools.best(a, b, c)
    folded_a = tools.fold_resynth(tools.canonicalize(a))
    folded_b = tools.fold_resynth(tools.canonicalize(b))
    folded_c = tools.fold_resynth(tools.canonicalize(c))
    candidates = [a, b, c, folded_a, folded_b, folded_c, best]
    result = tools.canonicalize(tools.best(candidates))

    if tools.time_left() > 30:
        pre = result
        block = tools.block_optimize(pre, method='fold_resynth', block_size=3, max_gates=60)
        result = tools.canonicalize(tools.best(pre, block))

    if tools.time_left() > 20:
        pre = result
        cs = tools.pyzx_clifford_simp(pre)
        result = tools.canonicalize(tools.best(pre, cs))

    if tools.time_left() > 20:
        pre = result
        tr = tools.pyzx_teleport_reduce(pre)
        trf = tools.fold_resynth(tools.canonicalize(tr))
        result = tools.canonicalize(tools.best(pre, trf))

    if tools.time_left() > 15:
        pre = result
        pr = tools.pyzx_full_reduce(pre)
        prf = tools.fold_resynth(tools.canonicalize(pr))
        result = tools.canonicalize(tools.best(pre, pr, prf))

    if tools.time_left() > 10:
        pre = result
        allowance = tools.error_left(pre) * 0.05
        ar = tools.canonicalize(tools.approx_round(pre, allowance))
        fr = tools.fold_resynth(ar)
        result = tools.canonicalize(tools.best(pre, ar, fr))

    return tools.canonicalize(result)
