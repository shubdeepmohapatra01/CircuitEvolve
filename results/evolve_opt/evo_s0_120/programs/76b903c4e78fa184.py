"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(tools.lower(circ))
    best = tools.best(a, b, c)
    folded_a = tools.fold_resynth(tools.canonicalize(a))
    folded_b = tools.fold_resynth(tools.canonicalize(b))
    folded_c = tools.fold_resynth(tools.canonicalize(c))
    candidates = [a, b, c, folded_a, folded_b, folded_c, best]
    if tools.time_left() > 20:
        block = tools.block_optimize(tools.canonicalize(best), method='fold_resynth')
        candidates.append(block)
    return tools.best(candidates)
