"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.pyzx_full_reduce(tools.lower(circ)))
    except Exception:
        pass
    try:
        starts.append(tools.pyzx_full_reduce(tools.tket(circ, "FullPeepholeOptimise")))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.block_optimize(cur, method="pyzx", block_size=3, max_gates=40)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.fold_resynth(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
