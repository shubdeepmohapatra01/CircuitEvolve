"""Expanded multi-pipeline search: try several classical+folding combinations and block-level
rewrites, keep the cheapest verified result."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)

    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    d = tools.pyzx_clifford_simp(lowered)

    best = tools.best([a, b, c, d])

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fc = tools.fold_resynth(tools.canonicalize(c))
    fd = tools.fold_resynth(tools.canonicalize(d))
    fbest = tools.fold_resynth(tools.canonicalize(best))

    candidate = tools.best([a, b, c, d, fa, fb, fc, fd, fbest])

    blocked1 = tools.block_optimize(candidate, method='fold_resynth', block_size=3)
    candidate = tools.best(candidate, blocked1)

    if tools.time_left() > 30:
        blocked1b = tools.block_optimize(candidate, method='fold_resynth', block_size=4)
        candidate = tools.best(candidate, blocked1b)

    if tools.time_left() > 30:
        blocked2 = tools.block_optimize(candidate, method='tket', block_size=3)
        candidate = tools.best(candidate, blocked2)

    if tools.time_left() > 30:
        blocked3 = tools.block_optimize(candidate, method='pyzx', block_size=3)
        candidate = tools.best(candidate, blocked3)

    if tools.time_left() > 30:
        blocked4 = tools.block_optimize(candidate, method='resynth_1q', block_size=2)
        candidate = tools.best(candidate, blocked4)

    return candidate
