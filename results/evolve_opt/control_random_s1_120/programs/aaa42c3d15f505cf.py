"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.pyzx_teleport_reduce(tools.lower(circ)))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.tket(cur, "OptimisePhaseGadgets")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "KAKDecomposition")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
