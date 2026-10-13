"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    folded = tools.fold_resynth(tools.canonicalize(best))

    candidates = [a, b, best, fa, fb, folded]
    top = tools.best(candidates)

    blocked = tools.block_optimize(top, method='fold_resynth')
    candidates.append(blocked)

    return tools.best(candidates)
