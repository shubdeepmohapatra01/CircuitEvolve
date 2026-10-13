"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    t = tools.pyzx_teleport_reduce(lowered)
    best = tools.best(a, b)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    ft = tools.fold_resynth(tools.canonicalize(t))
    fl = tools.fold_resynth(tools.canonicalize(lowered))
    fbest = tools.fold_resynth(tools.canonicalize(best))

    candidate = tools.best([a, b, t, fa, fb, ft, fl, fbest])

    blocked1 = tools.block_optimize(candidate, method='fold_resynth')
    candidate = tools.best([candidate, blocked1])

    if tools.time_left() > 30:
        blocked2 = tools.block_optimize(candidate, method='pyzx')
        candidate = tools.best([candidate, blocked2])

    if tools.time_left() > 30:
        blocked3 = tools.block_optimize(candidate, method='tket')
        candidate = tools.best([candidate, blocked3])

    if tools.time_left() > 30:
        blocked4 = tools.block_optimize(candidate, method='fold_resynth', block_size=2)
        candidate = tools.best([candidate, blocked4])

    if tools.time_left() > 30:
        blocked5 = tools.block_optimize(candidate, method='fold_resynth', block_size=4, max_gates=60)
        candidate = tools.best([candidate, blocked5])

    if tools.time_left() > 20:
        blocked6 = tools.block_optimize(candidate, method='pyzx', block_size=4, max_gates=60)
        candidate = tools.best([candidate, blocked6])

    if tools.time_left() > 20:
        blocked7 = tools.block_optimize(candidate, method='resynth_1q', block_size=3, max_gates=40)
        candidate = tools.best([candidate, blocked7])

    if tools.time_left() > 20:
        blocked8 = tools.block_optimize(candidate, method='fold_resynth', block_size=3, max_gates=100)
        candidate = tools.best([candidate, blocked8])

    return candidate
