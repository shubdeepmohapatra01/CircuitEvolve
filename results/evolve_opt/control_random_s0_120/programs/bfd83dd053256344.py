"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.tket(circ, "FullPeepholeOptimiseNoSwaps"))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.block_optimize(cur, method="fold_resynth", block_size=4, max_gates=80)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
