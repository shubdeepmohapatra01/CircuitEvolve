"""R-DPF-PK: the paper's full 'DPF Synth' arm (DPF + phase-kickback), bqskit-ft @ greedy_ntro c04a322.

Why a new module instead of reusing stage1/run_bqskit_arms.py's B3g:
  B3g runs `DPFPass(k=3)` + `ConvertFractionalRZPass(max_k=3)`, so only angles on the pi/4 grid are
  fixed and everything else returns to gridsynth (dpf.py:62 carries the upstream comment
  "TODO: Make k a parameter to use PKAC"). The paper's DPF Synth additionally lowers fixed dyadic
  Rz with k <= k_reg onto a SHARED phase-gradient register via Gidney adders. That lowering lives
  only on branch `greedy_ntro`, where `GreedyNTROPass(max_k, success_threshold)` generalises DPFPass
  to arbitrary k (so dpf.py is not needed) and `ConvertToPKAC` builds the register.

Pipeline (paper Sec. III-IV steps 1-6):
  1. TKET FullPeepholeOptimise            -- already applied; our inputs ARE the TKET outputs
  2. CliffordRZModel(epsilon_per_gate = error / (num_params + 1))
  3. ScanPartitioner(4)  (QuickPartitioner if > 30 qudits or > 600 ops)
  4. ForEachBlockPass([ GreedyNTROPass(max_k = K, success_threshold = error / num_blocks) ])
  5. UnfoldPass
  6. ConvertToPKAC(max_k = K, add_measurements = False, use_catalyzed_sqrt_t = ...)
  then GridSynthPass at algorithmic_error for every Rz that survived.

Deviations from the published code, all deliberate and reported:
  * `PKACtoGatesPass` is NOT run. Its own docstring: it "does *not* keep the unitary of the circuit
    the same, since we replace LogicalAndInverses with an H gate and control Z (which is applied 50%
    of the time)" -- it mocks measurement outcomes with random.rand() < 0.5 to feed lattice-surgery
    tilers. Including it would make the T-count nondeterministic and the circuit wrong. T-count is
    read off the PKAC-form circuit instead, where the gadgets still carry their true T content.
  * k_reg is NOT chosen by the paper's decision matrix (not present in the public code;
    ConvertToPKAC takes max_k from the caller). We sweep K and report the minimum T-count, which is
    a faithful stand-in for "picks k_reg, falls back to gridsynth when that is cheaper" but is OUR
    code, not theirs.
  * `MidCircuitMeasurement` is shimmed (midmeasure_shim.py) purely so `bqskit.ft` imports; our
    pipeline never instantiates it.

T accounting after unfold_all():
  explicit TGate/TdgGate + 1 per odd pi/4 multiple of a surviving RZGate + gridsynth T for the rest.
  LogicalAndDgGate is the measurement-based temporary-AND uncompute (Gidney 2018) and costs 0 T;
  its count is reported separately as `logical_and_dg` so the zero is visible, and each
  LogicalAndGate unfolds to 2 Tdg + 1 T with a further T on the freshly prepared ancilla (4 T/AND).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / 'stage1'))

import midmeasure_shim  # noqa: E402
import u12rz_shim       # noqa: E402

midmeasure_shim.install()
u12rz_shim.install()

BQSKIT_FT_COMMIT = 'c04a32245d88a0877277dccbcb8001cd85a7eef0'   # branch greedy_ntro


def serial_compiler():
    """SerialCompiler from stage1/run_bqskit_arms.py (BQSKit's Compiler binds a localhost socket)."""
    import run_bqskit_arms
    return run_bqskit_arms.make_serial_compiler()


def partition(circ, compiler, block_size: int = 4):
    from bqskit.passes.partitioning import QuickPartitioner, ScanPartitioner
    p = (QuickPartitioner(block_size) if (circ.num_qudits > 30 or circ.num_operations > 600)
         else ScanPartitioner(block_size))
    return compiler.compile(circ, [p])


def dpf_pk_compile(circ, compiler, error: float, max_k: int, use_catalyzed_sqrt_t: bool = True):
    """Steps 2-6. Returns (circuit, info)."""
    from bqskit.compiler.compile import compile as bq_compile
    from bqskit.ft.cliffordrz.cliffordrzmodel import CliffordRZModel
    from bqskit.ft.ftpasses.convert_to_pkac import ConvertToPKAC
    from bqskit.ft.ftpasses.greedy_ntro import GreedyNTROPass
    from bqskit.passes.control.foreach import ForEachBlockPass
    from bqskit.passes.util.unfold import UnfoldPass

    info = {}
    eps_per_gate = error / (circ.num_params + 1)
    info['eps_per_gate'] = eps_per_gate
    rz_circ = bq_compile(circ, model=CliffordRZModel(circ.num_qudits, epsilon_per_gate=eps_per_gate),
                         compiler=compiler)
    info['after_cliffordrz'] = counts(rz_circ)

    part = partition(rz_circ, compiler, 4)
    n_blocks = part.num_operations
    info['num_blocks'] = n_blocks
    info['block_threshold'] = error / n_blocks if n_blocks else error

    out = compiler.compile(part, [
        ForEachBlockPass([GreedyNTROPass(max_k=max_k, success_threshold=error / n_blocks)]),
        UnfoldPass(),
    ])
    info['after_greedy_ntro'] = counts(out)

    out = compiler.compile(out, [
        ConvertToPKAC(max_k=max_k, add_measurements=False,
                      use_catalyzed_sqrt_t=use_catalyzed_sqrt_t),
        UnfoldPass(),
    ])
    info['after_pkac'] = counts(out)
    info['max_k'] = max_k
    return out, info


def counts(c) -> dict:
    from bqskit.ir.gates import RZGate, TGate, TdgGate
    return dict(qudits=c.num_qudits, ops=c.num_operations, params=c.num_params,
                rz=c.count(RZGate()), t=c.count(TGate()) + c.count(TdgGate()))


def gate_histogram(c) -> dict:
    return {str(g): int(n) for g, n in c.gate_counts.items()}


def canonical_t_count(circ, eps_synth: float) -> dict:
    """T-count of a PKAC-form circuit under the SAME convention as stage1/canonical.py's
    `t_count_canon` (the authoritative column of stage1_baselines_v2.csv, and the one v3 reads):
    explicit T/Tdg, plus 1 per odd pi/4 multiple of a surviving RZ, plus pygridsynth 2.0.0
    (mpmath dps 128, deterministic) at eps_rz = eps_synth / N_Rz for every other RZ.

    rsgridsynth is deliberately NOT used: s1_common.gridsynth_words documents that rsgridsynth v1.0.0
    is not a pure function of (theta, eps) - its word depends on earlier calls in the same process,
    moving whole-circuit T-counts by a few percent. Every other arm is counted canonically, so this
    one is too.

    LogicalAndDgGate is the measured temporary-AND uncompute (Gidney 2018) and contributes 0 T; it is
    counted and reported so the zero is explicit rather than silent.
    """
    import math
    import mpmath
    from pygridsynth.gridsynth import gridsynth_gates
    from bqskit.ft.gates.logical_and import LogicalAndDgGate
    from bqskit.ir.gates import RZGate, TGate, TdgGate
    sys.path.insert(0, str(HERE.parent / 'stage1'))
    from s1_common import quarter, word_distance

    mpmath.mp.dps = 128
    t_explicit = circ.count(TGate()) + circ.count(TdgGate())
    angles = [float(op.params[0]) for op in circ.operations() if isinstance(op.gate, RZGate)]
    t_quarter = sum(q % 2 for q in (quarter(a) for a in angles) if q is not None)
    to_synth = [a for a in angles if quarter(a) is None]
    n_rz = len(to_synth)
    eps_rz = (eps_synth / n_rz) if n_rz else None
    t_gs, worst = 0, 0.0
    if n_rz:
        words = {}
        for a in set(to_synth):
            w = str(gridsynth_gates(mpmath.mpmathify(a), mpmath.mpmathify(eps_rz)))
            words[a] = w
            worst = max(worst, word_distance(w, a))
        t_gs = sum(words[a].count('T') for a in to_synth)
    return dict(t_count=int(t_explicit + t_quarter + t_gs), t_explicit=int(t_explicit),
                t_quarter_rz=int(t_quarter), t_gridsynth=int(t_gs),
                n_rz_synthesized=n_rz, eps_rz=eps_rz,
                worst_word_distance=worst, eps_rz_respected=bool(n_rz == 0 or worst <= eps_rz),
                logical_and_dg=int(circ.count(LogicalAndDgGate())))


def run_arm(name_or_path, eps: float, max_k: int, split=(0.4, 0.4),
            use_catalyzed_sqrt_t: bool = True) -> dict:
    """Full R-DPF-PK arm at one (circuit, eps, K).

    Error split follows B3g exactly so the arms are comparable: split[0]*eps to the
    CliffordRZ + GreedyNTRO stage, split[1]*eps to final synthesis, 0.2*eps slack for the retarget,
    i.e. a code-accounted total <= eps.
    """
    import time
    from bqskit.ir.circuit import Circuit
    sys.path.insert(0, str(HERE.parent / 'stage1'))
    from s1_common import input_path

    p = str(name_or_path)
    if not p.endswith('.qasm'):
        p = str(input_path(p))
    compiler = serial_compiler()
    circ = Circuit.from_file(p)
    n_in = circ.num_qudits
    t0 = time.time()
    pk, info = dpf_pk_compile(circ, compiler, error=split[0] * eps, max_k=max_k,
                              use_catalyzed_sqrt_t=use_catalyzed_sqrt_t)
    t_pk = time.time() - t0
    m = canonical_t_count(pk, split[1] * eps)
    return dict(
        input=os.path.basename(p), eps=eps, max_k=max_k, arm='B4',
        bqskit_ft_commit=BQSKIT_FT_COMMIT,
        qubits_in=n_in, qubits_out=int(pk.num_qudits), ancillas=int(pk.num_qudits) - n_in,
        num_blocks=info['num_blocks'], block_threshold=info['block_threshold'],
        eps_split=dict(dpf=split[0] * eps, synth=split[1] * eps),
        err_bound_accounted=(split[0] + split[1] + 0.2) * eps,
        contract='relaxed (measured temporary-AND uncompute: ancillas + mid-circuit measurement)',
        seconds_pk=round(t_pk, 1), seconds_total=round(time.time() - t0, 1),
        stages=info, gates=gate_histogram(pk), **m)
