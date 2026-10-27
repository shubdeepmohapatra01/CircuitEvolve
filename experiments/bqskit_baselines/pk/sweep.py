import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dpf_pk
KEYS = ('max_k','t_count','t_explicit','t_quarter_rz','t_gridsynth','n_rz_synthesized',
        'eps_rz','eps_rz_respected','ancillas','logical_and_dg','num_blocks','seconds_total')
name, eps = sys.argv[1], float(sys.argv[2])
Ks = [int(x) for x in sys.argv[3].split(',')]
rows = []
for K in Ks:
    try:
        r = dpf_pk.run_arm(name, eps, K)
        rows.append(r)
        print(json.dumps({k: r[k] for k in KEYS}), flush=True)
    except BaseException as e:
        print(json.dumps(dict(max_k=K, error=f'{type(e).__name__}: {e}'[:250])), flush=True)
if rows:
    b = min(rows, key=lambda r: r['t_count'])
    print(f"BEST K={b['max_k']} T={b['t_count']} ancillas={b['ancillas']} "
          f"(explicit {b['t_explicit']} + quarter {b['t_quarter_rz']} + gridsynth {b['t_gridsynth']} "
          f"over {b['n_rz_synthesized']} rz)", flush=True)
