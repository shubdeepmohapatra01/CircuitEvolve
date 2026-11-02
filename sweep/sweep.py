"""No-LLM pass: every rule in a playbook folder x every circuit's TKET start (the isolated arm's transfer test).

    python sweep/sweep.py <playbook_dir> [circuits...]          (default: tfim_4 tfim_6)
For each circuit: every valid rule (recorded replay equivalent and lowered T) alone on the TKET start -> verified?
T; then a greedy pass applying all rules in order, keeping only verified improvements -> best T for the circuit.
Writes results/sweep_<playbook_dir basename>.csv and prints the table.
"""
import csv, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "verifier")]
from pipeline import HERE, load, t_count, tket
from playbook import find_circuit, try_rule, valid_rules


def sweep(folder, names):
    rules, tmp, rows = valid_rules(folder), tempfile.mkdtemp(prefix="sweep_"), []
    for name in names:
        tk = tket(load(find_circuit(name)))
        T0 = t_count(tk)
        best, Tb, used = tk, T0, []
        for i, (entry, _) in enumerate(rules):
            rule, script = os.path.basename(entry), os.path.join(entry, "technique.py")
            io = [os.path.join(tmp, f"{name}_{i}_{x}.qasm") for x in ("in", "out")]
            _, v = try_rule(script, tk, tk, *io)                             # the rule alone on the TKET start
            rows.append(dict(circuit=name, rule=rule, T_tket=T0, equivalent=v["equivalent"], T=v["T"],
                             reason=v["reason"]))
            io = [os.path.join(tmp, f"{name}_{i}_greedy_{x}.qasm") for x in ("in", "out")]
            new, v = try_rule(script, best, tk, *io)                         # greedy: on the best so far
            if new is not None and v["T"] < Tb:
                best, Tb = new, v["T"]; used.append(rule)
        rows.append(dict(circuit=name, rule="GREEDY (all rules in order)", T_tket=T0, equivalent=True, T=Tb,
                         reason="kept: " + (" + ".join(used) or "none")))
    return rules, rows


if __name__ == "__main__":
    folder = os.path.normpath(sys.argv[1])
    rules, rows = sweep(folder, sys.argv[2:] or ["tfim_4", "tfim_6"])
    out = os.path.join(HERE, "results", f"sweep_{os.path.basename(folder)}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["circuit"]); w.writeheader(); w.writerows(rows)
    print(f"{len(rules)} valid rules in {folder}; table -> {os.path.relpath(out, HERE)}")
    print(f"{'circuit':10s} {'rule':42s} {'T_tket':>7s} {'equiv':>6s} {'T':>6s}  reason")
    for r in rows:
        print(f"{r['circuit']:10s} {r['rule'][:42]:42s} {r['T_tket']:7d} {str(r['equivalent']):>6s} "
              f"{str(r['T']):>6s}  {r['reason'][:60]}")
