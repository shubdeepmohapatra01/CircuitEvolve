"""Standard compiler stages that turn arbitrary input QASM into our Clifford+Rz / Clifford+T gate set.

Pipeline used everywhere else in the project: load -> tket -> [pyzx_reduce] -> gridsynth -> t_count.
Every function is Circuit -> Circuit (gridsynth and t_count also take/use an error budget).
"""
from __future__ import annotations

import os
import re

os.environ.setdefault("XDG_CONFIG_HOME", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                        ".cache", "xdg"))

from . import circuit as C
from .circuit import Circuit, Gate, counts, from_qasm, is_arbitrary_rz, to_qasm

# rz(k*pi/4) that equals one single standard gate up to global phase (k=3,5 have no such single gate:
# they stay as rz but already count as T-like in circuit.counts).
_QUARTER_GATE = {0: None, 1: "t", 2: "s", 4: "z", 6: "sdg", 7: "tdg"}

_SCI = re.compile(r"(?<![\w.])-?\d+\.?\d*[eE][-+]?\d+")


def _safe_qasm(c: Circuit) -> str:
    """to_qasm, with scientific-notation angles expanded to fixed-point (pyzx/pytket angle parsers choke on 1e-05)."""
    return _SCI.sub(lambda m: format(float(m.group(0)), ".25f"), to_qasm(c))


def name_gates(c: Circuit) -> Circuit:
    """Rename rz at multiples of pi/4 to z/s/sdg/t/tdg; drop rz(0) (mod 2pi). Global phase is irrelevant."""
    out = []
    for g in c.gates:
        if g.name == "rz":
            k = C._quarter_turns(g.theta)
            if k in _QUARTER_GATE:
                name = _QUARTER_GATE[k]
                if name is not None:
                    out.append(Gate(name, g.qubits, cond=g.cond))
                continue
        out.append(g)
    return Circuit(c.n, out, c.nc)


def load(path: str) -> Circuit:
    """Our own QASM parser; falls back to pytket for gate sets we don't speak (u3, cp, ...).

    The fallback rebases to {CX, H, Rz} WITHOUT running any optimization pass, so it changes
    gate representation only, not gate count/structure beyond what the rebase itself requires.
    """
    try:
        c = C.load(path)
    except Exception:
        from pytket import OpType
        from pytket.passes import AutoRebase
        from pytket.qasm import circuit_from_qasm, circuit_to_qasm_str
        tkc = circuit_from_qasm(path)
        AutoRebase({OpType.CX, OpType.H, OpType.Rz}).apply(tkc)
        c = from_qasm(circuit_to_qasm_str(tkc, maxwidth=10 ** 6))
    return name_gates(c)


def tket(c: Circuit) -> Circuit:
    """pytket FullPeepholeOptimise -> rebase to {CX, H, Rz}. allow_swaps=False: our Circuit has no notion
    of an implicit output permutation, so we must forbid the optimizer from introducing one.
    FullPeepholeOptimise can turn an exact Clifford+T circuit into one with NEW arbitrary rotations (measured:
    rc_adder_6 0 -> 12 rz, vbe_adder_3 0 -> 16), which gridsynth then charges ~40 T each. If that happens we
    fall back to TKET passes that cannot create new angles."""
    from pytket import OpType
    from pytket.passes import (AutoRebase, CliffordSimp, CommuteThroughMultis, FullPeepholeOptimise,
                               RemoveRedundancies)
    from pytket.qasm import circuit_from_qasm_str, circuit_to_qasm_str

    def run(passes):
        tkc = circuit_from_qasm_str(_safe_qasm(c))
        for p in passes:
            p.apply(tkc)
        AutoRebase({OpType.CX, OpType.H, OpType.Rz}).apply(tkc)
        RemoveRedundancies().apply(tkc)
        return name_gates(from_qasm(circuit_to_qasm_str(tkc, maxwidth=10 ** 6)))

    out = run([FullPeepholeOptimise(allow_swaps=False)])
    if counts(out)["rz"] > counts(c)["rz"]:
        out = run([RemoveRedundancies(), CommuteThroughMultis(), CliffordSimp(allow_swaps=False), RemoveRedundancies()])
    return out


def pyzx_reduce(c: Circuit) -> Circuit:
    """pyzx full_reduce (the B1 recipe): to_graph -> full_reduce -> extract_circuit -> to_basic_gates ->
    basic_optimization. to_basic_gates must run BEFORE basic_optimization: pyzx's basic_optimization silently
    returns a non-equivalent circuit when handed XPhase gates, which extract_circuit can produce.
    Assumes c is purely unitary (no measure/reset/cond): pyzx has no notion of those."""
    import pyzx as zx
    zx.settings.float_to_fraction_max_denominator = 10 ** 15
    txt = re.sub(r"^creg .*;\n", "", _safe_qasm(c), flags=re.M)  # pyzx turns creg into extra graph wires
    g = zx.Circuit.from_qasm(txt).to_graph()
    zx.full_reduce(g)
    ex = zx.extract_circuit(g.copy())
    ex = zx.basic_optimization(ex.to_basic_gates())
    return name_gates(from_qasm(ex.to_qasm()))


_GS_CACHE: dict[tuple[float, float], str] = {}


def gridsynth(c: Circuit, eps_total: float) -> Circuit:
    """Replace every arbitrary rz by its pygridsynth Clifford+T sequence, budget eps_total / N_rz each
    (N_rz = number of arbitrary rz in c; the BQSKit-FT / stage-1 baseline convention, operator-norm bound
    N_rz * eps_total/N_rz = eps_total). measure/reset/cond/ccx/ccz and any already-Clifford+T gate pass
    through unchanged; only arbitrary rz are touched. Output has no arbitrary rz left."""
    import mpmath
    from pygridsynth.gridsynth import gridsynth_gates
    mpmath.mp.dps = 128
    n = sum(1 for g in c.gates if is_arbitrary_rz(g))
    eps_per = eps_total / n if n else eps_total
    out = []
    for g in c.gates:
        if not is_arbitrary_rz(g):
            out.append(g)
            continue
        key = (round(g.theta, 12), eps_per)
        word = _GS_CACHE.get(key)
        if word is None:
            word = str(gridsynth_gates(mpmath.mpmathify(g.theta), mpmath.mpmathify(eps_per)))
            _GS_CACHE[key] = word
        for ch in reversed(word):  # pygridsynth words are in matrix order; circuit order is reversed
            if ch == "H":
                out.append(Gate("h", g.qubits))
            elif ch == "S":
                out.append(Gate("s", g.qubits))
            elif ch == "T":
                out.append(Gate("t", g.qubits))
            elif ch == "X":
                out.append(Gate("x", g.qubits))
            elif ch in ("W", "I"):   # global phase / identity: dropped, as bqskit-ft's GridSynthPass does
                pass
            else:
                raise ValueError(f"unexpected gridsynth symbol {ch!r}")
    return Circuit(c.n, out, c.nc)


def t_count(c: Circuit) -> int:
    """T-count of a Clifford+T circuit, i.e. c after gridsynth (asserts no arbitrary rz remains)."""
    assert not any(is_arbitrary_rz(g) for g in c.gates), "t_count expects a gridsynth'd (pure Clifford+T) circuit"
    return counts(c)["t"]
