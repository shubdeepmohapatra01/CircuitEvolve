"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)
    folded_best = tools.fold_resynth(tools.canonicalize(best))
    candidates = [best, folded_best]
    if tools.time_left() > 30:
        other = a if best is b else b
        folded_other = tools.fold_resynth(tools.canonicalize(other))
        candidates.append(folded_other)
    if tools.time_left() > 40:
        tr = tools.pyzx_teleport_reduce(tools.lower(circ))
        folded_tr = tools.fold_resynth(tools.canonicalize(tr))
        candidates.append(tr)
        candidates.append(folded_tr)
    if tools.time_left() > 35:
        cs = tools.pyzx_clifford_simp(tools.lower(circ))
        folded_cs = tools.fold_resynth(tools.canonicalize(cs))
        candidates.append(folded_cs)
    top = tools.best(candidates)
    if tools.time_left() > 20:
        blocked = tools.block_optimize(top, method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        top = tools.best(candidates)
    if tools.time_left() > 12:
        blocked2 = tools.block_optimize(top, method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        top = tools.best(candidates)
    if tools.time_left() > 6:
        blocked3 = tools.block_optimize(top, method='resynth_1q', block_size=3, max_gates=40)
        candidates.append(blocked3)
    return tools.best(candidates)
