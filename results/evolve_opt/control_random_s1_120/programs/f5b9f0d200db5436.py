"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.pyzx_full_reduce(tools.tket(circ, "FullPeepholeOptimise")))
    except Exception:
        pass
    try:
        starts.append(tools.pyzx_teleport_reduce(tools.lower(circ)))
    except Exception:
        pass
    cur = tools.best(starts)
    return cur
