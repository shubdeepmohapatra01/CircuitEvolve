"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)

    folded_best = tools.fold_resynth(tools.canonicalize(best))
    best = tools.best(best, folded_best)

    folded_lowered = tools.fold_resynth(tools.canonicalize(lowered))
    best = tools.best(best, folded_lowered)

    if tools.time_left() > 20:
        blocked = tools.block_optimize(best, method='fold_resynth', block_size=3, max_gates=40)
        best = tools.best(best, blocked)

    return best
