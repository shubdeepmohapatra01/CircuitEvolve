"""Multi-seed best-of pipeline: combine pyzx full_reduce, tket FullPeepholeOptimise, pyzx
teleport_reduce, and clifford_simp as starting points, fold+resynth each, take the best,
then apply block_optimize as a final verified cleanup pass."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    d = tools.pyzx_clifford_simp(lowered)
    best = tools.best(a, b, c, d)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fc = tools.fold_resynth(tools.canonicalize(c))
    fd = tools.fold_resynth(tools.canonicalize(d))
    fbest = tools.fold_resynth(tools.canonicalize(best))

    candidate = tools.best(best, fa, fb, fc, fd, fbest)

    blocked = tools.block_optimize(candidate, method='fold_resynth')
    candidate2 = tools.best(candidate, blocked)

    blocked2 = tools.block_optimize(candidate2, method='pyzx')
    return tools.best(candidate2, blocked2)
