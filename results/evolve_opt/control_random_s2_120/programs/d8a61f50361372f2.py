"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
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
        nxt = tools.phase_fold(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "OptimisePhaseGadgets")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "FullPeepholeOptimise")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.pyzx_clifford_simp(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "PauliSquash")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
