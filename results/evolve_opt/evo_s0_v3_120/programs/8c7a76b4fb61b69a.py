"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fbest = tools.fold_resynth(tools.canonicalize(best))

    tr = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(tools.lower(circ))))
    cs = tools.fold_resynth(tools.canonicalize(tools.pyzx_clifford_simp(tools.lower(circ))))

    candidate = tools.best([a, b, fa, fb, fbest, tr, cs])

    blocked = tools.block_optimize(candidate, method='fold_resynth')
    candidate = tools.best([candidate, blocked])

    if tools.time_left() > 40:
        blocked2 = tools.block_optimize(candidate, method='fold_resynth', block_size=3, max_gates=20)
        candidate = tools.best([candidate, blocked2])

    if tools.time_left() > 40:
        blocked_pyzx = tools.block_optimize(candidate, method='pyzx')
        candidate = tools.best([candidate, blocked_pyzx])

    if tools.time_left() > 30:
        reclif = tools.fold_resynth(tools.canonicalize(tools.pyzx_clifford_simp(candidate)))
        candidate = tools.best([candidate, reclif])

    if tools.time_left() > 30:
        blocked_tket = tools.block_optimize(candidate, method='tket', block_size=3, max_gates=20)
        candidate = tools.best([candidate, blocked_tket])

    if tools.time_left() > 20:
        retele = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(candidate)))
        candidate = tools.best([candidate, retele])

    return candidate
