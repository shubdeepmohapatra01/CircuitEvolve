"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)

    folded_a = tools.fold_resynth(tools.canonicalize(a))
    folded_b = tools.fold_resynth(tools.canonicalize(b))
    folded_best = tools.fold_resynth(tools.canonicalize(best))

    candidate = tools.best(best, folded_a, folded_b, folded_best)

    if tools.time_left() > 20:
        blocked = tools.block_optimize(candidate, method='fold_resynth', block_size=3, max_gates=40)
        candidate = tools.best(candidate, blocked)

    return candidate
