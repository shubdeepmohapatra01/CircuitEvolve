"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.tket(circ, "FullPeepholeOptimise"))
    except Exception:
        pass
    try:
        starts.append(tools.tket(tools.pyzx_full_reduce(tools.lower(circ)), "FullPeepholeOptimise"))
    except Exception:
        pass
    try:
        starts.append(tools.lower(circ))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.tket(cur, "PeepholeOptimise2Q")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.pyzx_full_reduce(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.phase_fold(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.phase_fold(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
