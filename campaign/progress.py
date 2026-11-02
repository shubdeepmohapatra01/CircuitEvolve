"""Progress of the ancilla campaign (run_anc_campaign.sh). Run: python3 campaign/progress.py   (or watch -n 60 python3 campaign/progress.py)
Per family: one bar per arm (finished runs / circuits), the runs in progress with their current round, the sweep state,
and after the sweep the family result (ancilla best vs the no-ancilla final). Reads logs/campaign_anc/ only."""
import csv, glob, json, os, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = os.path.join(HERE, "logs", "campaign_anc")
FAMS = ["arithmetic", "other", "qft_qpe", "variational", "hamsim"]
W = 30


def bar(k, n):
    f = int(round(W * k / n)) if n else 0
    return "[" + "#" * f + "." * (W - f) + f"] {k:3d}/{n:<3d}"


def events(path):
    """[(time s, kind, circuit, arm)] from a worker log (lines 'HH:MM:SS start|end|skip|LIMIT|GAVE c arm')."""
    out, day, last = [], 0, -1
    for line in open(path) if os.path.exists(path) else []:
        p = line.split()
        if len(p) >= 4 and p[1] in ("start", "end", "skip", "LIMIT", "GAVE") and p[0].count(":") == 2:
            h, m, s = map(int, p[0].split(":")); t = h * 3600 + m * 60 + s
            if t < last: day += 86400                           # crossed midnight
            last = t
            arm = p[4] if p[1] == "GAVE" else p[3].rstrip()
            out.append((t + day, p[1], p[2] if p[1] != "GAVE" else p[3], arm))
    return out


def current_round(circuit, arm):
    logs = sorted(glob.glob(os.path.join(HERE, "logs", f"agent_{circuit}_{arm}_*.jsonl")), key=os.path.getmtime)
    if not logs: return "starting"
    r, stage = "playbook stage" if arm == "anc_shared" else "starting", ""
    for line in open(logs[-1]):
        e = json.loads(line); stage = e["stage"]
        if stage.startswith("ROUND"): r = stage.lower()
        if stage.startswith("PLAYBOOK: request"): r += " (card)"
    return r


manifest = list(csv.DictReader(open(os.path.join(HERE, "benchmarks", "MANIFEST.csv"))))
n_fam = {f: sum(c["family"] == f for c in manifest) for f in FAMS}
print(f"ancilla campaign  {time.strftime('%F %T')}")
camp = open(os.path.join(L, "campaign.txt")).read() if os.path.exists(os.path.join(L, "campaign.txt")) else ""
total_done, total, durations, active_fams = 0, 2 * sum(n_fam.values()), [], 0
for fam in FAMS:
    d, n = os.path.join(L, fam), n_fam[fam]
    sh = events(os.path.join(d, "shared.txt"))
    iso = events(os.path.join(d, "isolated_A.txt")) + events(os.path.join(d, "isolated_B.txt"))
    done_sh = sum(k in ("end", "skip", "GAVE") for _, k, _, _ in sh)
    done_iso = sum(k in ("end", "skip", "GAVE") for _, k, _, _ in iso)
    total_done += done_sh + done_iso
    state = ("done" if f"family {fam} done" in camp else "sweeping" if f"family {fam} sweep" in camp
             else "running" if os.path.isdir(d) else "queued")
    active_fams += state in ("running", "sweeping")
    print(f"\n{fam:12s} {state}")
    print(f"  shared    {bar(done_sh, n)}")
    print(f"  isolated  {bar(done_iso, n)}")
    for ev in (sh, iso):                                        # durations and runs in progress
        starts = {}
        for t, k, c, a in ev:
            if k == "start": starts[(c, a)] = t
            elif k == "end" and (c, a) in starts: durations.append(t - starts.pop((c, a)))
            elif k in ("LIMIT", "GAVE"): starts.pop((c, a), None)
        for (c, a), t in starts.items():
            print(f"    running  {c:18s} {a:13s} {current_round(c, a)}")
    for t, k, c, a in sh + iso:
        if k in ("LIMIT", "GAVE"): print(f"    {k:8s} {c} {a}")
    res = os.path.join(HERE, "results", f"sweep_anc_{fam}.csv")
    if state == "done" and os.path.exists(res):
        best = [r for r in csv.DictReader(open(res)) if r["rule"] == "BEST"]
        lower = [r for r in best if r["T_noanc_final"] and int(r["T"]) < int(float(r["T_noanc_final"]))]
        print(f"  result    ancilla best below the no-ancilla final on {len(lower)}/{len(best)} circuits: "
              + ", ".join(f"{r['circuit']} {int(float(r['T_noanc_final']))}->{r['T']} ({r['ancillas']} anc)" for r in lower[:8]))
print(f"\nALL         {bar(total_done, total)} runs", end="")
if durations and total_done < total:
    eta = (total - total_done) * (sum(durations) / len(durations)) / 3
    print(f"   mean run {sum(durations) / len(durations) / 60:.1f} min, ETA ~{eta / 3600:.1f} h (3 sessions; + sweeps)")
else:
    print("   " + ("CAMPAIGN DONE" if "CAMPAIGN DONE" in camp else ""))
