"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(tools.lower(circ))
    best = tools.best(a, b, c)
    folded = tools.fold_resynth(tools.canonicalize(best))
    best = tools.best(best, folded)
    if tools.time_left() > 20:
        blocked = tools.block_optimize(best, method='fold_resynth', block_size=3, max_gates=40)
        best = tools.best(best, blocked)
    if tools.time_left() > 15:
        blocked2 = tools.block_optimize(best, method='pyzx', block_size=4, max_gates=60)
        best = tools.best(best, blocked2)
    return best
