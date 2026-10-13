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
    pfl = tools.fold_resynth(tools.canonicalize(tools.phase_fold(lowered)))
    candidate = tools.best([a, b, t, c, fa, fb, ft, fc, fl, fbest, tfb, tft, tfa, pfl])

    if tools.time_left() > 20:
        retele = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(candidate)))
        candidate = tools.best([candidate, retele])

    if tools.time_left() > 15:
        reclif = tools.fold_resynth(tools.canonicalize(tools.pyzx_clifford_simp(candidate)))
        candidate = tools.best([candidate, reclif])

    if tools.time_left() > 15:
        retele2 = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(tools.pyzx_clifford_simp(candidate))))
        candidate = tools.best([candidate, retele2])

    return candidate
