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
    folded_d = tools.fold_resynth(tools.canonicalize(d))
    candidates.append(folded_d)

    e = tools.pyzx_full_reduce(b)
    folded_e = tools.fold_resynth(tools.canonicalize(e))
    candidates.append(folded_e)

    f = tools.pyzx_full_reduce(c)
    folded_f = tools.fold_resynth(tools.canonicalize(f))
    candidates.append(folded_f)

    g = tools.tket(a, "FullPeepholeOptimise")
    folded_g = tools.fold_resynth(tools.canonicalize(g))
    candidates.append(folded_g)

    h = tools.pyzx_teleport_reduce(b)
    folded_h = tools.fold_resynth(tools.canonicalize(h))
    candidates.append(folded_h)

    if tools.time_left() > 70:
        i = tools.pyzx_full_reduce(d)
        folded_i = tools.fold_resynth(tools.canonicalize(i))
        candidates.append(folded_i)

        j = tools.tket(d, "FullPeepholeOptimise")
        folded_j = tools.fold_resynth(tools.canonicalize(j))
        candidates.append(folded_j)

    top = tools.best(candidates)

    if tools.time_left() > 50:
        blocked = tools.block_optimize(tools.canonicalize(top), method='fold_resynth')
        candidates.append(blocked)
        top = tools.best(candidates)

    if tools.time_left() > 35:
        blocked2 = tools.block_optimize(top, method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        top = tools.best(candidates)

    if tools.time_left() > 20:
        blocked3 = tools.block_optimize(top, method='tket', block_size=4, max_gates=60)
        candidates.append(blocked3)
        top = tools.best(candidates)

    if tools.time_left() > 10:
        blocked4 = tools.block_optimize(top, method='resynth_1q', block_size=2, max_gates=30)
        candidates.append(blocked4)

    return tools.best(candidates)
