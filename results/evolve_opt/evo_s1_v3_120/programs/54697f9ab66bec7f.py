"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper. Adds teleport_reduce as a third base
candidate (often strong on phase-heavy circuits like QPE) and a final block_optimize pass."""


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
    if tools.time_left() > 25:
        tp = tools.pyzx_teleport_reduce(tools.lower(circ))
        tp_folded = tools.fold_resynth(tools.canonicalize(tp))
        candidates.append(tp_folded)
    top = tools.best(candidates)
    if tools.time_left() > 20:
        blocked = tools.block_optimize(top, method='fold_resynth', block_size=3, max_gates=40)
        candidates.append(blocked)
    return tools.best(candidates)
