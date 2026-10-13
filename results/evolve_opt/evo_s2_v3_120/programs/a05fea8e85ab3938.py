"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    candidates = [a, b, c]
    best = tools.best(candidates)
    folded = tools.fold_resynth(tools.canonicalize(best))
    candidates.append(folded)

    folded_a = tools.fold_resynth(tools.canonicalize(a))
    candidates.append(folded_a)
    folded_c = tools.fold_resynth(tools.canonicalize(c))
    candidates.append(folded_c)

    best = tools.best(candidates)

    if tools.time_left() > 60:
        d = tools.pyzx_clifford_simp(lowered)
        folded_d = tools.fold_resynth(tools.canonicalize(d))
        candidates.append(d)
        candidates.append(folded_d)
        best = tools.best(candidates)

    if tools.time_left() > 45:
        blocked = tools.block_optimize(tools.canonicalize(best), method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
        best = tools.best(candidates)
    if tools.time_left() > 30:
        blocked2 = tools.block_optimize(tools.canonicalize(best), method='pyzx', block_size=4, max_gates=60)
        candidates.append(blocked2)
        best = tools.best(candidates)
    if tools.time_left() > 15:
        blocked3 = tools.block_optimize(tools.canonicalize(best), method='resynth_1q', block_size=2, max_gates=30)
        candidates.append(blocked3)
        best = tools.best(candidates)
    return tools.best(candidates)
