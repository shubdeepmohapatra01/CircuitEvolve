"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper. Plus extra candidates when time allows."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)
    folded = tools.fold_resynth(tools.canonicalize(best))
    candidates = [best, folded]
    top = tools.best(candidates)

    if tools.time_left() > 40:
        tr = tools.pyzx_teleport_reduce(lowered)
        folded_tr = tools.fold_resynth(tools.canonicalize(tr))
        candidates.append(folded_tr)
        top = tools.best(candidates)

    if tools.time_left() > 35:
        cs = tools.pyzx_clifford_simp(lowered)
        folded_cs = tools.fold_resynth(tools.canonicalize(cs))
        candidates.append(folded_cs)
        top = tools.best(candidates)

    if tools.time_left() > 20:
        blocked = tools.block_optimize(top, method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        top = tools.best(candidates)

    return top
