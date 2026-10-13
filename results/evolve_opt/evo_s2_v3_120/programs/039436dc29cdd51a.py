def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fc = tools.fold_resynth(tools.canonicalize(c))

    candidates = [a, b, c, fa, fb, fc]
    top = tools.best(candidates)

    if tools.time_left() > 60:
        d = tools.pyzx_clifford_simp(lowered)
        fd = tools.fold_resynth(tools.canonicalize(d))
        candidates.append(fd)
        top = tools.best(candidates)

    if tools.time_left() > 40:
        blocked = tools.block_optimize(tools.canonicalize(top), method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        top = tools.best(candidates)

    if tools.time_left() > 25:
        blocked2 = tools.block_optimize(top, method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        top = tools.best(candidates)

    if tools.time_left() > 15:
        blocked3 = tools.block_optimize(top, method='tket', block_size=4, max_gates=60)
        candidates.append(blocked3)
        top = tools.best(candidates)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(top, method='resynth_1q', block_size=2, max_gates=30)
        candidates.append(blocked4)
        top = tools.best(candidates)

    return tools.best(candidates)
