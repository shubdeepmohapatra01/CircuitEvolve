"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.tket(circ, "FullPeepholeOptimiseNoSwaps"))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.tket(cur, "FullPeepholeOptimise")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "PauliSquash")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.approx_round(cur, 0.5 * tools.error_left(cur))
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.approx_round(cur, 1.0 * tools.error_left(cur))
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
