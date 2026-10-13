"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(tools.lower(circ))
    best = tools.best(a, b, c)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fc = tools.fold_resynth(tools.canonicalize(c))
    fbest = tools.fold_resynth(tools.canonicalize(best))

    candidate = tools.best(best, fa, fb, fc, fbest)

    blocked = tools.block_optimize(candidate, method='fold_resynth')
    blocked2 = tools.block_optimize(candidate, method='fold_resynth', block_size=5)
    blocked3 = tools.block_optimize(tools.best(candidate, blocked, blocked2), method='pyzx', block_size=4)
    return tools.best(candidate, blocked, blocked2, blocked3)
