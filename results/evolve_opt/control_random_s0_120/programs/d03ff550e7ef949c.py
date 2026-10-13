"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.tket(tools.pyzx_full_reduce(tools.lower(circ)), "FullPeepholeOptimise"))
    except Exception:
        pass
    try:
        starts.append(tools.pyzx_full_reduce(tools.tket(circ, "FullPeepholeOptimise")))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.pyzx_basic(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
