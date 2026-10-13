def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    d = tools.pyzx_clifford_simp(lowered)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fc = tools.fold_resynth(tools.canonicalize(c))
    fd = tools.fold_resynth(tools.canonicalize(d))
    fl = tools.fold_resynth(tools.canonicalize(lowered))

    candidates = [a, b, c, d, fa, fb, fc, fd, fl]

    e = tools.pyzx_full_reduce(b)
    f = tools.tket(a, "FullPeepholeOptimise")
    fe = tools.fold_resynth(tools.canonicalize(e))
    ff = tools.fold_resynth(tools.canonicalize(f))
    candidates.extend([e, f, fe, ff])

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
        blocked3 = tools.block_optimize(top, method='resynth_1q', block_size=2, max_gates=30)
        candidates.append(blocked3)
        top = tools.best(candidates)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(top, method='tket', block_size=4, max_gates=60)
        candidates.append(blocked4)
        top = tools.best(candidates)

    return tools.best(candidates)
