"""One command that says where everything stands.

    .venv/bin/python -m v4.tools.status

Reads only append-only results; runs nothing and spends nothing. Prints: the book, the gates, the
per-circuit numbers against the best baseline, what the overnight re-evaluation decided, and how far the
training loop has got (with its cost).
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import baselines as Ba, book as B
from ..paths import RESULTS


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:                                   # noqa: BLE001 (a missing file is normal)
        return None


def _lines(p: Path):
    if not p.is_file():
        return []
    out = []
    for line in p.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass                                    # a truncated last line from a kill
    return out


def main():
    print("=" * 96)
    print("v4 STATUS")
    print("=" * 96)

    floor = B.floor_tier()
    acc = B.accepted_tier()
    print(f"\nBOOK  ({B.digest(floor + acc)})")
    for r in floor:
        print(f"  floor     {r.name:<52} {r.error_class}/{r.resource_class}")
    for r in acc:
        print(f"  accepted  {r.name:<52} {r.error_class}/{r.resource_class}")
    if not acc:
        print("  accepted  (none)")

    g = _load(RESULTS / "planted_gate.json")
    print("\nGATES")
    if g:
        print(f"  planted-bug gate   {g['correct']}/{g['decisions']} correct -> "
              f"{'PASS' if g['passed'] else 'FAIL'}")
        for r in g["rows"]:
            print(f"      {'ok ' if r['ok'] else 'BAD'}  {r['control']:<40} want {r['want']}")
    else:
        print("  planted-bug gate   (not run)")

    for tag in ("p6", "p3", "p2"):
        fg = _load(RESULTS / f"floor_gate_{tag}.json")
        if fg:
            print(f"  floor gate ({tag})     guarantee met: {fg['guarantee_met']}")
            for r in fg["rows"]:
                print(f"      {r['label']:<9} floor {r['floor_t']:>7}   best {r['best_baseline']} "
                      f"{r['best_baseline_t']:>7}   gap {r['gap']:+}")
            break

    print("\nPER CIRCUIT, eps 1e-3   (ours = the current book)")
    res = _load(RESULTS / "p8" / "results.json") or _load(RESULTS / "p8_preloop" / "results.json")
    if res:
        print(f"  {'circuit':<11}{'TKET':>8}{'pyzx':>8}{'BQSKit':>8}{'DPF':>8}{'OURS':>9}  tags            vs best")
        for r in res["rows"]:
            tag = f"{r['ours_error_class']}/{r['ours_resource_class']}"
            vs = (f"{r.get('pct_vs_best'):+.1f}% vs {r['best_baseline']}"
                  if r.get("pct_vs_best") is not None else
                  f"{r.get('gap_to_best'):+} vs {r.get('best_baseline')}")
            print(f"  {r['label']:<11}{str(r.get('TKET')):>8}{str(r.get('pyzx')):>8}"
                  f"{str(r.get('BQSKit-FT')):>8}{str(r.get('DPF Synth')):>8}{r['ours']:>9}  "
                  f"{tag:<15} {vs}")
    else:
        print("  (no report yet - run `python -m v4.report --tag p8`)")

    print("\nRE-EVALUATION of v3's rejected rules (P6)")
    rows = _lines(RESULTS / "reevaluate_p6.jsonl")
    if rows:
        from collections import Counter
        c = Counter(r["decision"] for r in rows)
        print(f"  {len(rows)}/18 done: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
        for r in rows:
            if r["decision"] == "admit":
                helped = ", ".join(f"{h['label']} {h['before']}->{h['after']}"
                                   for h in (r.get("helped") or []))
                print(f"      ADMIT  {Path(str(r['candidate'])).stem:<52} [{r['v3_group']}] {helped}")
        nv = [r for r in rows if r["decision"] == "not_verifiable"]
        for r in nv:
            print(f"      not verifiable (NOT a rejection)  {Path(str(r['candidate'])).stem}")
    else:
        print("  (not started / no rows yet)")

    print("\nTRAINING LOOP")
    for tag in ("run1", "smoke"):
        d = RESULTS / tag
        att = _lines(d / "attempts.jsonl")
        tok = _lines(d / "tokens.jsonl")
        if not att and not tok:
            continue
        cost = sum(t.get("cost_usd") or 0 for t in tok)
        cfg = _load(d / "config.json") or {}
        from collections import Counter
        kinds = Counter(a["kind"] for a in att)
        print(f"  tag {tag}: {len(att)} attempts of {cfg.get('global_budget_attempts', '?')} "
              f"(reachable {cfg.get('reachable_attempts', '?')}, bound: {cfg.get('binding_bound', '?')}), "
              f"loop {max((a.get('loop') or 0) for a in att) if att else 0}, "
              f"{len(tok)} LLM calls, ${cost:.2f}")
        print("      outcomes: " + ", ".join(f"{k}={v}" for k, v in kinds.most_common()))
        for a in att:
            if a["kind"] == "admitted":
                h = ", ".join(f"{x['label']} {x['before']}->{x['after']}"
                              for x in ((a.get("admission") or {}).get("helped") or []))
                print(f"      ADMITTED on {a['label']}: {(a.get('card') or {}).get('name')}  {h}")
        last = att[-1] if att else None
        if last:
            print(f"      last: {last['label']} {last['kind']} ({last['level']}) T={last['current_t']}")
    else:
        pass
    if not _lines((RESULTS / "run1") / "attempts.jsonl"):
        print("  tag run1: not started yet (it is queued behind the re-evaluation chain)")
    print()


if __name__ == "__main__":
    main()
