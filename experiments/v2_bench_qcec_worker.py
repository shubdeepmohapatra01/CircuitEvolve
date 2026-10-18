"""Run one MQT QCEC check in a separate process (QCEC's alternating checker can ignore its own timeout, so the
caller enforces a hard wall-clock limit by killing this process).

    python v2_bench_qcec_worker.py a.qasm b.qasm '{"run_alternating_checker": false}' <timeout_s>
Prints one JSON line {"qcec": <EquivalenceCriterion name>}.
"""
import json
import sys

from mqt import qcec
from mqt.core import load

a, b, cfg, to = sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), float(sys.argv[4])
r = qcec.verify(load(a), load(b), timeout=to, **cfg)
print(json.dumps({"qcec": str(r.equivalence).split(".")[-1]}))
