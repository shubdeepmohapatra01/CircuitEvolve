def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    d = tools.pyzx_clifford_simp(lowered)

    candidates = [a, b, c, d]

    e = tools.pyzx_full_reduce(b)
    f = tools.tket(a, "FullPeepholeOptimise")
    g = tools.pyzx_full_reduce(c)
    h = tools.pyzx_teleport_reduce(a)
    candidates = candidates + [e, f, g, h]

    best = tools.best(candidates)
    folded = tools.fold_resynth(tools.canonicalize(best))
    candidates.append(folded)
    best = tools.best(candidates)

    if tools.time_left() > 40:
        blocked = tools.block_optimize(best, method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        best = tools.best(candidates)

    if tools.time_left() > 25:
        blocked2 = tools.block_optimize(best, method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        best = tools.best(candidates)

    if tools.time_left() > 15:
        blocked3 = tools.block_optimize(best, method='fold_resynth', block_size=2, max_gates=30)
        candidates.append(blocked3)
        best = tools.best(candidates)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(best, method='tket', block_size=4, max_gates=60)
        candidates.append(blocked4)
        best = tools.best(candidates)

    return best
