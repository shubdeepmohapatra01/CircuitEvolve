"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)
    folded = tools.fold_resynth(tools.canonicalize(best))
    candidates = [best, folded]

    lowered = tools.lower(circ)
    folded_lowered = tools.fold_resynth(tools.canonicalize(lowered))
    candidates.append(folded_lowered)

    top = tools.best(candidates)

    if tools.time_left() > 30:
        blocked = tools.block_optimize(tools.canonicalize(top), method='fold_resynth')
        candidates.append(blocked)

    return tools.best(candidates)
