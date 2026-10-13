"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.pyzx_full_reduce(tools.lower(circ)))
    except Exception:
        pass
    try:
        starts.append(tools.tket(circ, "FullPeepholeOptimise"))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.approx_round(cur, 1.0 * tools.error_left(cur))
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.block_optimize(cur, method="fold_resynth", block_size=2, max_gates=40)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "GreedyPauliSimp")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.block_optimize(cur, method="tket", block_size=2, max_gates=20)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
