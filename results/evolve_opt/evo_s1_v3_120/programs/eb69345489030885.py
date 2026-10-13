def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)
    folded_best = tools.fold_resynth(tools.canonicalize(best))
    candidates = [best, folded_best]
    if tools.time_left() > 40:
        other = a if best is b else b
        folded_other = tools.fold_resynth(tools.canonicalize(other))
        candidates.append(folded_other)
    if tools.time_left() > 35:
        tr = tools.pyzx_teleport_reduce(lowered)
        folded_tr = tools.fold_resynth(tools.canonicalize(tr))
        candidates.append(folded_tr)
    top = tools.best(candidates)
    if tools.time_left() > 20:
        blocked = tools.block_optimize(top, method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        top = tools.best(candidates)
    if tools.time_left() > 12:
        blocked2 = tools.block_optimize(top, method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
    return tools.best(candidates)
