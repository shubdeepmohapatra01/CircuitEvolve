"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.tket(circ, "FullPeepholeOptimiseNoSwaps"))
    except Exception:
        pass
    try:
        starts.append(tools.lower(circ))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.tket(cur, "PauliSimp")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.block_optimize(cur, method="tket", block_size=3, max_gates=40)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.block_optimize(cur, method="pyzx", block_size=3, max_gates=40)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "RemoveRedundancies")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
