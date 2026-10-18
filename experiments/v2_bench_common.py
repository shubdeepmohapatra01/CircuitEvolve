"""Shared helpers for the v2 benchmark track (Nam et al. 2018 arithmetic suite): QASM I/O, gate counts, pyzx / TKET
arms and output verification. Imports from circuitevolve (frozen verify_block, ir decomposition tables) without
modifying them.

Verification modes (label in every record):
  unitary_dense      n <= 12: phase-aligned operator-norm distance of the full 2^n x 2^n unitaries (float64,
                     verify_block.circuit_check with dense_max=12); pass if dist <= 1e-9.
  statevector_haar   13 <= n <= 22: Haar-random input states (4 states, 2 if n > 18); max phase-aligned vector
                     distance; pass if <= 1e-9 (a lower bound on the operator distance).
  sparse_pair_states n > 22: 24 random inputs (6 if n > 40) (|x> + |y>)/sqrt2 over computational basis states, simulated sparsely
                     (both circuits), phase-aligned distance per input; catches wrong functions and relative phases
                     between the pair; skipped if the state support exceeds 2^17.
  zx_identity        12 < n <= 40 (in addition): pyzx Circuit.verify_equality (compose A with B^dagger, full_reduce,
                     test for the identity). True is strong evidence of equality; None/False proves nothing.
  qcec               every n (in addition, run2 onward; subprocess with a hard wall-clock limit): MQT QCEC 3.8 equivalence checker (decision diagrams +
                     simulation + ZX, default configuration; timeout 120 s, 600 s when the sparse check was undecided). 'equivalent' /
                     'equivalent_up_to_global_phase' = proved; 'not_equivalent' = disproved; 'probably_*' /
                     'no_information' = undecided.
A record is VERIFIED if the primary method passes, or (primary undecided) QCEC proves equivalence; it FAILS if
either the primary method or QCEC reports a difference.
"""
from __future__ import annotations

import cmath
import math
import os
import re
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("XDG_CONFIG_HOME", os.path.join(ROOT, ".venv", "xdg"))  # pytket writes a config file

import numpy as np  # noqa: E402

from circuitevolve.blocks import verify_block as vb  # noqa: E402  (frozen; read-only use)
from circuitevolve.ir import _CCX, _CCZ  # noqa: E402

BENCH = os.path.join(ROOT, "benchmarks", "nam_arith")
TOL = 1e-9
SPARSE_TRIALS = 24        # n <= 40
SPARSE_TRIALS_LARGE = 6   # n > 40 (gf2^16, gf2^32: pure-Python sparse simulation is ~30 s per trial); QCEC decides
CLIFF_T = {"x", "z", "h", "s", "sdg", "t", "tdg", "cx", "cz"}


# ------------------------------------------------------------------------------------------------ QASM I/O
def read_qasm(path: str):
    """Parse the restricted OpenQASM 2 used in benchmarks/nam_arith (one or more qregs, gate defs skipped).
    Returns (n, ops) with ops = [(name, qubits, angle_or_None)]."""
    text = open(path).read()
    regs, n, ops = {}, 0, []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(("OPENQASM", "include", "//", "gate ", "creg", "barrier")):
            continue
        m = re.match(r"qreg\s+(\w+)\[(\d+)\];", s)
        if m:
            regs[m.group(1)] = n
            n += int(m.group(2))
            continue
        m = re.match(r"(\w+)(?:\(([^)]*)\))?\s+(.+);$", s)
        if not m:
            raise ValueError(f"cannot parse: {s}")
        g, arg = m.group(1), m.group(2)
        qs = tuple(regs[r] + int(i) for r, i in re.findall(r"(\w+)\[(\d+)\]", m.group(3)))
        ang = None
        if arg is not None:
            ang = float(eval(arg.replace("pi", "math.pi"), {"math": math}))  # angles only (pinned inputs)
        ops.append((g, qs, ang))
    return n, ops


def write_qasm(ops, n: int) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";']
    if any(o[0] == "ccz" for o in ops):
        lines.append("gate ccz a,b,c { h c; ccx a,b,c; h c; }")
    lines.append(f"qreg q[{n}];")
    for g, qs, a in ops:
        args = ",".join(f"q[{q}]" for q in qs)
        lines.append(f"{g}({a!r}) {args};" if a is not None else f"{g} {args};")
    return "\n".join(lines) + "\n"


def expand(ops):
    """ccx / ccz -> Clifford+T (frozen ir.py tables, 7 T each); rz(k pi/4) -> named gates."""
    out = []
    for g, qs, a in ops:
        if g in ("ccx", "ccz"):
            for e in (_CCX if g == "ccx" else _CCZ):
                out.append((e[0], tuple(qs[i] for i in e[1:]), None))
        elif g == "rz" and a is not None and _is_mult(a, math.pi / 4):
            out.extend(_rz_named(qs[0], a))
        else:
            out.append((g, tuple(qs), a))
    return out


def _is_mult(a: float, unit: float, tol: float = 1e-9) -> bool:
    k = a / unit
    return abs(k - round(k)) < tol


def _rz_named(q: int, a: float):
    k = round(a / (math.pi / 4)) % 8
    seq = {0: [], 1: ["t"], 2: ["s"], 3: ["s", "t"], 4: ["z"], 5: ["z", "t"], 6: ["sdg"], 7: ["tdg"]}[k]
    return [(g, (q,), None) for g in seq]


# ------------------------------------------------------------------------------------------------ counts
def counts(ops) -> dict:
    c = dict(gates=len(ops), t=0, ccx=0, ccz=0, cx=0, h=0, rz_nonclifford=0, rz_other=0)
    for g, qs, a in ops:
        if g in ("t", "tdg"):
            c["t"] += 1
        elif g == "rz":
            if _is_mult(a, math.pi / 2):
                pass
            elif _is_mult(a, math.pi / 4):
                c["t"] += 1
            else:
                c["rz_other"] += 1
        elif g in ("ccx", "ccz"):
            c[g] += 1
        elif g in ("cx", "cz"):
            c["cx"] += 1
        elif g == "h":
            c["h"] += 1
    c["t_if_expanded"] = c["t"] + 7 * (c["ccx"] + c["ccz"])
    return c


# ------------------------------------------------------------------------------------------------ verification
def _sparse_apply(st: dict, g: str, qs, a) -> dict:
    s2 = 1 / math.sqrt(2)
    if g in ("x", "cx", "ccx"):
        t = qs[-1]
        cm = sum(1 << q for q in qs[:-1])
        return {(k ^ (1 << t)) if (k & cm) == cm else k: v for k, v in st.items()}
    if g in ("z", "s", "sdg", "t", "tdg", "rz", "cz", "ccz"):
        if g == "rz":
            ph0, ph1 = cmath.exp(-0.5j * a), cmath.exp(0.5j * a)
        else:
            ph0, ph1 = 1, {"z": -1, "cz": -1, "ccz": -1, "s": 1j, "sdg": -1j,
                           "t": cmath.exp(0.25j * math.pi), "tdg": cmath.exp(-0.25j * math.pi)}[g]
        cm = sum(1 << q for q in qs)
        return {k: v * (ph1 if (k & cm) == cm else ph0) for k, v in st.items()}
    if g == "h":
        b = 1 << qs[0]
        out: dict = {}
        for k, v in st.items():
            k0 = k & ~b
            out[k0] = out.get(k0, 0) + s2 * v
            out[k0 | b] = out.get(k0 | b, 0) + (-s2 * v if k & b else s2 * v)
        return {k: v for k, v in out.items() if abs(v) > 1e-14}
    raise ValueError(f"sparse sim: unsupported gate {g}")


def sparse_run(ops, st: dict, cap: int = 1 << 17) -> dict:
    for g, qs, a in ops:
        st = _sparse_apply(st, g, qs, a)
        if len(st) > cap:
            raise OverflowError(len(st))
    return st


def sparse_pair_check(ops_a, ops_b, n: int, trials: int = 24, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    worst = 0.0
    for _ in range(trials):
        x, y = (int(v) for v in rng.integers(0, 1 << min(n, 62), size=2))
        if n > 62:
            x |= int(rng.integers(0, 1 << (n - 62))) << 62
            y |= int(rng.integers(0, 1 << (n - 62))) << 62
        st0 = {x: 1 / math.sqrt(2)} if x == y else {x: 1 / math.sqrt(2), y: 1 / math.sqrt(2)}
        if x == y:
            st0 = {x: 1.0}
        try:
            A = sparse_run(ops_a, dict(st0))
            B = sparse_run(ops_b, dict(st0))
        except OverflowError as e:
            return dict(method="sparse_pair_states", ok=None, reason=f"support > cap ({e})")
        ov = sum(A[k].conjugate() * B.get(k, 0) for k in A)
        ph = ov.conjugate() / abs(ov) if abs(ov) > 1e-12 else 1
        keys = set(A) | set(B)
        d = math.sqrt(sum(abs(A.get(k, 0) - ph * B.get(k, 0)) ** 2 for k in keys))
        worst = max(worst, d)
    return dict(method="sparse_pair_states", trials=trials, dist=worst, ok=worst <= TOL)


def zx_identity(ops_a, ops_b, n: int):
    import pyzx as zx
    ca = zx.Circuit.from_qasm(write_qasm(expand(ops_a), n))
    cb = zx.Circuit.from_qasm(write_qasm(expand(ops_b), n))
    return ca.verify_equality(cb)


QCEC_PROVED = {"equivalent", "equivalent_up_to_global_phase"}


def _qcec_run(qa: str, qb: str, cfg: dict, timeout: float) -> str:
    import json
    import subprocess
    import tempfile
    from circuitevolve.locks import NUMERIC_LOCK
    with tempfile.TemporaryDirectory() as d:
        pa, pb = os.path.join(d, "a.qasm"), os.path.join(d, "b.qasm")
        open(pa, "w").write(qa)
        open(pb, "w").write(qb)
        with NUMERIC_LOCK:  # never fork while numpy verification runs (project rule)
            p = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                               "v2_bench_qcec_worker.py"), pa, pb, json.dumps(cfg),
                                  str(timeout)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            out, _ = p.communicate(timeout=timeout + 30)
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
            return "killed_after_timeout"
        try:
            return json.loads(out.strip().splitlines()[-1])["qcec"]
        except Exception:  # noqa: BLE001
            return f"error: rc={p.returncode}"


def qcec_check(ops_a, ops_b, n: int, timeout: float = 120.0) -> dict:
    """Two phases: (1) ZX + simulation checkers (no alternating DD checker); (2) only if (1) did not decide,
    the alternating DD checker alone. Hard wall-clock limit per phase (process killed)."""
    t0 = time.time()
    qa, qb = write_qasm(expand(ops_a), n), write_qasm(expand(ops_b), n)
    eq = _qcec_run(qa, qb, dict(run_alternating_checker=False, run_zx_checker=True), timeout)
    phase = "zx+sim"
    if eq not in QCEC_PROVED and eq != "not_equivalent":
        eq2 = _qcec_run(qa, qb, dict(run_alternating_checker=True, run_zx_checker=False,
                                     run_simulation_checker=False, run_construction_checker=False), timeout)
        if eq2 in QCEC_PROVED or eq2 == "not_equivalent":
            eq, phase = eq2, "alternating"
        else:
            eq = f"{eq}/{eq2}"
    return dict(qcec=eq, qcec_phase=phase, qcec_s=round(time.time() - t0, 2))


def verdict(rec: dict):
    """True = verified, False = a check found a difference, None = undecided."""
    q = rec.get("qcec")
    if rec.get("ok") is False or q == "not_equivalent":
        return False
    if rec.get("ok") is True or q in QCEC_PROVED:
        return True
    return None


def check(ops_a, ops_b, n: int, zx: bool = True, qcec: bool = True) -> dict:
    """Verify circuit B against circuit A (both gate lists over n qubits). See the module docstring."""
    t0 = time.time()
    A, B = expand(ops_a), expand(ops_b)
    if n <= 12:
        r = vb.circuit_check(A, B, n, dense_max=12)
        rec = dict(method="unitary_dense", dist=r["dist"], ok=r["dist"] <= TOL)
    elif n <= 22:
        r = vb.circuit_check(A, B, n, n_states=4 if n <= 18 else 2, dense_max=12, sv_max=22)
        rec = dict(method="statevector_haar", n_states=r["n_states"], dist=r["dist"], ok=r["dist"] <= TOL)
    else:
        rec = sparse_pair_check(A, B, n, trials=SPARSE_TRIALS if n <= 40 else SPARSE_TRIALS_LARGE)
    if zx and 12 < n <= 40:
        try:
            rec["zx_identity"] = zx_identity(ops_a, ops_b, n)
        except Exception as e:  # noqa: BLE001
            rec["zx_identity"] = f"error: {type(e).__name__}"
    if qcec:
        rec.update(qcec_check(ops_a, ops_b, n, timeout=120.0 if rec.get("ok") is not None else 600.0))
    rec["verified"] = verdict(rec)
    rec["check_s"] = round(time.time() - t0, 2)
    return rec


# ------------------------------------------------------------------------------------------------ arms
def pyzx_arm(ops, n: int) -> dict:
    """pyzx full_reduce (T-count of the reduced graph) + extract_circuit + to_basic_gates + basic_optimization
    (circuitevolve.blocks.classical.pyzx_optimise, the project's existing pyzx pipeline)."""
    import pyzx as zx
    from circuitevolve.blocks.classical import pyzx_optimise
    t0 = time.time()
    g = zx.Circuit.from_qasm(write_qasm(expand(ops), n)).to_graph()
    zx.full_reduce(g)
    t_graph = zx.tcount(g)
    t1 = time.time()
    out = pyzx_optimise(expand(ops), n)
    return dict(t_graph=t_graph, ops=out, reduce_s=round(t1 - t0, 2), pipeline_s=round(time.time() - t1, 2))


def tket_arm(ops, n: int) -> dict:
    """TKET FullPeepholeOptimise -> replace_implicit_wire_swaps -> AutoRebase{CX,H,Rz} -> RemoveRedundancies
    (same pass sequence as circuitevolve.blocks.classical.tket_optimise). ccx is passed natively, ccz as h-ccx-h."""
    from pytket import OpType
    from pytket.passes import AutoRebase, FullPeepholeOptimise, RemoveRedundancies
    from pytket.qasm import circuit_from_qasm_str
    t0 = time.time()
    flat = []
    for g, qs, a in ops:
        if g == "ccz":
            flat += [("h", (qs[2],), None), ("ccx", qs, None), ("h", (qs[2],), None)]
        else:
            flat.append((g, qs, a))
    c = circuit_from_qasm_str(write_qasm(flat, n))
    FullPeepholeOptimise().apply(c)
    c.replace_implicit_wire_swaps()
    AutoRebase({OpType.CX, OpType.H, OpType.Rz}).apply(c)
    RemoveRedundancies().apply(c)
    idx = {q: i for i, q in enumerate(c.qubits)}
    out = []
    for cmd in c:
        qs = tuple(idx[q] for q in cmd.qubits)
        t = cmd.op.type
        if t == OpType.Rz:
            out.append(("rz", qs, math.pi * float(cmd.op.params[0])))
        elif t == OpType.H:
            out.append(("h", qs, None))
        elif t == OpType.CX:
            out.append(("cx", qs, None))
        else:
            raise ValueError(f"unexpected tket op {t}")
    return dict(ops=out, pipeline_s=round(time.time() - t0, 2))
