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
    blocked2 = tools.block_optimize(candidate, method='pyzx')

    return tools.best([candidate, blocked1, blocked2])
