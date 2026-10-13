"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)

    fa = tools.fold_resynth(tools.canonicalize(a))
    fb = tools.fold_resynth(tools.canonicalize(b))
    fbest = tools.fold_resynth(tools.canonicalize(best))

    tr = tools.fold_resynth(tools.canonicalize(tools.pyzx_teleport_reduce(tools.lower(circ))))
    cs = tools.fold_resynth(tools.canonicalize(tools.pyzx_clifford_simp(tools.lower(circ))))

    candidate = tools.best([a, b, fa, fb, fbest, tr, cs])

    blocked = tools.block_optimize(candidate, method='fold_resynth')
    blocked2 = tools.block_optimize(blocked, method='fold_resynth')
    blocked_pyzx = tools.block_optimize(candidate, method='pyzx')

    return tools.best([candidate, blocked, blocked2, blocked_pyzx])
