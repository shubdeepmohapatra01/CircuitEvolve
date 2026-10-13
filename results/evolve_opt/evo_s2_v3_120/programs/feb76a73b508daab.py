def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)

    candidates = [a, b, c]
    best = tools.best(candidates)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fc = tools.fold_resynth(tools.canonicalize(c))
    candidates.extend([fa, fb, fc])
    best = tools.best(candidates)

    if tools.time_left() > 60:
        d = tools.pyzx_clifford_simp(lowered)
        fd = tools.fold_resynth(tools.canonicalize(d))
        candidates.extend([d, fd])
        best = tools.best(candidates)

    if tools.time_left() > 50:
        blocked = tools.block_optimize(tools.canonicalize(best), method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        best = tools.best(candidates)

    if tools.time_left() > 35:
        blocked2 = tools.block_optimize(tools.canonicalize(best), method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        best = tools.best(candidates)

    if tools.time_left() > 20:
        blocked3 = tools.block_optimize(tools.canonicalize(best), method='tket', block_size=4, max_gates=60)
        candidates.append(blocked3)
        best = tools.best(candidates)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(tools.canonicalize(best), method='resynth_1q', block_size=2, max_gates=30)
        candidates.append(blocked4)
        best = tools.best(candidates)

    return best
