"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    lowered = tools.lower(circ)
    a = tools.pyzx_full_reduce(lowered)
    b = tools.tket(circ, "FullPeepholeOptimise")
    c = tools.pyzx_teleport_reduce(lowered)
    candidates = [a, b, c]
    folded_candidates = []
    for cand in candidates:
        f = tools.fold_resynth(tools.canonicalize(cand))
        folded_candidates.append(f)
    best = tools.best(candidates + folded_candidates)
    blocked = tools.block_optimize(best, method='fold_resynth')
    return tools.best(best, blocked)
