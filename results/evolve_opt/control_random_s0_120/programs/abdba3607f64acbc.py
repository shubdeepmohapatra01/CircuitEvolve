"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.pyzx_full_reduce(tools.lower(circ)))
    except Exception:
        pass
    try:
        starts.append(tools.tket(tools.pyzx_full_reduce(tools.lower(circ)), "FullPeepholeOptimise"))
    except Exception:
        pass
    try:
        starts.append(tools.pyzx_teleport_reduce(tools.lower(circ)))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.block_optimize(cur, method="fold_resynth", block_size=3, max_gates=40)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
