"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)
    folded_best = tools.fold_resynth(tools.canonicalize(best))
    candidates = [best, folded_best]
    if tools.time_left() > 30:
        other = a if best is b else b
        folded_other = tools.fold_resynth(tools.canonicalize(other))
        candidates.append(folded_other)
    top = tools.best(candidates)
    if tools.time_left() > 20:
        blocked = tools.block_optimize(top, method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
    return tools.best(candidates)
