def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))

    candidates = [a, b, fa, fb]
    best = tools.best(candidates)

    if tools.time_left() > 50:
        blocked = tools.block_optimize(tools.canonicalize(best), method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        best = tools.best(candidates)

    if tools.time_left() > 30:
        blocked2 = tools.block_optimize(best, method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        best = tools.best(candidates)

    if tools.time_left() > 15:
        blocked3 = tools.block_optimize(best, method='tket', block_size=4, max_gates=60)
        candidates.append(blocked3)
        best = tools.best(candidates)

    return best
