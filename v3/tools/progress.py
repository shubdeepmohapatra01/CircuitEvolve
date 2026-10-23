"""P2 progress bar (read-only; reads v3/results/p2/).

    .venv/bin/python -m v3.tools.progress            # print once
    .venv/bin/python -m v3.tools.progress --watch    # refresh every 30 s (Ctrl-C to quit)
"""
from __future__ import annotations

import json
import sys
import time

from ..paths import RESULTS, RULES

P2 = RESULTS / "p2"
W = 40


def bar(done, total, width=W):
    n = int(round(width * done / total)) if total else 0
    return "█" * n + "░" * (width - n)


def render() -> str:
    st = json.loads((P2 / "state.json").read_text())
    att = [json.loads(l) for l in (P2 / "attempts.jsonl").read_text().splitlines() if l.strip()]
    voided = {(a["label"], a["attempt"]) for a in att if a.get("type") == "annotation" and a.get("voided")}
    att = [a for a in att if a.get("type") != "annotation" and
           not ((a["label"], a["attempt"]) in voided and a.get("decision") == "harness_error")]
    tok = [json.loads(l) for l in (P2 / "tokens.jsonl").read_text().splitlines() if l.strip()]
    ours = {}
    for l in (P2 / "ours.jsonl").read_text().splitlines():
        r = json.loads(l)
        ours[r["label"]] = r
    plan = st["plan"]
    total = sum(b for _, b in plan)
    done = sum(st["done"][l] for l, _ in plan)
    cost = sum(t.get("cost_usd") or 0 for t in tok)
    durs = [a["finished"] - a["started"] for a in att if a.get("finished") and a.get("started")]
    rate = sum(durs) / len(durs) if durs else None          # mean measured attempt duration
    eta = time.strftime("%H:%M", time.localtime(time.time() + rate * (total - done))) if rate and done < total else "-"
    state = st.get("stopped") or ("finished" if done >= total else "running")
    lines = [f"P2  {bar(done, total)}  {done}/{total} attempts  ({100 * done / total:.0f}%)   ${cost:.2f}   "
             f"state: {state}   ETA ~{eta}" + (f" (mean {rate / 60:.0f} min/attempt)" if rate else ""), ""]
    running = next((l for l, _ in plan if st["status"].get(l) == "running"), None)
    for label, budget in plan:
        d = st["done"][label]
        mine = [a for a in att if a["label"] == label]
        last = mine[-1]["decision"] if mine else ""
        o = ours.get(label, {})
        flag = " ◀ running" if label == running else ""
        lines.append(f"  {label:<10} {bar(d, budget, 10)} {d}/{budget}  T={o.get('t_count', '?'):>6}  "
                     f"last: {last:<14}{flag}")
    acc = sorted(p.stem for p in (RULES / "accepted").glob("*.py"))
    ret = sorted(p.stem for p in (RULES / "retired").glob("*.py"))
    lines += ["", f"  book: {', '.join(acc) or '(empty)'}", f"  retired: {', '.join(ret) or '-'}"]
    return "\n".join(lines)


def main():
    if "--watch" in sys.argv:
        try:
            while True:
                print("\033[2J\033[H" + render(), flush=True)
                time.sleep(30)
        except KeyboardInterrupt:
            return
    print(render())


if __name__ == "__main__":
    main()
