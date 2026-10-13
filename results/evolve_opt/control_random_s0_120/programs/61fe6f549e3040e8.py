"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.lower(circ))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.phase_fold(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.pyzx_full_reduce(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.pyzx_teleport_reduce(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "CliffordResynthesis")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "CliffordResynthesis")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.phase_fold(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
