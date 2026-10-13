"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.tket(circ, "FullPeepholeOptimiseNoSwaps"))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.block_optimize(cur, method="tket", block_size=2, max_gates=20)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "CliffordResynthesis")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "ZXGraphlikeOptimisation")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "ZXGraphlikeOptimisation")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "CommuteThroughMultis")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
