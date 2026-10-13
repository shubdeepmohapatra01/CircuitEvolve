"""Best classical base + phase folding/resynth + block-level rewrites with multiple methods."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)
    candidates = [best]

    folded_best = tools.fold_resynth(tools.canonicalize(best))
    candidates.append(folded_best)

    if tools.time_left() > 60:
        other = a if best is b else b
        folded_other = tools.fold_resynth(tools.canonicalize(other))
        candidates.append(folded_other)

    if tools.time_left() > 40:
        tr = tools.pyzx_teleport_reduce(lowered)
        folded_tr = tools.fold_resynth(tools.canonicalize(tr))
        candidates.append(folded_tr)

    if tools.time_left() > 50:
        cs = tools.pyzx_clifford_simp(lowered)
        folded_cs = tools.fold_resynth(tools.canonicalize(cs))
        candidates.append(folded_cs)

    top = tools.best(candidates)

    if tools.time_left() > 30:
        blocked1 = tools.block_optimize(top, method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked1)
        top = tools.best(candidates)

    if tools.time_left() > 20:
        blocked2 = tools.block_optimize(top, method='pyzx', block_size=3, max_gates=40)
        candidates.append(blocked2)

    return tools.best(candidates)
