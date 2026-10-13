"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.pyzx_full_reduce(tools.lower(circ)))
    except Exception:
        pass
    try:
        starts.append(tools.tket(circ, "FullPeepholeOptimise"))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.tket(cur, "ZXGraphlikeOptimisation")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.pyzx_clifford_simp(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.resynth_1q(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.block_optimize(cur, method="fold_resynth", block_size=2, max_gates=40)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.pyzx_full_reduce(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "PauliSimp")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.resynth_1q(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
