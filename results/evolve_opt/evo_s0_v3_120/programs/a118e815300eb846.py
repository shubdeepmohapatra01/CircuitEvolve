"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    best = tools.best([a, b, c])
    folded = tools.fold_resynth(tools.canonicalize(best))
    candidate = tools.best([a, b, c, best, folded])

    if tools.time_left() > 40:
        blocked1 = tools.block_optimize(candidate, method='fold_resynth', block_size=3, max_gates=40)
        candidate = tools.best(candidate, blocked1)

    if tools.time_left() > 40:
        blocked2 = tools.block_optimize(candidate, method='tket', block_size=4, max_gates=60)
        candidate = tools.best(candidate, blocked2)

    if tools.time_left() > 40:
        blocked3 = tools.block_optimize(candidate, method='pyzx', block_size=3, max_gates=40)
        candidate = tools.best(candidate, blocked3)

    return candidate
