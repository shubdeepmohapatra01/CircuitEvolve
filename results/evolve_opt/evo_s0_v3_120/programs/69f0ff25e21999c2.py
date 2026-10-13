def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    t = tools.pyzx_teleport_reduce(lowered)
    c = tools.pyzx_clifford_simp(lowered)
    best = tools.best([a, b, t, c])

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    ft = tools.fold_resynth(tools.canonicalize(t))
    fc = tools.fold_resynth(tools.canonicalize(c))
    fl = tools.fold_resynth(tools.canonicalize(lowered))
    fbest = tools.fold_resynth(tools.canonicalize(best))

    tfb = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(b)))
    tft = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(t)))
    tfa = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(a)))
    tfbest = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(best)))
    candidate = tools.best([a, b, t, c, fa, fb, ft, fc, fl, fbest, tfb, tft, tfa, tfbest])

    if tools.time_left() > 40:
        blocked1 = tools.block_optimize(candidate, method='fold_resynth', block_size=3, max_gates=40)
        candidate = tools.best([candidate, blocked1])

    if tools.time_left() > 40:
        blocked2 = tools.block_optimize(candidate, method='tket', block_size=4, max_gates=60)
        candidate = tools.best([candidate, blocked2])

    if tools.time_left() > 40:
        blocked3 = tools.block_optimize(candidate, method='pyzx', block_size=3, max_gates=40)
        candidate = tools.best([candidate, blocked3])

    if tools.time_left() > 30:
        blocked4 = tools.block_optimize(candidate, method='fold_resynth', block_size=2, max_gates=30)
        candidate = tools.best([candidate, blocked4])

    if tools.time_left() > 20:
        blocked5 = tools.block_optimize(candidate, method='fold_resynth', block_size=4, max_gates=60)
        candidate = tools.best([candidate, blocked5])

    if tools.time_left() > 20:
        blocked6 = tools.block_optimize(candidate, method='pyzx', block_size=4, max_gates=100)
        candidate = tools.best([candidate, blocked6])

    if tools.time_left() > 15:
        blocked7 = tools.block_optimize(candidate, method='resynth_1q', block_size=3, max_gates=40)
        candidate = tools.best([candidate, blocked7])

    if tools.time_left() > 20:
        retele = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(candidate)))
        candidate = tools.best([candidate, retele])

    if tools.time_left() > 15:
        blocked8 = tools.block_optimize(candidate, method='fold_resynth', block_size=3, max_gates=40)
        candidate = tools.best([candidate, blocked8])

    return candidate
