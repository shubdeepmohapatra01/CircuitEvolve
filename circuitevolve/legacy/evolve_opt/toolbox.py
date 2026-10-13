"""The fixed toolbox handed to optimizer programs (runs inside the sandboxed child process).

Programs see an instance `tools` and opaque circuit handles (`Circ`, no public attributes). Every tool
returns a NEW handle; nothing is mutated. Tools are deterministic functions of their inputs and are cached
on disk by (tool, parameters, input ops) - a cache hit charges the CPU seconds of the original call, so the
runtime a program is charged does not depend on what other programs ran before.

Error accounting (per circuit, total ERROR_BUDGET = 1e-6, phase-aligned operator norm):
    bound = sum of approximation errors (ledger)  +  NUMERIC_SLACK (1e-8)  +  #rz(output) * EPS_RZ (1e-9)
Exact passes (pyzx, TKET, phase folding, 1q resynthesis) add nothing to the ledger; their floating-point
error (~1e-11) is covered by NUMERIC_SLACK and measured by the parent. Approximating tools (approx_round,
block rewrites accepted at a measured distance) add their measured / analytic distance and refuse to exceed
`error_left(c)`. EPS_RZ is fixed at the baseline's 1e-9 so that no gain can come from re-splitting the
budget between synthesis and approximation (the best-classical reference uses 1e-9 per rotation).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from fractions import Fraction
from pathlib import Path

from . import EPS_RZ, ERROR_BUDGET, NUMERIC_SLACK, TOOLBOX_VERSION
from circuitevolve.blocks import REPO

CACHE_ROOT = REPO / ".cache" / "evolve_opt"
CLIFFORD_RZ = frozenset({"h", "x", "z", "s", "sdg", "t", "tdg", "cx", "cz", "rz"})

TKET_PASSES = ("FullPeepholeOptimise", "FullPeepholeOptimiseNoSwaps", "PeepholeOptimise2Q", "CliffordSimp",
               "RemoveRedundancies", "CommuteThroughMultis", "KAKDecomposition", "SynthesiseTket",
               "OptimisePhaseGadgets", "PauliSimp", "GreedyPauliSimp", "ZXGraphlikeOptimisation",
               "CliffordResynthesis", "ThreeQubitSquash", "PauliSquash")
BLOCK_METHODS = ("fold", "resynth_1q", "fold_resynth", "pyzx", "tket")


class ToolError(Exception):
    pass


class BudgetError(ToolError):
    pass


# ------------------------------------------------------------------------------ gridsynth (process-safe)
def gridsynth():
    """A Gridsynth cache that is safe with several processes writing (unique tmp file, merge on save)."""
    from circuitevolve.blocks.cost_model import Gridsynth

    class SafeGridsynth(Gridsynth):
        def __init__(self):
            path = CACHE_ROOT / f"gridsynth_{EPS_RZ:g}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            super().__init__(eps=EPS_RZ, path=path.with_name("__never_read__.json"))
            self.path = path
            self.data = _read_json(path) or {}
            if not self.data:                       # seed from the block optimizer's cache (same eps, same call)
                self.data = _read_json(REPO / ".cache" / "blocks" / f"gridsynth_{EPS_RZ:g}.json") or {}

        def _save(self):
            disk = _read_json(self.path) or {}
            disk.update(self.data)
            self.data = disk
            _atomic_write(self.path, json.dumps(disk))

    return SafeGridsynth()


def _read_json(p: Path):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return None


def _atomic_write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.{time.time_ns()}.tmp")
    tmp.write_text(text)
    os.replace(tmp, p)


# ------------------------------------------------------------------------------ circuit handle
class Circ:
    """Opaque, immutable circuit handle. Programs cannot read its fields (no '_' attribute access)."""
    __slots__ = ("_ops", "_n", "_key")

    def __init__(self, ops, n: int):
        self._ops = tuple((g, tuple(int(q) for q in qs), _norm_arg(a)) for g, qs, a in ops)
        self._n = int(n)
        self._key = None

    def key(self) -> str:   # not reachable from programs (they may only call tools.*)
        if self._key is None:
            self._key = hashlib.sha256(json.dumps([self._n, ops_to_json(self._ops)]).encode()).hexdigest()
        return self._key

    def __repr__(self):
        return f"<Circ n={self._n} gates={len(self._ops)}>"


def _norm_arg(a):
    if a is None:
        return None
    if isinstance(a, (list, tuple)):
        return tuple(float(x) for x in a)
    return float(a)


def ops_to_json(ops) -> list:
    return [[g, list(qs), (list(a) if isinstance(a, tuple) else a)] for g, qs, a in ops]


def ops_from_json(js) -> list:
    return [(g, tuple(qs), (tuple(a) if isinstance(a, list) else a)) for g, qs, a in js]


# ------------------------------------------------------------------------------ backends (pure functions)
def _is_clifford_rz(ops) -> bool:
    return all(g in CLIFFORD_RZ for g, _, _ in ops)


def _lower(ops, n):
    from circuitevolve.blocks.circuit_io import lower_minrz, ops_to_bqskit
    return lower_minrz(ops_to_bqskit(ops, n))


def _pyzx(ops, n, mode: str):
    import pyzx as zx
    from circuitevolve.blocks.circuit_io import emit_rz, ops_to_qasm
    zx.settings.float_to_fraction_max_denominator = 10 ** 15
    txt = re.sub(r"(?<![\w.])-?\d+\.?\d*[eE][-+]?\d+", lambda m: format(float(m.group(0)), ".25f"),
                 ops_to_qasm(ops, n))
    c_in = zx.Circuit.from_qasm(txt)
    if mode == "full_reduce":
        g = c_in.to_graph()
        zx.full_reduce(g)
        c = zx.basic_optimization(zx.extract_circuit(g.copy()).to_basic_gates())
    elif mode == "teleport_reduce":
        g = c_in.to_graph()
        zx.teleport_reduce(g)
        c = zx.basic_optimization(zx.Circuit.from_graph(g).to_basic_gates())
    elif mode == "clifford_simp":
        g = c_in.to_graph()
        zx.clifford_simp(g)
        c = zx.basic_optimization(zx.extract_circuit(g.copy()).to_basic_gates())
    elif mode == "basic":
        c = zx.basic_optimization(c_in.to_basic_gates())
    else:
        raise ToolError(f"unknown pyzx mode {mode}")
    out = []
    for gate in c.gates:
        nm = gate.name
        if nm in ("ZPhase", "XPhase"):
            q = gate.target
            if nm == "XPhase":
                out.append(("h", (q,), None))
            emit_rz(out, q, float(Fraction(gate.phase)) * math.pi)
            if nm == "XPhase":
                out.append(("h", (q,), None))
        elif nm in ("T", "T*", "S", "S*", "Z", "NOT", "HAD"):
            name = {"T": "tdg" if getattr(gate, "adjoint", False) else "t", "T*": "tdg",
                    "S": "sdg" if getattr(gate, "adjoint", False) else "s", "S*": "sdg",
                    "Z": "z", "NOT": "x", "HAD": "h"}[nm]
            out.append((name, (gate.target,), None))
        elif nm == "CNOT":
            out.append(("cx", (gate.control, gate.target), None))
        elif nm == "CZ":
            out.append(("cz", (gate.control, gate.target), None))
        elif nm == "SWAP":
            a, b = gate.control, gate.target
            out.extend([("cx", (a, b), None), ("cx", (b, a), None), ("cx", (a, b), None)])
        else:
            raise ToolError(f"unexpected pyzx gate {nm}")
    return out


def _tket(ops, n, passes):
    from pytket import OpType
    from pytket import passes as tp
    from pytket.qasm import circuit_from_qasm_str
    from circuitevolve.blocks.circuit_io import emit_rz, ops_to_qasm
    c = circuit_from_qasm_str(ops_to_qasm(ops, n))
    if any(g == "u3" for g, _, _ in ops) and passes[0] not in ("FullPeepholeOptimise", "FullPeepholeOptimiseNoSwaps"):
        tp.AutoRebase({OpType.CX, OpType.H, OpType.Rz}).apply(c)      # passes with gate-set predicates
    for p in passes:
        if p == "FullPeepholeOptimise":
            tp.FullPeepholeOptimise().apply(c)
        elif p == "FullPeepholeOptimiseNoSwaps":
            tp.FullPeepholeOptimise(allow_swaps=False).apply(c)
        elif p == "GreedyPauliSimp":
            tp.GreedyPauliSimp().apply(c)
        else:
            getattr(tp, p)().apply(c)
        tp.DecomposeBoxes().apply(c)
    c.replace_implicit_wire_swaps()
    tp.DecomposeBoxes().apply(c)
    tp.AutoRebase({OpType.CX, OpType.H, OpType.Rz}).apply(c)
    tp.RemoveRedundancies().apply(c)
    idx = {q: i for i, q in enumerate(c.qubits)}
    if len(idx) != n:
        raise ToolError("tket changed the number of qubits")
    out = []
    for cmd in c:
        qs = tuple(idx[q] for q in cmd.qubits)
        t = cmd.op.type
        if t == OpType.Rz:
            emit_rz(out, qs[0], math.pi * float(cmd.op.params[0]))
        elif t == OpType.H:
            out.append(("h", qs, None))
        elif t == OpType.CX:
            out.append(("cx", qs, None))
        elif t == OpType.Phase:
            continue
        else:
            raise ToolError(f"unexpected tket op {t}")
    return out


# ------------------------------------------------------------------------------ the toolbox
class Toolbox:
    """Public methods = the program API (see API_DOC). Private state is unreachable from programs."""

    def __init__(self, n: int, time_s: float = 120.0, cache: bool = True, gs=None):
        self._n = n
        self._time_s = float(time_s)
        self._charged = 0.0
        self._ledger = 0.0
        self._calls = {}
        self._cache = cache
        self._gs = gs or gridsynth()
        self._cost_memo = {}
        self._approx_log = []

    # ---------------------------------------------------------------- internals
    def _charge(self, sec: float):
        self._charged += sec
        if self._charged > self._time_s:
            raise BudgetError(f"time budget exceeded ({self._charged:.1f} s > {self._time_s:.0f} s charged CPU)")

    def _run(self, name: str, params, c: Circ, fn, with_meta: bool = False):
        """fn(ops, n) -> ops, or (ops, meta) when with_meta (meta is cached with the result)."""
        if not isinstance(c, Circ):
            raise ToolError(f"{name}: expected a circuit handle")
        self._calls[name] = self._calls.get(name, 0) + 1
        if self._charged > self._time_s:
            raise BudgetError("time budget exhausted")
        key = hashlib.sha256(json.dumps([TOOLBOX_VERSION, name, params, c.key()]).encode()).hexdigest()
        path = CACHE_ROOT / "tools" / key[:2] / f"{key}.json"
        if self._cache:
            hit = _read_json(path)
            if hit is not None:
                self._charge(hit["sec"])
                if hit.get("error"):
                    raise ToolError(hit["error"])
                out = Circ(ops_from_json(hit["ops"]), c._n)
                return (out, hit.get("meta")) if with_meta else out
        t0 = time.process_time()
        meta = None
        try:
            ops = fn(list(c._ops), c._n)
            if with_meta:
                ops, meta = ops
            err = None
        except BudgetError:
            raise
        except Exception as e:                                   # deterministic failure: cache it too
            ops, err = None, f"{name}: {type(e).__name__}: {str(e)[:200]}"
        sec = time.process_time() - t0
        if self._cache:
            _atomic_write(path, json.dumps(dict(sec=sec, error=err, meta=meta,
                                                ops=ops_to_json(ops) if ops is not None else None)))
        self._charge(sec)
        if err:
            raise ToolError(err)
        out = Circ(ops, c._n)
        return (out, meta) if with_meta else out

    def _cost(self, c: Circ) -> dict:
        k = c.key()
        if k not in self._cost_memo:
            from circuitevolve.blocks.cost_model import ops_cost
            ops = list(c._ops) if _is_clifford_rz(c._ops) else _lower(list(c._ops), c._n)
            t0 = time.process_time()
            self._cost_memo[k] = ops_cost(ops, self._gs)
            self._charge(time.process_time() - t0)
        return dict(self._cost_memo[k])

    def _ensure_crz(self, c: Circ) -> Circ:
        return c if _is_clifford_rz(c._ops) else self.lower(c)

    # ---------------------------------------------------------------- queries
    def stats(self, c) -> dict:
        """{'t','rz','t_fixed','t_gs','cx','gates','n'} of the circuit (T at gridsynth eps_rz = 1e-9)."""
        d = self._cost(c)
        d["n"] = c._n
        return d

    def t_count(self, c) -> int:
        return self._cost(c)["t"]

    def rz_count(self, c) -> int:
        return self._cost(c)["rz"]

    def cx_count(self, c) -> int:
        return self._cost(c)["cx"]

    def gate_count(self, c) -> int:
        return len(c._ops)

    def gridsynth_t(self, angle) -> int:
        """T-count of one rz(angle) synthesised at eps_rz (angle reduced to [-pi, pi])."""
        from circuitevolve.blocks.circuit_io import classify_angle
        a = math.remainder(float(angle), 2 * math.pi)
        k = classify_angle(a)
        return (k % 2) if k is not None else self._gs.t(a)

    def better(self, a, b) -> bool:
        """True if a is strictly cheaper than b (T, then #rz, then cx, then gates)."""
        from circuitevolve.blocks.cost_model import cost_key
        return cost_key(self._cost(a)) < cost_key(self._cost(b))

    def best(self, *cs):
        """The cheapest of the given circuits (T, then #rz, then cx, then gates). Accepts a list too."""
        from circuitevolve.blocks.cost_model import cost_key
        if len(cs) == 1 and isinstance(cs[0], (list, tuple)):
            cs = tuple(cs[0])
        cs = [c for c in cs if isinstance(c, Circ)]
        if not cs:
            raise ToolError("best: no circuits")
        return min(cs, key=lambda c: (cost_key(self._cost(self._ensure_crz(c))) if _is_clifford_rz(c._ops)
                                      else (float("inf"),)))

    def error_used(self) -> float:
        return self._ledger

    def error_left(self, c) -> float:
        """Approximation allowance still available if c were returned: 1e-6 - ledger - 1e-8 - #rz(c)*1e-9."""
        return ERROR_BUDGET - self._ledger - NUMERIC_SLACK - self._cost(c)["rz"] * EPS_RZ

    def time_left(self) -> float:
        return self._time_s - self._charged

    def tket_passes(self) -> list:
        return list(TKET_PASSES)

    # ---------------------------------------------------------------- exact transformations
    def lower(self, c):
        """Exact Clifford+Rz form (each merged 1q run with the minimal number of rz)."""
        return self._run("lower", None, c, _lower)

    def pyzx_full_reduce(self, c):
        return self._run("pyzx_full_reduce", None, self._ensure_crz(c), lambda o, n: _pyzx(o, n, "full_reduce"))

    def pyzx_teleport_reduce(self, c):
        return self._run("pyzx_teleport_reduce", None, self._ensure_crz(c),
                         lambda o, n: _pyzx(o, n, "teleport_reduce"))

    def pyzx_clifford_simp(self, c):
        return self._run("pyzx_clifford_simp", None, self._ensure_crz(c), lambda o, n: _pyzx(o, n, "clifford_simp"))

    def pyzx_basic(self, c):
        return self._run("pyzx_basic", None, self._ensure_crz(c), lambda o, n: _pyzx(o, n, "basic"))

    def tket(self, c, passes):
        """Apply TKET passes in order (a name or a list of names from tket_passes()), then rebase to CX,H,Rz."""
        if isinstance(passes, str):
            passes = [passes]
        passes = list(passes)
        bad = [p for p in passes if p not in TKET_PASSES]
        if bad or not passes:
            raise ToolError(f"tket: unknown passes {bad}; allowed {list(TKET_PASSES)}")
        return self._run("tket", passes, c, lambda o, n: _tket(o, n, passes))

    def phase_fold(self, c):
        """Whole-circuit phase-polynomial rotation merging (exact)."""
        from circuitevolve.blocks.passes import phase_fold
        return self._run("phase_fold", None, self._ensure_crz(c), phase_fold)

    def resynth_1q(self, c):
        """Every maximal 1q run rewritten with the minimal number of rz when that lowers the rz count."""
        from circuitevolve.blocks.passes import resynth_1q
        return self._run("resynth_1q", None, self._ensure_crz(c), resynth_1q)

    def fold_resynth(self, c, max_iter=6):
        """phase_fold and resynth_1q alternated until the rz/T/gate count stops improving."""
        from circuitevolve.blocks.passes import classical_pass
        mi = int(max(1, min(int(max_iter), 20)))
        return self._run("fold_resynth", mi, self._ensure_crz(c), lambda o, n: classical_pass(o, n, mi))

    def canonicalize(self, c):
        """rz angles reduced to [-pi, pi] (exact up to global phase)."""
        from circuitevolve.blocks.cost_model import canonicalize
        return self._run("canonicalize", None, self._ensure_crz(c), lambda o, n: canonicalize(o))

    # ---------------------------------------------------------------- block resynthesis
    def block_optimize(self, c, method="fold_resynth", block_size=3, max_gates=40, passes=None):
        """Partition (BQSKit QuickPartitioner(block_size), windows <= max_gates) and rewrite every block with
        `method` in BLOCK_METHODS ('tket' uses `passes`). A block rewrite is kept only if it is strictly
        cheaper (cost_model.improves) and within 1e-8 of the block (frozen verify_block.verify_instance);
        its measured distance is added to the error ledger."""
        if method not in BLOCK_METHODS:
            raise ToolError(f"block_optimize: method must be one of {BLOCK_METHODS}")
        bs, mg = int(block_size), int(max_gates)
        if bs not in (2, 3, 4) or not 4 <= mg <= 200:
            raise ToolError("block_optimize: block_size in {2,3,4}, 4 <= max_gates <= 200")
        if method == "tket":
            passes = [passes] if isinstance(passes, str) else list(passes or ["FullPeepholeOptimise"])
            if any(p not in TKET_PASSES for p in passes):
                raise ToolError("block_optimize: unknown tket pass")
        c = self._ensure_crz(c)
        left = self.error_left(c)
        params = [method, bs, mg, passes]
        out, d = self._run("block_optimize", params, c,
                           lambda o, n: _block_optimize(o, n, method, bs, mg, passes, self._gs), with_meta=True)
        d = float(d or 0.0)        # sum of the verified block distances (frozen verify_block.verify_instance)
        if d > left:
            raise BudgetError(f"block_optimize would use {d:.2e} > error left {left:.2e}")
        self._ledger += d
        self._approx_log.append(("block_optimize", d))
        return out

    # ---------------------------------------------------------------- approximation
    def approx_round(self, c, allowance):
        """Round rz angles to the nearest multiple of pi/4 (Clifford/T), smallest error first, while the
        summed error 2|sin(delta/4)| stays <= min(allowance, error_left). Adds the error to the ledger."""
        from circuitevolve.blocks.circuit_io import emit_rz
        c = self._ensure_crz(c)
        cap = min(float(allowance), self.error_left(c))
        if not cap > 0:
            return c
        ops = list(c._ops)
        cand = []
        for i, (g, qs, a) in enumerate(ops):
            if g == "rz":
                b = round(a / (math.pi / 4)) * (math.pi / 4)
                cand.append((2 * abs(math.sin((a - b) / 4)), i, b))
        cand.sort()
        used, repl = 0.0, {}
        for e, i, b in cand:
            if used + e > cap:
                break
            used += e
            repl[i] = b
        if not repl:
            return c
        out = []
        for i, op in enumerate(ops):
            if i in repl:
                emit_rz(out, op[1][0], repl[i])
            else:
                out.append(op)
        self._ledger += used
        self._approx_log.append(("approx_round", used))
        self._calls["approx_round"] = self._calls.get("approx_round", 0) + 1
        return Circ(out, c._n)


def _block_optimize(ops, n, method, bs, mg, passes, gs):
    from circuitevolve.blocks import verify_block as vb
    from circuitevolve.blocks.cost_model import improves, ops_cost
    from circuitevolve.blocks.partition import partition, to_global
    from circuitevolve.blocks.passes import classical_pass, phase_fold, resynth_1q
    out, dist = [], 0.0
    for b in partition(ops, n, bs, mg):
        try:
            if method == "fold":
                new = phase_fold(b.ops, b.n)
            elif method == "resynth_1q":
                new = resynth_1q(b.ops, b.n)
            elif method == "fold_resynth":
                new = classical_pass(b.ops, b.n)
            elif method == "pyzx":
                new = _pyzx(b.ops, b.n, "full_reduce")
            else:
                new = _tket(b.ops, b.n, passes)
        except Exception:
            new = b.ops
        if new != b.ops and improves(ops_cost(new, gs), ops_cost(b.ops, gs)):
            v = vb.verify_instance(b.ops, new, b.n)
            if v["ok"]:
                out.extend(to_global(b, new))
                dist += float(v["dist"])
                continue
        out.extend(to_global(b, b.ops))
    return out, dist


API_DOC = """\
Toolbox API (`tools`). Circuits are opaque handles; every tool returns a NEW handle. All tools are exact
unless marked APPROX. T is counted as explicit T gates + gridsynth T per rz at eps_rz = 1e-9.
  queries
    tools.stats(c) -> dict t, rz, t_fixed, t_gs, cx, gates, n      tools.t_count(c) / rz_count(c) / cx_count(c) / gate_count(c)
    tools.better(a, b) -> bool (a strictly cheaper)                 tools.best(c1, c2, ...) or tools.best([..]) -> cheapest
    tools.gridsynth_t(angle) -> int                                 tools.time_left() -> charged CPU seconds left
    tools.error_used() / tools.error_left(c) -> float               tools.tket_passes() -> list of pass names
  exact passes
    tools.lower(c)                 minimal-rz Clifford+Rz form of the input (the input `circ` is U3+CX)
    tools.pyzx_full_reduce(c)      pyzx full_reduce + extract + basic_optimization
    tools.pyzx_teleport_reduce(c)  pyzx teleport_reduce (phase teleportation, keeps circuit structure)
    tools.pyzx_clifford_simp(c)    pyzx clifford_simp + extract
    tools.pyzx_basic(c)            pyzx basic_optimization only
    tools.tket(c, passes)          passes: a name or list from tools.tket_passes(); output rebased to CX,H,Rz
    tools.phase_fold(c)            whole-circuit phase-polynomial rotation merging
    tools.resynth_1q(c)            minimal-rz resynthesis of every single-qubit run
    tools.fold_resynth(c, max_iter=6)  phase_fold and resynth_1q alternated to a fixed point
    tools.canonicalize(c)          rz angles reduced to [-pi, pi]
    tools.block_optimize(c, method='fold_resynth', block_size=3, max_gates=40, passes=None)
        partition into blocks; rewrite each with method in ('fold','resynth_1q','fold_resynth','pyzx','tket');
        a block rewrite is kept only if strictly cheaper and verified (<= 1e-8); its distance goes to the ledger
  APPROX
    tools.approx_round(c, allowance)  round rz angles to multiples of pi/4, smallest error first, total error
        <= min(allowance, tools.error_left(c)); error goes to the ledger
Budget: total error per circuit 1e-6 = ledger + 1e-8 numeric slack + #rz(output) * 1e-9. Exceeding the
time budget (budget['time_s'] charged CPU seconds) raises an error and the circuit fails.
The returned circuit must be one of these handles, in Clifford+Rz form (any tool output except the raw input).
"""
