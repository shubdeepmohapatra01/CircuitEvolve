"""BQSKit arms on the shared TKET inputs (bqskit-ft @ 2e99ba6, branch algorithmic_error_dpf).

One job = (circuit, arm, eps), run in its own process:
  .venv-dpf/bin/python stage1/run_bqskit_arms.py --job qft/qft_8 B3 1e-3

Arms
  B2    paper "Baseline": BQSKit-FT Clifford+RZ retarget exactly as alg_err_workflow.full_rz_compile's
        first stage (CliffordRZModel, epsilon_per_gate = eps/(num_params+1), optimization_level 1),
        then bqskit-ft GridSynthPass (rsgridsynth) at algorithmic_error = eps -> eps / N_Rz per Rz.
        No DPF.
  B2ft  (supplementary) the branch's default Clifford+T compile:
        compile(circ, CliffordTModel(n, algorithmic_error=eps)). NOTE on this branch the default
        Clifford+T workflow itself contains DPFPass(k=3) per 3-qubit block, so it is NOT DPF-free.
  B3    published Dyadic Phase Fixing script, vendor/alg_err_workflow.py (verbatim copy of the file at
        2e99ba6, sha256 80b47c9f...), __main__ logic: full_rz_compile(circ, error=eps) then
        compile_rz_to_clifft(rz_circ, success_threshold=eps). ONE unavoidable deviation:
        the script calls DPFPass(success_threshold=error / part_circ.num_operations) but DPFPass.__init__
        at this commit only accepts (cost, k) -> TypeError. We substitute a subclass that accepts the
        keyword and supplies it to DPFPass through PassData['algorithmic_error'] (the only channel
        DPFPass.run reads) -- i.e. the evident intent, per-block threshold eps/B.
  B3m   (supplementary, budget-matched) same functions, but error split so the code-accounted total
        is <= eps: full_rz_compile(error=0.4 eps) and CliffordTModel(algorithmic_error=0.2 eps) for the
        Clifford+T stage (B3 itself ignores its err_per_gate argument; see ERROR_ACCOUNTING.md).
  B3g   (supplementary, diagnostic) full_rz_compile(error=0.4 eps) (stage A + DPF exactly as the script),
        then bqskit-ft GridSynthPass directly at algorithmic_error = 0.4 eps (eps_rz = 0.4 eps / N_Rz),
        i.e. WITHOUT the script's second CliffordTModel compile (which re-derives ZXZXZ Euler angles
        and adds Rz gates). Code-accounted total <= 0.2 + 0.4 + 0.4 = 1.0 eps.

BQSKit's Compiler binds a localhost socket (forbidden in this sandbox): SerialCompiler runs each
task in-process on the serial runtime of ../serial_runtime.py, deep-copying circuit and workflow
first (the real runtime pickles both, so in-place mutation semantics match).
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import gzip
import json
import os
import sys
import time
import traceback
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE / 'vendor'))

import u12rz_shim  # noqa: E402

u12rz_shim.install()  # bqskit.passes.rules.u12rz is missing from every bqskit release/branch; see shim

from s1_common import (OUTPUTS, RUNS, count_ct, dump_json, eps_tag, input_path, load_qiskit,  # noqa: E402
                       orig_path, short, state_distance)

LOG: dict = {'gridsynth_calls': [], 'dpf_thresholds': [], 'assign_errors': [], 'partitions': []}


# ----------------------------------------------------------------------------- serial compiler
def make_serial_compiler():
    import serial_runtime
    from bqskit.compiler.compiler import Compiler
    from bqskit.compiler.passdata import PassData
    from bqskit.compiler.workflow import Workflow

    class SerialCompiler(Compiler):
        def __init__(self):  # no server, no socket
            self.p = None
            self.conn = None
            self._res = {}

        def submit(self, circuit, workflow, request_data=False, logging_level=None,
                   max_logging_depth=-1, data=None):
            serial_runtime.install()
            circ = circuit.copy()
            wf = Workflow(copy.deepcopy(workflow))
            pd = PassData(circ)
            if data is not None:
                pd.update(data)
            asyncio.run(wf.run(circ, pd))
            tid = uuid.uuid4()
            self._res[tid] = (circ, pd) if request_data else circ
            return tid

        def result(self, task_id):
            return self._res.pop(task_id)

        def compile(self, circuit, workflow, request_data=False, logging_level=None,
                    max_logging_depth=-1, data=None):
            return self.result(self.submit(circuit, workflow, request_data, logging_level,
                                           max_logging_depth, data))

        def close(self):
            pass

        def __del__(self):
            pass

    return SerialCompiler()


_FRESH = ("import json,sys,rsgridsynth;r=rsgridsynth.synth(sys.argv[1],sys.argv[2],compute_error=True);"
          "print(json.dumps(dict(gates=''.join(r.gates),error=float(r.error))))")


def patch_rsgridsynth_panic():
    """rsgridsynth v1.0.0 occasionally panics ('Invalid coefficients for inverse sqrt2 multiplication').
    The panic depends on process state, not only on (theta, precision): a call that panics inside a
    long run succeeds 30/30 times in a fresh interpreter, while in-process retries keep panicking.
    On a panic ONLY we re-run the IDENTICAL call (same theta and precision strings) in a fresh
    subprocess of the same venv (up to 3 attempts). Logged in LOG['gridsynth_panic_retries'].
    """
    import subprocess
    import types
    import rsgridsynth as _rs
    import bqskit.ft.ftpasses.gridsynth as gsmod
    LOG.setdefault('gridsynth_panic_retries', [])

    def synth(theta_s, prec_s, **kw):
        try:
            return _rs.synth(theta_s, prec_s, **kw)
        except BaseException as e:  # pyo3 PanicException derives from BaseException
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            rec = dict(theta=theta_s, precision=prec_s, error=str(e)[:120])
            LOG['gridsynth_panic_retries'].append(rec)
            for i in range(3):
                p = subprocess.run([sys.executable, '-c', _FRESH, theta_s, prec_s], capture_output=True, text=True)
                if p.returncode == 0:
                    d = json.loads(p.stdout.strip().splitlines()[-1])
                    rec['resolved_by'] = f'fresh subprocess attempt {i + 1}'
                    return types.SimpleNamespace(gates=list(d['gates']), error=d['error'])
            raise RuntimeError(f'rsgridsynth panicked in-process and in 3 fresh subprocesses: {rec}')
    gsmod.rsgridsynth = types.SimpleNamespace(synth=synth)


def instrument():
    """Record (without changing) gridsynth precision / N_Rz, DPF thresholds, block counts."""
    from bqskit.ft.ftpasses.gridsynth import GridSynthPass
    from bqskit.ft.cliffordt import defaultworkflow as dw
    from bqskit.ft.ftpasses.dpf import DPFPass

    g_run = GridSynthPass.run

    async def gs_run(self, circuit, data):
        ae = next((data[k] for k in data.keys() if 'algorithmic_error' in k), None)
        n = circuit.num_params
        LOG['gridsynth_calls'].append(dict(num_rzs=n, algorithmic_error=ae,
                                           precision_per_rz=(ae / n) if (ae and n) else None))
        if LOG.get('dump_pregs'):  # save the exact circuit handed to GridSynthPass (for the canonical recount)
            tmp = str(LOG['dump_pregs']) + '.tmp.qasm'
            circuit.save(tmp)
            with open(tmp) as fi, gzip.open(LOG['dump_pregs'], 'wt') as fo:
                fo.write(fi.read())
            os.unlink(tmp)
        await g_run(self, circuit, data)
    GridSynthPass.run = gs_run

    a_run = dw.AssignErrors.run

    async def ae_run(self, circuit, data):
        nb = sum(1 for op in circuit.operations() if op.gate.__class__.__name__ == 'CircuitGate')
        LOG['assign_errors'].append(dict(num_blocks=nb, algorithmic_error=data['algorithmic_error']))
        await a_run(self, circuit, data)
    dw.AssignErrors.run = ae_run

    d_run = DPFPass.run

    async def dpf_run(self, circuit, data):
        thr = next((data[k] for k in data.keys() if 'algorithmic_error' in k), None)
        LOG['dpf_thresholds'].append(thr)
        await d_run(self, circuit, data)
    DPFPass.run = dpf_run


def patched_alg_err_workflow():
    import alg_err_workflow as aew
    from bqskit.ft.ftpasses.dpf import DPFPass

    class DPFPassWithThreshold(DPFPass):
        """Accepts the script's success_threshold kwarg (absent from DPFPass at 2e99ba6)."""

        def __init__(self, success_threshold=None, **kw):
            super().__init__(**kw)
            self._thr = success_threshold

        async def run(self, circuit, data):
            if self._thr is not None:
                data['algorithmic_error'] = self._thr
            await super().run(circuit, data)

    aew.DPFPass = DPFPassWithThreshold
    p_orig = aew.partition_circ

    def partition_circ(circ, compiler, block_size=4):
        pc = p_orig(circ, compiler, block_size)
        LOG['partitions'].append(dict(num_blocks=pc.num_operations, block_size=block_size,
                                      partitioner='Quick' if (circ.num_qudits > 30 or circ.num_operations > 600) else 'Scan',
                                      ops_before=circ.num_operations))
        return pc
    aew.partition_circ = partition_circ
    return aew


def gate_summary(c):
    return {str(g): n for g, n in c.gate_counts.items()}


def bq_counts(c):
    from bqskit.ir.gates import RZGate, TGate, TdgGate
    return dict(rz=c.count(RZGate()), t=c.count(TGate()) + c.count(TdgGate()), params=c.num_params,
                ops=c.num_operations)


# ----------------------------------------------------------------------------- arms
def run_job(name, arm, eps):
    from bqskit.compiler.compile import compile as bq_compile
    from bqskit.ft.cliffordrz.cliffordrzmodel import CliffordRZModel
    from bqskit.ft.cliffordt.cliffordtmodel import CliffordTModel
    from bqskit.ft.ftpasses.gridsynth import GridSynthPass
    from bqskit.ir.circuit import Circuit
    from bqskit.passes.util.update import UpdateDataPass

    tag = f'{short(name)}_{arm}_{eps_tag(eps)}'
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    LOG['dump_pregs'] = OUTPUTS / f'{tag}_pregs.qasm.gz'
    instrument()
    patch_rsgridsynth_panic()
    aew = patched_alg_err_workflow()
    compiler = make_serial_compiler()
    circ = Circuit.from_file(str(input_path(name)))
    stages = {'input': bq_counts(circ)}
    t0 = time.time()
    if arm == 'B2':
        eps_pg = eps / (circ.num_params + 1)
        rz = bq_compile(circ, model=CliffordRZModel(circ.num_qudits, epsilon_per_gate=eps_pg), compiler=compiler)
        stages['clifford_rz'] = bq_counts(rz)
        stages['clifford_rz']['eps_per_gate'] = eps_pg
        rz_saved = rz
        out = compiler.compile(rz, [UpdateDataPass('algorithmic_error', eps), GridSynthPass()])
    elif arm == 'B2ft':
        rz_saved = None
        out = bq_compile(circ, model=CliffordTModel(circ.num_qudits, algorithmic_error=eps), compiler=compiler)
    elif arm == 'B3g':
        rz = aew.full_rz_compile(circ, compiler, error=0.4 * eps)
        stages['after_dpf'] = bq_counts(rz)
        stages['after_dpf']['elapsed_s'] = round(time.time() - t0, 1)
        rz_saved = rz
        out = compiler.compile(rz, [UpdateDataPass('algorithmic_error', 0.4 * eps), GridSynthPass()])
    elif arm in ('B3', 'B3m'):
        e1 = eps if arm == 'B3' else 0.4 * eps
        rz = aew.full_rz_compile(circ, compiler, error=e1)
        stages['after_dpf'] = bq_counts(rz)
        rz_saved = rz
        t_mid = time.time()
        stages['after_dpf']['elapsed_s'] = round(t_mid - t0, 1)
        if arm == 'B3':
            out = aew.compile_rz_to_clifft(rz, compiler, success_threshold=eps)
        else:
            out = bq_compile(rz, model=CliffordTModel(rz.num_qudits, algorithmic_error=0.2 * eps), compiler=compiler)
    else:
        raise ValueError(arm)
    runtime = time.time() - t0
    stages['output'] = bq_counts(out)
    outp = OUTPUTS / f'{tag}.qasm.gz'
    tmpq = OUTPUTS / f'{tag}.tmp.qasm'
    out.save(str(tmpq))
    with open(tmpq) as fi, gzip.open(outp, 'wt') as fo:
        fo.write(fi.read())
    tmpq.unlink()
    if rz_saved is not None:
        rzp = OUTPUTS / f'{tag}_cliffrz.qasm'
        rz_saved.save(str(rzp))
        with open(rzp) as fi, gzip.open(str(rzp) + '.gz', 'wt') as fo:
            fo.write(fi.read())
        rzp.unlink()
    # metrics from the written QASM (same parser as B0/B1)
    qc = load_qiskit(outp)
    cc = count_ct(qc)
    tv = time.time()
    d_orig = state_distance(load_qiskit(orig_path(name)), qc)
    d_in = state_distance(load_qiskit(input_path(name)), qc)
    d_rz = None
    if rz_saved is not None:
        d_rz = state_distance(load_qiskit(input_path(name)), load_qiskit(str(OUTPUTS / f'{tag}_cliffrz.qasm.gz')))
    gs = LOG['gridsynth_calls'][-1] if LOG['gridsynth_calls'] else {}
    return dict(circuit=short(name), arm=arm, eps=eps, status='ok', t_count=cc['t_count'], cx=cc['cx'],
                n_rz=gs.get('num_rzs'), eps_per_rz=gs.get('precision_per_rz'),
                gridsynth_algorithmic_error=gs.get('algorithmic_error'),
                residual_rz=cc['residual_rz'], other_ops=cc['other_ops'], runtime_s=round(runtime, 1),
                verify_s=round(time.time() - tv, 1), state_dist_vs_orig=d_orig, state_dist_vs_input=d_in,
                state_dist_input_vs_cliffrz=d_rz, stages=stages, gate_counts=gate_summary(out),
                log={k: (v if k != 'dpf_thresholds' else dict(n=len(v), distinct=sorted(set(map(float, filter(None, v))))))
                     for k, v in LOG.items()},
                output=outp.name, bqskit_ft_commit='2e99ba614d48970b9afefc0b8c32860c3a3dc9f1')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', nargs=3, metavar=('CIRCUIT', 'ARM', 'EPS'), required=True)
    a = ap.parse_args()
    name, arm, eps = a.job[0], a.job[1], float(a.job[2])
    f = RUNS / f'{short(name)}_{arm}_{eps_tag(eps)}.json'
    if f.exists():
        prev = json.loads(f.read_text())
        if prev.get('status') == 'ok':
            print('exists', f.name)
            return
        # keep failed attempts (append-only): move aside with a timestamp
        f.rename(f.with_name(f.stem + f'.failed_{int(f.stat().st_mtime)}.json'))
    t0 = time.time()
    try:
        r = run_job(name, arm, eps)
    except BaseException as e:  # incl. pyo3 PanicException
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        r = dict(circuit=short(name), arm=arm, eps=eps, status='error', error=f'{type(e).__name__}: {e}',
                 traceback=traceback.format_exc()[-3000:], wall_s=round(time.time() - t0, 1), log=LOG)
    dump_json(r, f)
    print(json.dumps({k: r.get(k) for k in ('circuit', 'arm', 'eps', 'status', 't_count', 'n_rz', 'cx',
                                             'runtime_s', 'state_dist_vs_orig', 'error')}), flush=True)


if __name__ == '__main__':
    main()
