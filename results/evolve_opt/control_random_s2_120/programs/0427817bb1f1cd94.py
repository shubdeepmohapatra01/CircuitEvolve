"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.pyzx_full_reduce(tools.lower(circ)))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.tket(cur, "RemoveRedundancies")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.resynth_1q(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
