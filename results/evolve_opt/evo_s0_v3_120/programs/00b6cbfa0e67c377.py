def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    t = tools.pyzx_teleport_reduce(lowered)
    cs = tools.pyzx_clifford_simp(lowered)
    best = tools.best([a, b, t, cs])

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    ft = tools.fold_resynth(tools.canonicalize(t))
    fcs = tools.fold_resynth(tools.canonicalize(cs))
    fbest = tools.fold_resynth(tools.canonicalize(best))
    fl = tools.fold_resynth(tools.canonicalize(lowered))

    candidate = tools.best([a, b, t, cs, fa, fb, ft, fcs, fbest, fl])

    if tools.time_left() > 60:
        blocked1 = tools.block_optimize(candidate, method='fold_resynth', block_size=3, max_gates=40)
        candidate = tools.best([candidate, blocked1])

    if tools.time_left() > 60:
        blocked2 = tools.block_optimize(candidate, method='tket', block_size=4, max_gates=60)
        candidate = tools.best([candidate, blocked2])

    if tools.time_left() > 50:
        blocked3 = tools.block_optimize(candidate, method='pyzx', block_size=3, max_gates=40)
        candidate = tools.best([candidate, blocked3])

    if tools.time_left() > 40:
        blocked4 = tools.block_optimize(candidate, method='fold_resynth', block_size=2, max_gates=30)
        candidate = tools.best([candidate, blocked4])

    if tools.time_left() > 30:
        blocked5 = tools.block_optimize(candidate, method='fold_resynth', block_size=4, max_gates=60)
        candidate = tools.best([candidate, blocked5])

    if tools.time_left() > 20:
        retele = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(candidate)))
        candidate = tools.best([candidate, retele])

    if tools.time_left() > 15:
        reclif = tools.fold_resynth(tools.canonicalize(tools.pyzx_clifford_simp(candidate)))
        candidate = tools.best([candidate, reclif])

    return candidate
