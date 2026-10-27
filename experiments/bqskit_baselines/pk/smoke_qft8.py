import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dpf_pk
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'stage1'))
from s1_common import input_path
from bqskit.ir.circuit import Circuit
from bqskit.ir.gates import RZGate, TGate, TdgGate
from bqskit.ft.gates.logical_and import LogicalAndDgGate

name = sys.argv[1] if len(sys.argv) > 1 else 'qft/qft_8'
eps = float(sys.argv[2]) if len(sys.argv) > 2 else 1e-3
Ks = [int(x) for x in (sys.argv[3].split(',') if len(sys.argv) > 3 else ['4','5','6'])]
p = input_path(name)
print('input:', p, flush=True)
for K in Ks:
    circ = Circuit.from_file(str(p))
    compiler = dpf_pk.serial_compiler()
    t0 = time.time()
    try:
        out, info = dpf_pk.dpf_pk_compile(circ, compiler, error=0.4 * eps, max_k=K)
        el = time.time() - t0
        print(json.dumps(dict(K=K, seconds=round(el, 1), qudits=out.num_qudits,
              t_explicit=out.count(TGate()) + out.count(TdgGate()),
              residual_rz=out.count(RZGate()),
              logical_and_dg=out.count(LogicalAndDgGate()),
              num_blocks=info['num_blocks'],
              after_ntro=info['after_greedy_ntro'], after_pkac=info['after_pkac'])), flush=True)
    except BaseException as e:
        print(json.dumps(dict(K=K, seconds=round(time.time()-t0,1), error=f'{type(e).__name__}: {e}'[:300])), flush=True)
