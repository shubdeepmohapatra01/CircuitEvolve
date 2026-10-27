import time
from v3.tools.evaluate import evaluate, plan, accepted_book
book = accepted_book()
print("book size:", len(book))
for target in ['hhl_8','qpe_8','qft_8']:
    pl = plan('dv', eps=1e-3, target=target, small_only=True)
    print(f"\ntarget={target}: test_rule would run {[c['label'] for c,_ in pl]}")
    t0=time.time()
    rep = evaluate('v3/rules/candidates/_timing_noop.py', eps=1e-3, target=target,
                   small_only=True, stop_at_first_failure=True, time_limit=1e9)
    el=time.time()-t0
    per = {r['label']: r['seconds'] for r in rep['circuits']}
    print(f"  HARNESS FLOOR for ONE test_rule call: {el:7.1f} s = {el/60:.1f} min   decision={rep['decision']}")
    print(f"  per circuit: {per}")
