"""CV-DV circuit helpers for rules: v3 JSON op lists.

A CV-DV circuit is {"label": <suite label>, "ops": [op, ...]} with op = {"name", "params": [[re, im], ...],
"wires": [["q"|"qm", i], ...]} for a native gate (Genesis Table 2 names: R D BS CR CP CD CBS + qubit gates), or
{"term": k} for IR term k not yet synthesized (simulated exactly by the judge, priced as unsynthesized).
Ours starts from the spec: start_circuit(label) = every IR term as a placeholder, in IR order.
"""
from __future__ import annotations

import copy
import json

from ..paths import MANIFEST, V3


def n_terms(label: str) -> int:
    c = next(x for x in json.loads(MANIFEST.read_text())["circuits"] if x["label"] == label)
    lines = [l for l in (V3 / c["spec"]).read_text().splitlines() if l.strip() and not l.strip().startswith("//")]
    return len(lines)


def start_circuit(label: str) -> dict:
    return {"label": label, "ops": [{"term": k} for k in range(n_terms(label))]}


def wires(op) -> tuple:
    return tuple(tuple(w) for w in op.get("wires", ()))


def param(op, i=0) -> complex:
    a, b = op["params"][i]
    return complex(a, b)


def gate(name, params, ws) -> dict:
    return {"name": name, "params": [[complex(p).real, complex(p).imag] for p in params],
            "wires": [list(w) for w in ws]}


def next_on_wire(ops, i, w):
    """Index of the next op after i touching wire w (placeholders touch no wires known here -> barrier)."""
    for j in range(i + 1, len(ops)):
        if "term" in ops[j] or tuple(w) in wires(ops[j]):
            return j
    return None


def replace(circ, i0, i1, new_ops) -> dict:
    """Copy of circ with ops[i0..i1] (inclusive) replaced by new_ops."""
    out = copy.deepcopy(circ)
    out["ops"] = out["ops"][:i0] + list(new_ops) + out["ops"][i1 + 1:]
    return out
