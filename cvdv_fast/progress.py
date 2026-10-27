"""Text progress view of the LLM rule-book loop (reads results/*.jsonl; read-only)."""
import json, time, datetime as dt
from pathlib import Path
R = Path(__file__).resolve().parent / "results"
START, BUDGET_MIN = dt.datetime.strptime("2026-10-21 13:38", "%Y-%m-%d %H:%M"), 67   # training stops 14:45 local
TARGETS = ["boseHubbard_small", "z2Higgs_small", "electronicVibration_small", "heisenberg_small"]
MAX_WAVES = 9 - 2   # waves 3..9 (cap)

def bar(frac, w=30):
    frac = max(0.0, min(1.0, frac)); n = int(round(frac * w))
    return "[" + "#" * n + "-" * (w - n) + f"] {100*frac:5.1f}%"

rows = [json.loads(l) for l in open(R / "attempts.jsonl")] if (R / "attempts.jsonl").exists() else []
calls = [json.loads(l) for l in open(R / "agent_calls.jsonl")] if (R / "agent_calls.jsonl").exists() else []
el = (dt.datetime.now() - START).total_seconds() / 60
print(f"LLM rule-book training   {dt.datetime.now():%H:%M}   loop started {START:%H:%M}, budget {BUDGET_MIN} min")
print(f"  wall clock   {bar(el / BUDGET_MIN)}  {el:4.0f} / {BUDGET_MIN} min")
waves = sorted({r['attempt'] for r in rows if r['attempt'] >= 3})
lastcall = calls[-1] if calls else {}
print(f"  waves (3-8)  {bar(len(waves) / MAX_WAVES)}  {len(waves)} / {MAX_WAVES} complete; last LLM call: "
      f"{lastcall.get('role')} on {lastcall.get('label')} (attempt {lastcall.get('attempt')}) at {lastcall.get('time')}")
dec = {}
for r in rows:
    d = r['decision'] if r['decision'] != 'reject' or 'no code' not in (r.get('reason') or '') else 'no_code'
    dec[d] = dec.get(d, 0) + 1
print("  outcomes     " + ", ".join(f"{k}: {v}" for k, v in sorted(dec.items())) + f"   (LLM calls: {len(calls)})")
print("  per target (attempts this session, all waves):")
for t in TARGETS + ["kerr_small"]:
    rs = [r for r in rows if r['label'] == t]
    marks = "".join({"admit": "A", "never_fires": "n", "reject": "x"}.get(r['decision'], "?") if 'no code' not in (r.get('reason') or '') else "." for r in rs)
    print(f"    {t:27s} {marks:10s} " + (f"admitted: {', '.join(r['card']['name'] for r in rs if r['decision']=='admit')}" if 'A' in marks else ""))
print("    legend: A admitted, x rejected, n never fires, . no code produced")
acc = sorted(p.stem for p in (R.parent / "rules" / "accepted").glob("*.py"))
print(f"  book: 13 seed rules (Liu et al.) + {len(acc)} LLM rules: {', '.join(acc)}")
bs = R / "book_state.json"
if bs.exists():
    st = json.loads(bs.read_text())["results"]
    print("  current book vs Genesis (routed total gates / duration):")
    for t in ["kerr_small"] + TARGETS:
        g = json.loads((R.parent / "baselines" / f"genesis_{t}.json").read_text()) if (R.parent / "baselines" / f"genesis_{t}.json").exists() and (R.parent / "baselines" / f"genesis_{t}.json").stat().st_size else {"total": 595, "duration": 3032}
        o = st.get(t, {})
        print(f"    {t:27s} Genesis {g['total']:4d} / {g['duration']:5d}    ours {o.get('total')} / {o.get('duration')}")
