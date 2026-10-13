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

    c = tools.pyzx_teleport_reduce(lowered)
    folded_c = tools.fold_resynth(tools.canonicalize(c))
    candidates.append(folded_c)

    top = tools.best(candidates)

    if tools.time_left() > 40:
        blocked = tools.block_optimize(tools.canonicalize(top), method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        top = tools.best(candidates)

    if tools.time_left() > 25:
        blocked2 = tools.block_optimize(top, method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        top = tools.best(candidates)

    if tools.time_left() > 15:
        blocked3 = tools.block_optimize(top, method='tket', block_size=4, max_gates=60)
        candidates.append(blocked3)
        top = tools.best(candidates)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(top, method='resynth_1q', block_size=2, max_gates=30)
        candidates.append(blocked4)

    return tools.best(candidates)
