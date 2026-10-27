"""Rule API for cvdv_fast (what rule files import). Same contract as v3: one file = one RULE.

Two rule kinds
  synth    RULE.synth(t, g, r): emit gates for ONE classified Hamiltonian part `t` (TermView) through builder `g`
           so that the gates implement exp(-i H_part). `t.kind` in RULE.term_kinds. `r` = precision knob for
           approximate rules (the runner raises it until the ledger share is met; exact rules ignore it).
           Return None (or raise ValueError) to decline.
  rewrite  RULE.trigger(ops) -> list of matches;  RULE.apply(ops, m) -> (i0, i1, new_ops): replace ops[i0..i1]
           (inclusive) by new_ops. `stage` = 'logical' (before routing), 'physical' (after routing; new 2-op gates
           must stay on coupled pairs, enforced by the runner) or 'both'.

TermView t: kind, label (Pauli string on t.q), q (qubit wires), m (qumode wires), theta, phi, alpha
            (H_part = theta * O for real-coefficient kinds; disp/pauli_disp: H = i(alpha a^+ - alpha* a) * P).
Kinds: n (theta n), n2 (theta n^2), hop (theta (e^{i phi} a^+ b + h.c.)), z_n (theta Z n),
       z_hop (theta Z (e^{i phi} a^+ b + h.c.)), pauli (theta P), disp, pauli_disp (P (alpha a^+ - alpha* a)).
Builder g: qubit gates h x y z s sdg t tdg rx ry rz r; R D BS CR CP CD CBS RB; anc_qubit(k), anc_mode(k).
Op = cvdv.qasm.Op(name, params, wires); wires are ('q', i) / ('qm', j).
Gate conventions: R(t)=e^{-itn}, D(a)=e^{a a^+ - a* a}, BS(t,p)=e^{-it/2(e^{ip}a^+b+h.c.)}, CR(t)=e^{-it/2 Z n},
CP=CR(pi), CD(a)=e^{Z(a a^+ - a* a)}, CBS(t,p)=e^{-it/2 Z(e^{ip}a^+b+h.c.)}, RB(t)=e^{-i X(t a^+ + t* a)}.
Time order = emission order (first emitted acts first).
"""
from __future__ import annotations

import cmath  # noqa: F401  (re-exported for rule files)
import math  # noqa: F401
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import paths  # noqa: F401  (sys.path shim)
from cvdv.library import Builder, TermView  # noqa: F401
from cvdv.qasm import Op  # noqa: F401


@dataclass
class Rule:
    name: str
    kind: str                         # 'synth' | 'rewrite'
    contract: str                     # 'exact' | 'approx'
    idea: str
    source: str
    term_kinds: tuple = ()            # synth only
    synth: Optional[Callable] = None  # synth only
    trigger: Optional[Callable] = None  # rewrite only
    apply: Optional[Callable] = None    # rewrite only
    stage: str = "logical"            # rewrite only
    meta: dict = field(default_factory=dict)


# ---- small helpers for rewrite rules
def wires_of(op):
    return tuple(op.wires)


def next_on_wires(ops, i, ws=None):
    """Index of the next op after i sharing a wire with ops[i] (or with `ws`), else None."""
    ws = set(ws if ws is not None else ops[i].wires)
    for j in range(i + 1, len(ops)):
        if ws & set(ops[j].wires):
            return j
    return None


def same_wires_adjacent(ops, i):
    """j > i such that ops[j] is the next op on every wire of ops[i] and has exactly the same wires, else None."""
    j = next_on_wires(ops, i)
    if j is None or tuple(ops[j].wires) != tuple(ops[i].wires):
        return None
    for k in range(i + 1, j):
        if set(ops[k].wires) & set(ops[i].wires):
            return None
    return j
