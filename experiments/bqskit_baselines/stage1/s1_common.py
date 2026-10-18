"""Stage-1 baseline helpers (B0-B3), run with experiments/bqskit_baselines/.venv-dpf.

Protocol: skill `bqskit-ft-reference-baseline`. Every arm starts from the SAME TKET
FullPeepholeOptimise input (results/bqskit_baselines/stage1/inputs/<name>_tket.qasm).

Gridsynth: rsgridsynth v1.0.0 (git bff24e2), called exactly as bqskit-ft's GridSynthPass
(@2e99ba6, bqskit/ft/ftpasses/gridsynth.py): rsgridsynth.synth(f"{theta}", f"{precision}",
compute_error=True); gates are in matrix order (circuit order = reversed); 'W' (global phase) dropped.
"""
from __future__ import annotations

import gzip
import json
import math
import os
import time
from multiprocessing import get_context
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
QASM = REPO / 'benchmarks' / 'bqskit_qseed' / 'qasm'
OUT = REPO / 'results' / 'bqskit_baselines' / 'stage1'
INPUTS = OUT / 'inputs'
# S1_RUN_VERSION selects the run/output directories ('' = first pass runs/, outputs/; 'v2' = runs_v2/ ...)
_RV = os.environ.get('S1_RUN_VERSION', '')
RUNS = OUT / ('runs' + (f'_{_RV}' if _RV else ''))
OUTPUTS = OUT / ('outputs' + (f'_{_RV}' if _RV else ''))

CIRCUITS = ['qft/qft_8', 'qpe/qpe_8', 'qae/qae_13', 'heisenberg/heisenberg_6', 'tfim/tfim_6',
            'hubbard/hubbard_8', 'qml/qml_13', 'hhl/hhl_8']
EPS = [1e-3, 1e-5]
DPF_COMMIT = '2e99ba614d48970b9afefc0b8c32860c3a3dc9f1'
RSGRIDSYNTH_COMMIT = 'bff24e24b63d530f0f53851d9c0ae970a39ce0d4'


def short(name: str) -> str:
    return name.split('/')[-1]


def orig_path(name: str) -> Path:
    return QASM / f'{name}.qasm'


def input_path(name: str) -> Path:
    return INPUTS / f'{short(name)}_tket.qasm'


def eps_tag(eps: float) -> str:
    return f'e{int(round(-math.log10(eps)))}'


# ----------------------------------------------------------------------------- gridsynth
def _gs_one(args):
    theta, prec = args
    import rsgridsynth
    t0 = time.time()
    try:
        r = rsgridsynth.synth(f'{theta}', f'{prec}', compute_error=True)
    except BaseException as e:  # rsgridsynth panic (see run_bqskit_arms.patch_rsgridsynth_panic)
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        r = rsgridsynth.synth(f'{math.remainder(theta, 2 * math.pi)}', f'{prec}', compute_error=True)
    gates = ''.join(r.gates) if not isinstance(r.gates, str) else r.gates
    return theta, gates, float(r.error), time.time() - t0


def _gs_one_pyg(args):
    """pygridsynth 2.0.0 (deterministic, pure function of (theta, eps)); error re-computed by matrix product."""
    theta, prec = args
    import mpmath
    from pygridsynth.gridsynth import gridsynth_gates
    mpmath.mp.dps = 128
    t0 = time.time()
    w = str(gridsynth_gates(mpmath.mpmathify(theta), mpmath.mpmathify(prec)))
    return theta, w, word_distance(w, theta), time.time() - t0


def word_distance(word: str, theta: float) -> float:
    """Phase-invariant operator-norm distance between a gridsynth word (matrix order) and Rz(theta)."""
    s2 = 1 / math.sqrt(2)
    G = {'H': np.array([[s2, s2], [s2, -s2]], complex), 'S': np.diag([1, 1j]),
         'T': np.diag([1, np.exp(1j * math.pi / 4)]), 'X': np.array([[0, 1], [1, 0]], complex),
         'W': np.exp(1j * math.pi / 4) * np.eye(2), 'I': np.eye(2)}
    U = np.eye(2, dtype=complex)
    for g in word:
        U = U @ G[g]
    R = np.diag([np.exp(-0.5j * theta), np.exp(0.5j * theta)])
    tr = np.trace(R.conj().T @ U)
    ph = tr / abs(tr) if abs(tr) > 0 else 1.0
    return float(np.linalg.norm(U - ph * R, 2))


def gridsynth_words(angles, prec: float, procs: int | None = None, impl: str = 'rs') -> dict:
    """{theta: (word_matrix_order, error, seconds)} for each DISTINCT float angle.

    impl='rs': rsgridsynth (as bqskit-ft GridSynthPass). NOTE: rsgridsynth v1.0.0 is not a pure function:
    its output for a given (theta, eps) depends on earlier calls in the same process (see README).
    impl='pyg': pygridsynth 2.0.0, deterministic; used for the canonical T recount.
    """
    uniq = sorted(set(float(a) for a in angles))
    if not uniq:
        return {}
    fn = _gs_one if impl == 'rs' else _gs_one_pyg
    procs = procs or int(os.environ.get('S1_GS_PROCS', '4'))
    if len(uniq) < 8 or procs <= 1:
        res = [fn((a, prec)) for a in uniq]
    else:
        with get_context('spawn').Pool(procs) as pool:
            res = pool.map(fn, [(a, prec) for a in uniq], chunksize=4)
    out = {}
    for a, w, err, dt in res:
        if err > prec * (1 + 1e-9):
            raise ValueError(f'gridsynth error {err} > {prec} for {a}')
        out[a] = (w, err, dt)
    return out


# ----------------------------------------------------------------------------- qiskit IO
def load_qiskit(path: Path | str):
    from qiskit import QuantumCircuit
    p = Path(path)
    txt = gzip.open(p, 'rt').read() if p.suffix == '.gz' else p.read_text()
    return QuantumCircuit.from_qasm_str(txt)


def write_qasm(qc, path: Path):
    from qiskit import qasm2
    path.parent.mkdir(parents=True, exist_ok=True)
    txt = qasm2.dumps(qc)
    if path.suffix == '.gz':
        with gzip.open(path, 'wt') as f:
            f.write(txt)
    else:
        path.write_text(txt)


def quarter(theta: float, tol: float = 1e-10):
    """k in 0..7 if theta = k*pi/4 (mod 2pi) within tol, else None."""
    x = theta / (math.pi / 4)
    r = round(x)
    return int(r) % 8 if abs(x - r) * math.pi / 4 <= tol else None


CLIFF_1Q = {'h', 'x', 'y', 'z', 's', 'sdg', 'sx', 'sxdg', 'id'}
T_1Q = {'t', 'tdg'}
TWOQ_CX = {'cx': 1, 'cz': 1, 'swap': 3}
_KGATES = {0: [], 1: ['t'], 2: ['s'], 3: ['s', 't'], 4: ['z'], 5: ['z', 't'], 6: ['sdg'], 7: ['tdg']}


def lower_clifford_rz(qc, eps_total: float, impl: str = 'rs', eps_per_rz: float | None = None):
    """Clifford+Rz(+Rx) qiskit circuit -> Clifford+T via gridsynth at eps_total / N_Rz per rotation.

    Rotations with angle k*pi/4 are emitted exactly (T-count k mod 2). rx(t) = h rz(t) h.
    Returns (qc_cliffordT, stats).
    """
    from qiskit import QuantumCircuit
    rots = []
    for ins in qc.data:
        nm = ins.operation.name
        if nm in ('rz', 'rx', 'p', 'u1'):
            th = float(ins.operation.params[0])
            if quarter(th) is None:
                rots.append(th)
        elif nm in CLIFF_1Q | T_1Q | set(TWOQ_CX) | {'barrier'} or nm.startswith('identity'):
            pass
        else:
            raise ValueError(f'unsupported gate {nm}')
    n_rz = len(rots)
    prec = eps_per_rz if eps_per_rz is not None else (eps_total / n_rz if n_rz else eps_total)
    t0 = time.time()
    words = gridsynth_words(rots, prec, impl=impl)
    gs_s = time.time() - t0
    out = QuantumCircuit(qc.num_qubits)
    cnt = dict(t_fixed=0, t_gs=0, cx=0)
    qidx = {q: i for i, q in enumerate(qc.qubits)}

    def emit_rz(th, q):
        k = quarter(th)
        if k is not None:
            cnt['t_fixed'] += k % 2
            for g in _KGATES[k]:
                getattr(out, g)(q)
            return
        w = words[float(th)][0]
        cnt['t_gs'] += w.count('T')
        for g in reversed(w):
            if g == 'H':
                out.h(q)
            elif g == 'S':
                out.s(q)
            elif g == 'T':
                out.t(q)
            elif g == 'X':
                out.x(q)
            elif g in ('W', 'I'):  # global phase / identity (GridSynthPass also ignores them)
                pass
            else:
                raise ValueError(g)

    for ins in qc.data:
        nm = ins.operation.name
        qs = [qidx[q] for q in ins.qubits]
        if nm == 'barrier' or nm.startswith('identity'):  # bqskit writes IdentityGate as identity1
            continue
        if nm in ('rz', 'p', 'u1'):
            emit_rz(float(ins.operation.params[0]), qs[0])
        elif nm == 'rx':
            out.h(qs[0])
            emit_rz(float(ins.operation.params[0]), qs[0])
            out.h(qs[0])
        elif nm in T_1Q:
            cnt['t_fixed'] += 1
            getattr(out, nm)(qs[0])
        elif nm in CLIFF_1Q:
            if nm != 'id':
                getattr(out, nm)(qs[0])
        elif nm in TWOQ_CX:
            cnt['cx'] += TWOQ_CX[nm]
            getattr(out, nm)(*qs)
    stats = dict(n_rz=n_rz, rz_distinct=len(set(rots)), eps_per_rz=prec, t_fixed=cnt['t_fixed'],
                 t_gridsynth=cnt['t_gs'], t_count=cnt['t_fixed'] + cnt['t_gs'], cx=cnt['cx'],
                 gridsynth_s=round(gs_s, 2),
                 gs_max_reported_err=max((v[1] for v in words.values()), default=0.0),
                 err_bound_gridsynth=n_rz * prec)
    return out, stats


def count_ct(qc):
    """T-count / CX count / leftover-rotation count of a (nominally) Clifford+T qiskit circuit."""
    ops = qc.count_ops()
    t = ops.get('t', 0) + ops.get('tdg', 0)
    cx = sum(ops.get(k, 0) * v for k, v in TWOQ_CX.items())
    left = {k: v for k, v in ops.items() if k not in CLIFF_1Q | T_1Q | set(TWOQ_CX) | {'barrier'}}
    rz_nonq = 0
    for ins in qc.data:
        if ins.operation.name in ('rz', 'u1', 'p'):
            k = quarter(float(ins.operation.params[0]))
            if k is None:
                rz_nonq += 1
            else:
                t += k % 2
    return dict(t_count=t, cx=cx, other_ops=left, residual_rz=rz_nonq, n_ops=sum(ops.values()))


# ----------------------------------------------------------------------------- equivalence
def state_distance(ref, cand, nstates: int = 2, seed: int = 1234):
    """max over Haar-random |psi> of min_phi || U|psi> - e^{i phi} V|psi> ||  (= sqrt(2-2|<a|b>|)).

    A lower bound on the phase-aligned operator-norm distance ||U - e^{i phi} V||.
    """
    from qiskit.quantum_info import Statevector, random_statevector  # noqa: F401
    assert ref.num_qubits == cand.num_qubits
    ref = ref.remove_final_measurements(inplace=False)
    worst = 0.0
    for i in range(nstates):
        psi = random_statevector(2 ** ref.num_qubits, seed=seed + i)
        a = psi.evolve(ref).data
        b = psi.evolve(cand).data
        ov = np.vdot(b, a)
        ph = ov / abs(ov) if abs(ov) > 0 else 1.0
        # direct norm (not sqrt(2-2|ov|), which has a ~1e-7 floating-point floor)
        worst = max(worst, float(np.linalg.norm(a - ph * b)))
    return worst


def dump_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    os.replace(tmp, path)
