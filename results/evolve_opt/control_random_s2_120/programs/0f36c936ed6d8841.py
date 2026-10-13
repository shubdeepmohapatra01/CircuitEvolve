"""Classical-control program (generated from a pass-sequence genome)."""


def optimize(circ, tools, budget):
    starts = []
    try:
        starts.append(tools.lower(circ))
    except Exception:
        pass
    cur = tools.best(starts)
    try:
        nxt = tools.fold_resynth(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.block_optimize(cur, method="fold_resynth", block_size=4, max_gates=80)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.pyzx_clifford_simp(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.tket(cur, "RemoveRedundancies")
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    try:
        nxt = tools.pyzx_full_reduce(cur)
        cur = tools.best(cur, nxt)
    except Exception:
        pass
    return cur
