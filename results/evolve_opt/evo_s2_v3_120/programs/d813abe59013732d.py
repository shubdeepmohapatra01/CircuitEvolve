"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)
    folded = tools.fold_resynth(tools.canonicalize(best))
    cand = tools.best(best, folded)
    blocked = tools.block_optimize(cand, method='fold_resynth', block_size=3, max_gates=40)
    cand = tools.best(cand, blocked)
    if tools.time_left() > 5:
        tele = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(tools.lower(circ))))
        cand = tools.best(cand, tele)
    return cand
