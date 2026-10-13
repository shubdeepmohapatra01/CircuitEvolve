"""Best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, plus staged block-local refinement, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fc = tools.fold_resynth(tools.canonicalize(c))

    candidates = [a, b, c, fa, fb, fc]
    best = tools.best(candidates)

    if tools.time_left() > 60:
        d = tools.pyzx_clifford_simp(lowered)
        fd = tools.fold_resynth(tools.canonicalize(d))
        candidates.append(d)
        candidates.append(fd)
        best = tools.best(candidates)

    if tools.time_left() > 45:
        blocked1 = tools.block_optimize(tools.canonicalize(best), method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked1)
        best = tools.best(candidates)

    if tools.time_left() > 30:
        blocked2 = tools.block_optimize(tools.canonicalize(best), method='pyzx', block_size=3, max_gates=40)
        candidates.append(blocked2)
        best = tools.best(candidates)

    if tools.time_left() > 15:
        blocked3 = tools.block_optimize(tools.canonicalize(best), method='resynth_1q', block_size=2, max_gates=30)
        candidates.append(blocked3)
        best = tools.best(candidates)

    return tools.best(candidates)
