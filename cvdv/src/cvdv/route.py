"""Physical mapping with Genesis' own router, so that compilers differing only in synthesis are
compared under the same routing.

route(ops) writes the logical circuit, runs Genesis `Circuit.map_to_graph` on the square grid
Genesis' main.py would choose (site i = qubit q_i + qumode qm_i, qumode grid edges), with the same
options as Genesis' main ('depth_sum', simulated-annealing TSP, no qubit swaps) and a fixed seed.

SWAP phase fix: Genesis inserts SWAP = BS(π,0)·R(π/2)⊗R(π/2), which equals SWAP·(-1)^{n_a+n_b}
(see P0 audit).  The correct SWAP is BS(π,0) followed by R(-π/2)⊗R(-π/2).  Router-inserted gates
are patched at construction time: inside map_to_graph `PiAngle(0.5)` is used only for the two
SWAP rotations, so it is wrapped to return PiAngle(-0.5).  Gate counts are unchanged by the fix.
"""
from __future__ import annotations

import contextlib
import io
import math
import os
import random
import sys
import tempfile

import numpy as np

from . import qasm

_G = os.path.join(os.path.dirname(__file__), "..", "..", "third_party", "genesis")


def _genesis():
    p = os.path.abspath(_G)
    if p not in sys.path:
        sys.path.insert(0, p)
    import src.circuits as gc  # noqa
    import src.graph_mapping as gm  # noqa
    import src.parser as gp  # noqa
    return gc, gm, gp


def _same(lo, po, inv_wire):
    if lo.name != po.name or len(lo.params) != len(po.params):
        return False
    if any(abs(complex(a) - complex(b)) > 1e-7 for a, b in zip(lo.params, po.params)):
        return False
    return True


def route(ops, seed: int = 0, fix_swaps: bool = True):
    gc, gm, gp = _genesis()
    with tempfile.TemporaryDirectory() as d:
        lp = os.path.join(d, "logical.cvdvqasm")
        with open(lp, "w") as f:
            for o in ops:
                f.write(qasm.format_op(o) + "\n")
        circ = gp.read_qasm(lp)
        square_len = math.ceil(math.sqrt(max(l for _, l in circ.wires) + 1))
        graph = gm.make_rectangle_graph(square_len, square_len)
        random.seed(seed)
        np.random.seed(seed)
        created = []
        orig_init = gm.Mapping.__init__

        def _init(this, g):
            orig_init(this, g)
            created.append(this)

        gm.Mapping.__init__ = _init
        import src.circ_utils as cu  # noqa
        orig_pi = cu.PiAngle
        swaps = [0]

        def _pi(x):  # inside map_to_graph, PiAngle(0.5) occurs only in the SWAP construction
            if fix_swaps and x == 0.5:
                swaps[0] += 1
                return orig_pi(-0.5)
            return orig_pi(x)

        if fix_swaps:
            cu.PiAngle = _pi
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                out = circ.map_to_graph(graph, pauli_mapping_order="depth_sum",
                                        tsp_method="simulated_annealing_tsp", qubit_swaps=False)
        finally:
            gm.Mapping.__init__ = orig_init
            cu.PiAngle = orig_pi
        cur = created[0]
        final = {tuple(l): tuple(p) for l, p in zip(cur.log_qubits, cur.phys_qubits)}
        pp = os.path.join(d, "physical.cvdvqasm")
        gp.write_qasm(out, pp)
        phys = qasm.read(pp).ops
    return phys, {"final_map": final, "square_len": square_len, "n_inserted": len(phys) - len(ops),
                  "n_swaps": swaps[0] // 2, "seed": seed}
