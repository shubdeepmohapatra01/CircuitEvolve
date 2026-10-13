"""Diagnostic for Shor-16 (arXiv:2409.00433 Table 3 By Gate: 816 RZ, 74,797 T).

Counts every parameterised gate (cp, ccp, u1) whose angle is not a multiple of pi/4 as ONE RZ and
synthesises RZ(angle) with gridsynth at 1e-9. This is a COUNTING CONVENTION, not a valid
Clifford+T compilation: CP(t) needs 3 RZ(t/2) and CCP(t) 7 RZ(t/4) (phase polynomial) without
ancillas. Reported only to explain the published number."""
import math, re, sys, json
from collections import Counter
sys.path.insert(0, '.')
from common import QASM, gridsynth_summary
from bygate_exact import classify_angle
def main(name='shor/shor_16'):
    gates = Counter(); angles = []; t_quarter = 0; params = Counter()
    for line in open(QASM / f'{name}.qasm'):
        m = re.match(r'(\w+)(?:\(([^)]*)\))?\s', line)
        if not m or m.group(1) in ('OPENQASM', 'include', 'qreg', 'creg'): continue
        g, p = m.groups(); gates[g] += 1
        if p is None: continue
        th = float(eval(p, {'pi': math.pi}))
        k = classify_angle(th, 1e-10)
        if k is None:
            angles.append(th); params[(g, 'nonpi4')] += 1
        else:
            params[(g, f'k{k}')] += 1
            t_quarter += k % 2
    gs = gridsynth_summary(angles, 1e-9)
    return dict(circuit=name.split('/')[1], gate_counts=dict(gates), param_classes={f'{a}:{b}': v for (a, b), v in params.items()},
                rz_param_convention=len(angles), t_gridsynth=gs['gs_t'], t_quarter_params=t_quarter,
                t_ccx_7=7 * gates.get('ccx', 0), t_gridsynth_plus_ccx=gs['gs_t'] + 7 * gates.get('ccx', 0),
                t_all=gs['gs_t'] + 7 * gates.get('ccx', 0) + t_quarter)
if __name__ == '__main__':
    print(json.dumps(main(*sys.argv[1:])))
