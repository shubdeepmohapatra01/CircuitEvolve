"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(tools.lower(circ))
    best = tools.best([a, b, c])

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fc = tools.fold_resynth(tools.canonicalize(c))
    folded = tools.fold_resynth(tools.canonicalize(best))

    candidates = [a, b, c, best, fa, fb, fc, folded]
    top = tools.best(candidates)

    blocked = tools.block_optimize(top, method='fold_resynth')
    candidates.append(blocked)

    if tools.time_left() > 20:
        blocked2 = tools.block_optimize(top, method='fold_resynth', block_size=5)
        candidates.append(blocked2)

    return tools.best(candidates)
