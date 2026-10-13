"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    best = tools.best(a, b, c)
    folded = tools.fold_resynth(tools.canonicalize(best))
    candidates = [best, folded]

    folded_lowered = tools.fold_resynth(tools.canonicalize(lowered))
    candidates.append(folded_lowered)

    folded_c = tools.fold_resynth(tools.canonicalize(c))
    candidates.append(folded_c)

    d = tools.pyzx_clifford_simp(lowered)
    candidates.append(d)
    folded_d = tools.fold_resynth(tools.canonicalize(d))
    candidates.append(folded_d)

    top = tools.best(candidates)

    if tools.time_left() > 50:
        blocked = tools.block_optimize(tools.canonicalize(top), method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        top = tools.best(candidates)

    if tools.time_left() > 35:
        blocked2 = tools.block_optimize(tools.canonicalize(top), method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        top = tools.best(candidates)

    if tools.time_left() > 20:
        blocked3 = tools.block_optimize(tools.canonicalize(top), method='tket', block_size=4, max_gates=60)
        candidates.append(blocked3)
        top = tools.best(candidates)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(tools.canonicalize(top), method='resynth_1q', block_size=2, max_gates=30)
        candidates.append(blocked4)
        top = tools.best(candidates)

    return tools.best(candidates)
