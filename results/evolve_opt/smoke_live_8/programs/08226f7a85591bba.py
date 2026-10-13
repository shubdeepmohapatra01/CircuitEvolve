"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)
    folded = tools.fold_resynth(tools.canonicalize(best))
    best = tools.best(best, folded)

    teleported = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(lowered)))
    best = tools.best(best, teleported)

    blocked = tools.block_optimize(tools.canonicalize(best), method='fold_resynth', block_size=3)
    best = tools.best(best, blocked)

    blocked2 = tools.block_optimize(tools.canonicalize(best), method='pyzx', block_size=4)
    best = tools.best(best, blocked2)

    blocked3 = tools.block_optimize(tools.canonicalize(best), method='resynth_1q', block_size=3)
    best = tools.best(best, blocked3)

    return best
