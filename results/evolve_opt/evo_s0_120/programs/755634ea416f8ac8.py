def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    base = tools.best(a, b)

    folded = tools.fold_resynth(tools.canonicalize(base))
    candidates = [base, folded]

    if tools.time_left() > 20:
        blocked = tools.block_optimize(folded, method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)

    if tools.time_left() > 10:
        folded_a = tools.fold_resynth(tools.canonicalize(a))
        folded_b = tools.fold_resynth(tools.canonicalize(b))
        candidates.append(folded_a)
        candidates.append(folded_b)

    return tools.best(candidates)
