"""Profile BQSKit QuickPartitioner blocks (sizes 2 and 3) on dev + eval circuits.

Two circuit forms are partitioned:
  cliffordrz : exact gate-level Clifford+RZ lowering (bygate_exact 'minrz': every merged 1q run
               written with the minimal number of non-Clifford RZ; T/S/H/CX named). A 'rotation'
               is an RZ whose angle is not a multiple of pi/4 (i.e. one gridsynth call).
  u3cx       : the benchmark as given ({U3, CX}; shor_* lowered by qiskit opt0). Rotations per
               block = non-Clifford angles of the per-U3 parameter ZSX lowering (paper convention).
Per circuit and block size:
  n_blocks, rotations per block (mean / median / max), fraction of blocks with 0 rotations,
  n_struct  : distinct block STRUCTURES = ordered (gate name, local qubit tuple) list with all
              rotation angles abstracted (U3 -> 'U3', RZ -> 'RZ'); local qubits = index in the
              block's sorted global location,
  n_unitary : distinct block unitaries up to global phase: U / phase(first entry with |u|>1e-3),
              rounded to 6 decimals, hashed.
Run: .venv/bin/python profile_partitions.py --tag NAME
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from multiprocessing import get_context
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import EVAL, OUT, QASM  # noqa: E402

DEV = ([f'qft/qft_{n}' for n in (3, 4, 5, 6, 7, 8, 16)]
       + [f'qpe/qpe_{n}' for n in (6, 8, 10, 12, 14)]
       + [f'qae/qae_{n}' for n in (11, 13, 15, 17, 19, 21)]
       + [f'heisenberg/heisenberg_{n}' for n in range(3, 9)]
       + [f'tfim/tfim_{n}' for n in range(3, 9)]
       + ['hubbard/hubbard_4', 'hubbard/hubbard_8', 'grover/grover_3', 'grover/grover_5',
          'qml/qml_4', 'qml/qml_13', 'shor/shor_12', 'shor/shor_14', 'mult/mult_8', 'hhl/hhl_8'])


def ops_to_bqskit(ops, n):
    from bqskit import Circuit
    from bqskit.ir.gates import (CNOTGate, HGate, RZGate, SdgGate, SGate, SqrtXGate, TdgGate, TGate,
                                 ZGate)
    G = dict(h=HGate(), s=SGate(), sdg=SdgGate(), t=TGate(), tdg=TdgGate(), z=ZGate(), cx=CNOTGate(),
             sx=SqrtXGate())
    c = Circuit(n)
    for g, qs, a in ops:
        if g == 'rz':
            c.append_gate(RZGate(), qs, [a])
        else:
            c.append_gate(G[g], qs)
    return c


def unitary_key(U) -> str:
    import numpy as np
    U = np.asarray(U, complex)
    flat = U.ravel()
    i = int(np.argmax(np.abs(flat) > 1e-3))
    V = U * (abs(flat[i]) / flat[i])
    R = np.round(V, 6) + 0.0  # +0.0 folds -0.0
    return hashlib.sha1(np.ascontiguousarray(R).tobytes()).hexdigest()


def block_stats(sub, form):
    import numpy as np
    from bqskit.ir.gates import RZGate, U3Gate
    from bygate_exact import classify_angle
    rot = 0
    struct = []
    for op in sub:
        name = type(op.gate).__name__.replace('Gate', '')
        struct.append((name, tuple(op.location)))
        if form == 'cliffordrz' and isinstance(op.gate, RZGate):
            rot += classify_angle(op.params[0]) is None
        elif form == 'u3cx' and isinstance(op.gate, U3Gate):
            th, ph, lam = op.params
            rot += sum(classify_angle(x) is None for x in (lam, th + math.pi, ph + math.pi))
    return rot, tuple(struct), unitary_key(sub.get_unitary())


def profile_job(args):
    name, form = args
    import numpy as np
    from bqskit.ir.gates import CircuitGate
    from bqskit.passes import QuickPartitioner
    from bygate_exact import lower_circuit, lower_to_u3cx
    from serial_runtime import run_passes
    path = QASM / f'{name}.qasm'
    t0 = time.time()
    circ, _ = lower_to_u3cx(path, OUT / 'work')
    if form == 'cliffordrz':
        ops, _ = lower_circuit(circ)
        circ = ops_to_bqskit(ops, circ.num_qudits)
    rows = []
    for k in (2, 3):
        c = circ.copy()
        run_passes(c, [QuickPartitioner(k)])
        rots, structs, units = [], set(), set()
        for op in c:
            assert isinstance(op.gate, CircuitGate)
            sub = op.gate._circuit
            r, s, u = block_stats(sub, form)
            rots.append(r)
            structs.add((op.num_qudits, s))
            units.add((op.num_qudits, u))
        rots = np.array(rots)
        rows.append(dict(circuit=name.split('/')[1], family=name.split('/')[0], form=form,
                         block_size=k, qubits=circ.num_qudits, gates=circ.num_operations,
                         rotations_total=int(rots.sum()), n_blocks=len(rots),
                         rot_per_block_mean=round(float(rots.mean()), 3),
                         rot_per_block_median=float(np.median(rots)), rot_per_block_max=int(rots.max()),
                         frac_blocks_no_rotation=round(float((rots == 0).mean()), 3),
                         n_struct=len(structs), n_unitary=len(units),
                         struct_per_block=round(len(structs) / len(rots), 3),
                         eval_circuit=name in EVAL, seconds=round(time.time() - t0, 1)))
    return rows


def main():
    import pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', required=True)
    ap.add_argument('--circuits', nargs='*', default=EVAL + DEV)
    ap.add_argument('--forms', nargs='*', default=['cliffordrz', 'u3cx'])
    ap.add_argument('--procs', type=int, default=6)
    a = ap.parse_args()
    f = OUT / f'{a.tag}.csv'
    assert not f.exists(), f'{f} exists; results are append-only'
    jobs = [(c, fm) for c in a.circuits for fm in a.forms]
    with get_context('spawn').Pool(a.procs) as pool:
        rows = [r for rs in pool.imap(profile_job, jobs) for r in rs]
    df = pd.DataFrame(rows)
    f.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(f, index=False)
    print(df[['circuit', 'form', 'block_size', 'n_blocks', 'rot_per_block_mean', 'n_struct', 'n_unitary']]
          .to_string(index=False))
    print('wrote', f)


if __name__ == '__main__':
    main()
