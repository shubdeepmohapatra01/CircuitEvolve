"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fbest = tools.fold_resynth(tools.canonicalize(best))

    candidate = tools.best([a, b, fa, fb, fbest])

    blocked = tools.block_optimize(candidate, method='fold_resynth')

    return tools.best(candidate, blocked)
