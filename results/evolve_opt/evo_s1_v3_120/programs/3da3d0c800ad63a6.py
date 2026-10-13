"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)
    folded_best = tools.fold_resynth(tools.canonicalize(best))
    candidates = [best, folded_best]

    other = a if best is b else b
    folded_other = tools.fold_resynth(tools.canonicalize(other))
    candidates.append(folded_other)

    if tools.time_left() > 40:
        c = tools.pyzx_teleport_reduce(lowered)
        folded_c = tools.fold_resynth(tools.canonicalize(c))
        candidates.append(folded_c)

    top = tools.best(candidates)

    if tools.time_left() > 30:
        blocked = tools.block_optimize(top, method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)

    if tools.time_left() > 20:
        blocked2 = tools.block_optimize(tools.best(candidates), method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)

    if tools.time_left() > 12:
        blocked3 = tools.block_optimize(tools.best(candidates), method='tket', block_size=3, max_gates=40)
        candidates.append(blocked3)

    return tools.best(candidates)
