"""Run Genesis' src.main unchanged, with two additions needed for verification:

1. seeds Python's `random` and numpy (Genesis' routing uses networkx simulated-annealing TSP with
   seed=None, so physical circuits otherwise differ run to run);
2. records the final logical->physical wire mapping of every `Circuit.map_to_graph` call (routing
   SWAPs permute qumodes and are never undone) into `<physical output>.mapping.json`.

Genesis' compiler logic is not modified.  Usage (cwd = Genesis root):
    python run_genesis.py --batch-json job.json --stats [--seed 0]
"""
import json
import os
import random
import runpy
import sys

sys.path.insert(0, os.getcwd())
seed = 0
if "--seed" in sys.argv:
    i = sys.argv.index("--seed")
    seed = int(sys.argv[i + 1])
    del sys.argv[i:i + 2]
random.seed(seed)
try:
    import numpy as _np
    _np.random.seed(seed)
except Exception:
    pass

import src.circuits as _circuits  # noqa: E402
import src.graph_mapping as _gm  # noqa: E402
import src.parser as _parser  # noqa: E402

_created = []
_orig_init = _gm.Mapping.__init__


def _init(this, coupling_graph):
    _orig_init(this, coupling_graph)
    _created.append(this)


_gm.Mapping.__init__ = _init
_orig_map = _circuits.Circuit.map_to_graph
_last_mapping = {}


def _map_to_graph(this, *a, **k):
    start = len(_created)
    out = _orig_map(this, *a, **k)
    cur = _created[start]  # first Mapping built inside the call is `current_mapping`
    _last_mapping["pairs"] = [[list(l), list(p)] for l, p in zip(cur.log_qubits, cur.phys_qubits)]
    return out


_circuits.Circuit.map_to_graph = _map_to_graph
_orig_write = _parser.write_qasm


def _write(circ, path, *a, **k):
    r = _orig_write(circ, path, *a, **k)
    if "pairs" in _last_mapping:
        with open(str(path) + ".mapping.json", "w") as f:
            json.dump({"seed": seed, "final_log_to_phys": _last_mapping["pairs"]}, f)
    return r


_parser.write_qasm = _write
sys.argv = ["src.main"] + sys.argv[1:]
runpy.run_module("src.main", run_name="__main__", alter_sys=True)
