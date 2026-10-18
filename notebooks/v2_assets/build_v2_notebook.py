"""Build notebooks/v2_group_meeting.ipynb (unexecuted) from the cell sources below.

    .venv/bin/python notebooks/v2_assets/build_v2_notebook.py
    .venv/bin/python notebooks/v2_assets/run_ipykernel_inprocess.py notebooks/v2_group_meeting.ipynb

No LLM or network calls in any cell. Cached LLM records come from notebooks/v2_assets/tier1_cached_records.json
(written by make_v2_assets.py from the append-only dev logs); everything else is computed live or read from
results/v2/ and benchmarks/nam_arith/.
"""
from pathlib import Path

import nbformat

HERE = Path(__file__).resolve().parent
NB = HERE.parent / "v2_group_meeting.ipynb"
CELLS = []


def md(s):
    CELLS.append(nbformat.v4.new_markdown_cell(s.strip("\n")))


def code(s):
    CELLS.append(nbformat.v4.new_code_cell(s.strip("\n")))


# ================================================================================================ title + setup
md(r"""
# CircuitEvolve v2 — group meeting

Two-tier LLM-assisted fault-tolerant (Clifford+T) compilation on the Nam et al. arithmetic suite, with one verifier
deciding every result. This notebook runs **offline**: no network and no LLM calls. The LLM exchanges shown are
replayed from cached records of the real DEV run (`notebooks/v2_assets/tier1_cached_records.json`, copied verbatim
from `results/v2/tier1/logs/`); compilation, verification and rule application run live. Every number is computed
here or read from `results/v2/`, `benchmarks/nam_arith/` or the reused baseline files.
""")

code(r"""
import json, sys, time, math, ast
from collections import Counter
from pathlib import Path
import pandas as pd
from IPython.display import Image, Markdown, display

T0 = time.time()
ROOT = Path.cwd() if (Path.cwd() / "results").exists() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
ASSETS = ROOT / "notebooks" / "v2_assets"
R2 = ROOT / "results" / "v2"
BENCH = ROOT / "benchmarks" / "nam_arith"
pd.set_option("display.width", 220); pd.set_option("display.max_colwidth", 90); pd.set_option("display.max_columns", 40)

from circuitevolve import integrity
from circuitevolve.v2 import verify as V, metric as M, baselines as BL
DIGEST0 = integrity.frozen_digest()
V.check_integrity()
CACHED = json.loads((ASSETS / "tier1_cached_records.json").read_text())["records"]
print("frozen verifier digest:", DIGEST0[:16], "| frozen files:", len(integrity.FROZEN))
print("cached LLM records:", {k: v["_source"] for k, v in CACHED.items()})
""")

# ================================================================================================ 1. idea
md(r"""
## 1. The two-tier idea

**Tier 1 (compilation strategy):** the LLM reads a recognizer summary of a *logical* (Toffoli-level) circuit and returns
a JSON plan that picks a known construction per subroutine (Gidney temporary AND, Jones 4-T Toffoli, relative-phase
Toffoli, ...); a deterministic compiler executes it and the result is verified against the logical circuit.
**Tier 2 (optimization):** the LLM writes *executable* rewrite rules (pattern → replacement); each rule is proven once as
an exact identity, applied wherever it matches, and a library version is kept only if it lowers DEV T-count.

| role | tier 1 | tier 2 |
|---|---|---|
| mutator (LLM) | `tier1/prompt.py`, `tier1/loop.py` → plan in `tier1/plan.py` format | `tier2/evolve.py` → `RULE` blocks parsed by `tier2/rules.py` |
| executor | `tier1/recognize.py` + `tier1/compile.py` | `tier2/apply.py` (matcher) + `tier2/commute.py` |
| verifier | `v2/verify.py` (`exact` / `relaxed`) vs the logical circuit | `rules.verify_rule` (`exact`, once per rule) + whole-circuit guards |
| metric | `v2/metric.py` (T, qubits, ancillas, measurements, T-depth) | (T, gates) lexicographic, `v2/metric.py` |
| no-LLM control | `tier1/control.py` (route sets V1-V4 × global passes) | `tier2/enumerate_ids.py` (Quartz-style enumeration) |

The verifier has three labelled modes: **exact** (same qubits, U_cand = c·U_ref over D[ω]), **approx** (phase-aligned
operator distance ≤ ε for continuous rotations) and **relaxed** (clean ancillas, measurement + feed-forward, correct on
every valid input and branch with an input-independent phase). The cell below runs one toy case per mode.
""")

code(r"""
import circuitevolve.v2.tier1.recognize, circuitevolve.v2.tier1.plan, circuitevolve.v2.tier1.compile
import circuitevolve.v2.tier1.control, circuitevolve.v2.tier2.rules, circuitevolve.v2.tier2.apply
import circuitevolve.v2.tier2.enumerate_ids, circuitevolve.v2.tier2.evolve
mods = [V, M, BL] + [sys.modules[f"circuitevolve.v2.{m}"] for m in
        ("tier1.recognize", "tier1.plan", "tier1.compile", "tier1.control", "tier2.rules", "tier2.apply",
         "tier2.enumerate_ids", "tier2.evolve")]
for mod in mods:
    print(f"{mod.__name__.replace('circuitevolve.v2.', ''):20s} {mod.__doc__.strip().splitlines()[0][:105]}")

from circuitevolve.ir import Circuit
ccx = Circuit(3).add("ccx", 0, 1, 2)
gidney = Circuit(4).add("and_compute", 0, 1, 3).add("cx", 3, 2).add("and_uncompute", 0, 1, 3)   # Toffoli via a temporary AND on ancilla q3
cases = [
    ("exact",   "ccx -> 7-T Clifford+T expansion",          V.verify(ccx.expand("clifford_t"), ccx, "exact")),
    ("approx",  "rz(0.3 + 1e-10) vs rz(0.3), eps 1e-8",     V.verify(([("rz", (0,), 0.3 + 1e-10)], 1), ([("rz", (0,), 0.3)], 1), "approx", eps=1e-8)),
    ("approx",  "rz(0.3 + 1e-6) vs rz(0.3), eps 1e-8",      V.verify(([("rz", (0,), 0.3 + 1e-6)], 1), ([("rz", (0,), 0.3)], 1), "approx", eps=1e-8)),
    ("relaxed", "ccx via Gidney AND on a fresh ancilla",    V.verify(gidney, ccx, "relaxed", data_map=[0, 1, 2])),
]
display(pd.DataFrame([dict(mode=m, case=c, ok=v.ok, method=v.method, certified=v.certified,
                           unitary_preserving=v.unitary_preserving, distance=v.distance, reason=v.reason[:60])
                      for m, c, v in cases]))
""")

# ================================================================================================ 2. benchmarks
md(r"""
## 2. Benchmarks and baselines

The v2 suite (`benchmarks/nam_arith/MANIFEST.csv`, split `v2-nam-arith-1` in `SPLIT.md`) is the Nam et al. 2018 /
T-par arithmetic suite plus generated Cuccaro adders and qseed Shor circuits. DEV holds the smallest instances of each
family; held-out holds strictly larger instances plus whole families with no DEV member. Baselines are **reused**, never
recomputed: our pyzx / TKET runs (`results/v2/baselines_new.csv`), the stage-1 BQSKit table, the old reference pipelines,
and published values (context only).
""")

code(r"""
man = pd.read_csv(BENCH / "MANIFEST.csv")
split = json.loads((BENCH / "split_v2.json").read_text())
fam = (man.groupby(["family", "split"]).agg(circuits=("name", lambda s: ", ".join(s)), qubits_min=("qubits", "min"),
                                           qubits_max=("qubits", "max")).reset_index().sort_values(["split", "family"]))
print(f"{len(man)} circuits; split {split.get('version')}: dev {len(split['dev'])}, held-out {len(split['heldout'])}, "
      f"large_optional {len(split.get('large_optional', []))}")
display(fam)
tab = BL.table()
src = (tab.groupby("source").agg(rows=("circuit", "size"), circuits=("circuit", "nunique"), valid=("valid", "sum"),
                                 comparable=("comparable", "sum")).reset_index())
display(src)
""")

# ================================================================================================ 3. tier 1
md(r"""
## 3. Tier 1 live demo: `cuccaro_8`

`cuccaro_8` is an 8-bit Cuccaro ripple-carry adder (18 qubits, 16 Toffolis). The deterministic recognizer lists qubit
roles, Toffolis `T<k>` and compute/uncompute pairs `P<k>` with their class (clean / mirror / controls_fixed); this
summary is what the LLM sees. Below: the summary, as computed now.
""")

code(r"""
from circuitevolve.v2.tier1.recognize import load_logical, summarize
from circuitevolve.v2.tier1.compile import evaluate
row = man.set_index("name").loc["cuccaro_8"]
declared_zero = [] if pd.isna(row["zero_init_qubits"]) else [int(x) for x in str(row["zero_init_qubits"]).split()]
orig8, lc8 = load_logical(BENCH / row["logical_path"], name="cuccaro_8")
s8 = summarize(lc8, declared_zero, "cuccaro_8")
norm = V.verify(orig8, V.ReferenceSpec.from_circuit(lc8.to_ir()), "exact")      # normalization check, as the dev runner
print("normalized circuit vs original QASM:", norm.ok, norm.method)
txt = s8.text(lc8).splitlines()
print("\n".join(l[:200] for l in txt[:txt.index(next(l for l in txt if l.startswith("NORMALIZED")))]))
""")

md(r"""
### 3a. One cached LLM compilation plan (DEV run `dev_v1`, `cuccaro_8`, call 2)

Prompt excerpt (objective, toolbox, and the history the model saw) and the model's JSON reply, both verbatim from the
log. The model recognized the pairs as compute/uncompute and routed every pair to Gidney's temporary AND on a fresh
ancilla; the toolbox description it chose from is shown in the excerpt.
""")

code(r"""
rec = CACHED["cuccaro_8_call2"]
P = rec["prompt"].splitlines()
def block(start, stop):
    i = next(k for k, l in enumerate(P) if l.startswith(start))
    j = next(k for k, l in enumerate(P) if k > i and l.startswith(stop)) if stop else len(P)
    return P[i:j]
excerpt = P[:6] + ["[...]"] + block("TOOLBOX", "TECHNIQUE CARDS")[:6] + ["[...]"] + block("BEST VERIFIED", "RECENT")
print(f"prompt: {rec['prompt_chars']} chars, sha256 {rec['prompt_sha256'][:16]}..., cards {rec['cards']}, "
      f"usage {rec['usage']}\n")
print("\n".join(l if len(l) < 240 else l[:237] + "..." for l in excerpt))
print("\nREPLY (JSON plan):")
print(json.dumps(json.loads(rec["reply"]), indent=1))
""")

md(r"""
### 3b. Compile and verify the replayed plan live

The plan is parsed (json + regex only), compiled with the frozen IR gadgets, and verified against the normalized
logical circuit in **relaxed** mode (the plan adds ancillas and measurements). T is compared with the naive logical
cost and with the best reused unitary-preserving classical number from `baselines.best_classical`.
""")

code(r"""
t1 = time.time()
ev8 = evaluate(lc8, s8, rec["reply"])
dt8 = time.time() - t1
comp8 = ev8["_compiled"]
naive = M.measure(lc8.to_ir())
bc8 = BL.best_classical("cuccaro_8", 0.0)
print(f"verdict: ok={ev8['ok']} mode={ev8['verdict_mode']} method={ev8['method']} certified={ev8['certified']} "
      f"unitary_preserving={ev8['unitary_preserving']}  ({dt8:.1f} s)")
print(f"compiled digest {ev8['digest']} == logged {rec['digest']}: {ev8['digest'] == rec['digest']}")
display(pd.DataFrame([
    dict(circuit="logical (7 T per Toffoli)", T=naive["t_count"], qubits=naive["qubits"], measurements=naive["measurements"], contract="-"),
    dict(circuit=f"best classical ({bc8['arm']})", T=bc8["t_count"], qubits=lc8.n, measurements=0, contract="unitary-preserving"),
    dict(circuit="LLM plan, compiled now", T=ev8["t_count"], qubits=ev8["qubits"], measurements=ev8["measurements"], contract="relaxed"),
    dict(circuit="LLM plan, as logged", T=rec["t_count"], qubits=rec["qubits"], measurements=rec["measurements"], contract=rec["verdict_mode"]),
]))
print(f"T: {naive['t_count']} (logical) -> {ev8['t_count']} (relaxed plan); best classical exact {bc8['t_count']:.0f}; "
      f"ratio {ev8['t_count'] / bc8['t_count']:.2f}; cost +{ev8['ancillas']} ancillas, {ev8['measurements']} measurements")
# one Gidney gadget at the gadget level: the first and_compute / and_uncompute pair of the routed circuit
g = comp8.routed.gates
i = next(k for k, x in enumerate(g) if x.name == "and_compute")
a = g[i].qubits[2]
j = next(k for k, x in enumerate(g) if x.name == "and_uncompute" and x.qubits[2] == a)
print("first temporary AND (ancilla q%d): gates %d..%d:" % (a, i - 1, j + 1),
      "; ".join(f"{x.name} {' '.join('q%d' % q for q in x.qubits)}" for x in g[i - 1:i + 2]), "... ",
      "; ".join(f"{x.name} {' '.join('q%d' % q for q in x.qubits)}" for x in g[j - 1:j + 2]))
""")

md(r"""
### 3c. Rejections: one logged LLM plan and one planted plan

The verifier's failure reasons are diagnoses fed back to the LLM. First, a logged LLM plan for `cuccaro_4` (call 4)
that computed a temporary AND directly into a pair's target instead of a fresh ancilla, replayed live. Second, a planted
plan for `cuccaro_8`: `temporary_and` directly on `P0`, whose target `q2` is *dirty* (written between the pair).
""")

code(r"""
rej = CACHED["cuccaro_4_call4"]
row4 = man.set_index("name").loc["cuccaro_4"]
orig4, lc4 = load_logical(BENCH / row4["logical_path"], name="cuccaro_4")
s4 = summarize(lc4, [int(x) for x in str(row4["zero_init_qubits"]).split()] if not pd.isna(row4["zero_init_qubits"]) else [], "cuccaro_4")
ev4 = evaluate(lc4, s4, rej["reply"])
print("cuccaro_4 call 4 decisions:", [(d["element"], d["route"], d.get("via_ancilla")) for d in json.loads(rej["reply"])["decisions"]])
print("  rationale:", json.loads(rej["reply"])["rationale"][:200], "...")
print(f"  live : ok={ev4['ok']} mode={ev4['verdict_mode']} method={ev4['method']} reason: {ev4['reason']}")
print(f"  log  : ok={rej['ok']} reason: {rej['reason']}")
print("  P3 class in the summary:", next(l.strip() for l in s4.text(lc4).splitlines() if l.strip().startswith("P3 =")))

bad = {"target": "relaxed", "global_pass": "none",
       "decisions": [{"element": "P0", "route": "temporary_and"}] +
                    [{"element": f"P{k}", "route": "temporary_and", "via_ancilla": True} for k in range(1, 8)]}
evb = evaluate(lc8, s8, json.dumps(bad))
print("\nplanted cuccaro_8 plan (P0 direct temporary_and on dirty target q2):")
print("  P0 class in the summary:", next(l.strip() for l in txt if l.strip().startswith("P0 =")))
print(f"  live : ok={evb['ok']} stage={evb['stage']} mode={evb['verdict_mode']} method={evb['method']} T would be {evb['t_count']}")
print(f"  reason: {evb['reason']}")
""")

# ================================================================================================ 4. tier 2
md(r"""
## 4. Tier 2 live demo: one verified LLM rule

A verified rule proposed by the LLM in run `run1` (read from `results/v2/tier2/rules_verified.csv`) is re-proven live as
an exact identity (frozen D[ω] simulator, exhaustive over 2^k inputs), shown firing on a toy circuit through a commuting
gate, and then applied to all 16 DEV start circuits (the best verified classical outputs). A planted non-identity is
rejected for contrast.
""")

code(r"""
from circuitevolve.v2.tier2.rules import parse_rules, verify_rule, Library
from circuitevolve.v2.tier2.apply import apply_library, cost
from circuitevolve.v2.tier2.circuits import start_circuits
rv = pd.read_csv(R2 / "tier2" / "rules_verified.csv")
r = rv[(rv.arm == "llm") & (rv.name == "g4p1_t_cz_t_merge")].iloc[0]
rule_text = f"RULE {r['name']}\nPATTERN: {r['pattern']}\nREPLACE: {r['replacement']}\nSIDE: commute\nEND"
print(rule_text, f"\n(logged: gen {r['gen']}, dT={r['dT']}, DEV applications {r['applications_dev']}; meaning: {r['meaning']})")
(rule,), errs = parse_rules(rule_text, "llm")
proof = verify_rule(rule)
print("\nlive proof:", proof)
toy = [("t", (0,)), ("cx", (0, 2)), ("cz", (0, 1)), ("h", (2,)), ("t", (0,))]
res_toy = apply_library(toy, 3, [rule], log_apps=True)
print("toy circuit :", toy, "cost (T, gates)", res_toy["cost_before"])
print("rewritten   :", res_toy["gates"], "cost", res_toy["cost_after"], "apps", dict(res_toy["apps"]))
print("toy rewrite exact check:", V.verify((list((n_, q_, None) for n_, q_ in res_toy["gates"]), 3),
                                           (list((n_, q_, None) for n_, q_ in toy), 3), "exact").ok)
(planted,), _ = parse_rules("RULE planted_bad\nPATTERN: t a; h a; t a\nREPLACE: s a; h a\nEND", "test")
print("planted non-identity:", verify_rule(planted))
""")

code(r"""
starts = start_circuits()
rows = []
for c, st in starts.items():
    res = apply_library(st["gates"], st["n"], [rule])
    rows.append(dict(circuit=c, start=st["arm"], n=st["n"], T=res["cost_before"][0], gates=res["cost_before"][1],
                     matches=sum(res["apps"].values()), T_after=res["cost_after"][0]))
app = pd.DataFrame(rows)
print(f"rule {rule.name} on {len(app)} DEV start circuits: {app.matches.sum()} matches, total T {app['T'].sum()} -> {app.T_after.sum()}")
display(app)
lib = Library.load(R2 / "tier2" / "library_final.json")          # re-verifies every rule and the content hash
print(f"frozen primary library: version {lib.version}, {len(lib.rules)} rules, sha256 {lib.sha256[:16]}...",
      "| .sha256 file:", (R2 / "tier2" / "library_final.sha256").read_text().split()[0][:16])
diag = json.loads((R2 / "tier2" / "diagnostics.json").read_text())
print(f"headroom probe (diagnostics.json): enumerated pool {diag['pool_size']:,} identities "
      f"(specs qubits<=gates {diag['pool_specs']}), {diag['pool_t_reducing']:,} T-reducing; "
      f"T-reducing rules matching any start circuit: {diag['t_reducing_pool_rules_matching_any_start']} "
      f"({diag['t_reducing_pool_total_matches']} matches)")
""")

# ================================================================================================ 5. dev results
md(r"""
## 5. DEV results: LLM vs no-LLM control

Tier 1: best verified T per circuit for the LLM arm and the deterministic control at the same budget (8 compile+verify
evaluations), in both modes, next to the best reused classical (unitary-preserving) number. Tier 2: total DEV T for the
LLM-evolved and enumeration-control libraries. Both tables are read from the DEV CSVs.
""")

code(r"""
d1 = pd.read_csv(R2 / "tier1" / "dev_results.csv")
piv = d1[d1.arm.isin(["llm", "control"])].pivot_table(index="circuit", columns=["mode", "arm"], values="t_count")
piv.columns = [f"{m}_{a}" for m, a in piv.columns]
piv["best_classical"] = d1[d1.arm == "best_classical"].set_index("circuit")["t_count"]
piv = piv[["best_classical", "exact_control", "exact_llm", "relaxed_control", "relaxed_llm"]]
display(piv)
tally = []
for mode in ("exact", "relaxed"):
    l, c = piv[f"{mode}_llm"], piv[f"{mode}_control"]
    tally.append(dict(mode=mode, circuits=len(piv), llm_better=int((l < c).sum()), equal=int((l == c).sum()),
                      llm_worse=int((l > c).sum()), llm_no_valid_plan=int(l.isna().sum()),
                      control_below_classical=int((c < piv.best_classical).sum())))
TALLY1 = pd.DataFrame(tally); display(TALLY1)
run1 = json.loads((R2 / "tier1" / "dev_v1_run.json").read_text())

d2 = pd.read_csv(R2 / "tier2" / "dev_results.csv")
d2 = d2[d2.start_arm != "excluded"]
T2 = pd.DataFrame([dict(arm=a, circuits=len(d2), start_T=int(d2.start_t.sum()), final_T=int(d2[f"{a}_t"].sum()),
                        best_classical_T=int(d2.best_classical_t.sum()), start_gates=int(d2.start_gates.sum()),
                        lex_secondary_gates=int(d2[f"{a}_lex_gates"].sum())) for a in ("llm", "control")])
display(T2)
gens = pd.read_csv(R2 / "tier2" / "generations.csv")
prim = gens[gens.arm.isin(["llm", "control"])]
print("tier-2 primary arms: generations", prim.groupby("arm").gen.max().to_dict(), "| library versions accepted after v0:",
      prim[(prim.gen > 0) & prim.accepted.astype(str).eq("True")].groupby("arm").size().reindex(["llm", "control"], fill_value=0).to_dict(),
      "| final version:", prim.groupby("arm").library_version.last().to_dict())
""")

# ================================================================================================ 6. held-out
md(r"""
## 6. Held-out evaluation (frozen artifacts, no LLM arms)

Both LLM arms were null on DEV, so the held-out run (`results/v2/eval/`) evaluates the frozen deterministic tier-1
control, the frozen tier-2 library and their combination against the reused baselines. Unitary-preserving (exact)
and relaxed (ancilla + measurement) results are kept in separate tables; relaxed rows list their qubit and measurement
overhead and the zero-init promise they rely on.
""")

code(r"""
ev = pd.read_csv(R2 / "eval" / "eval_results.csv")
base = ev[ev.arm == "best_classical_ours"].set_index("circuit")
def arm(a, mode=None):
    x = ev[(ev.arm == a) & (ev["mode"] == mode)] if mode else ev[ev.arm == a]
    return x.set_index("circuit")
ex, rx = arm("tier1_control", "exact"), arm("tier1_control", "relaxed")
A = pd.DataFrame({"n": base.n.astype(int), "best_classical_ours": base.t_count, "arm": base.best_classical_ours_arm,
                  "tier1_exact": ex.t_count, "tier2_v0": arm("tier2_final").t_after,
                  "tier1+tier2_v0": arm("tier1+tier2_final").t_count,
                  "best_published": base.best_published_T, "check": ex.check})
print("A. unitary-preserving")
display(A)
B = pd.DataFrame({"best_classical_ours": base.t_count, "relaxed_T": rx.t_count, "ratio": (rx.t_count / base.t_count).round(2),
                  "qubits": rx.qubits.astype(int), "ancillas": rx.ancillas.astype(int), "measurements": rx.measurements.astype(int),
                  "zero_init_promise": rx.zero_qubits.fillna("none"), "variant": rx.variant + " + " + rx.global_pass, "check": rx.check})
print("B. relaxed (different contract)")
display(B)
SUM = dict(n=len(A), exact_eq=int((A.tier1_exact == A.best_classical_ours).sum()), exact_worse=int((A.tier1_exact > A.best_classical_ours).sum()),
           exact_better=int((A.tier1_exact < A.best_classical_ours).sum()), t2_changed=int((A.tier2_v0 != A.best_classical_ours).sum()),
           relaxed_lower=int((B.relaxed_T < B.best_classical_ours).sum()), relaxed_higher=int((B.relaxed_T > B.best_classical_ours).sum()),
           relaxed_total=int(B.relaxed_T.sum()), classical_total=int(B.best_classical_ours.sum()),
           min_lower=int((pd.concat([A.tier1_exact, B.relaxed_T], axis=1).min(axis=1) < A.best_classical_ours).sum()),
           pub_lower=int((A.best_published < A.best_classical_ours).sum()), pub_n=int(A.best_published.notna().sum()),
           anc_min=int(B.ancillas.min()), anc_max=int(B.ancillas.max()), meas_min=int(B.measurements.min()), meas_max=int(B.measurements.max()),
           variants=sorted(B.variant.unique()))
SUM["relaxed_pct"] = 100 * (SUM["relaxed_total"] / SUM["classical_total"] - 1)
print(SUM)
print("\nnot evaluated:")
for _, r in ev[ev.arm.isin(["skipped", "blocked"])].iterrows():
    print(f"  {r.circuit:14s} {r.arm:8s} {r.notes[:150]}")
display(Image(filename=str(R2 / "eval" / "eval_figure.png"), width=900))
""")

# ================================================================================================ 7. takeaways
md(r"""
## 7. Takeaways

Generated from the tables above (every number interpolated from the files read in sections 5-6).
""")

code(r"""
t1x, t1r = TALLY1.set_index("mode").loc["exact"], TALLY1.set_index("mode").loc["relaxed"]
gap = int(d2.start_t.sum() - d2.best_classical_t.sum())
display(Markdown(f'''
1. **LLM arms are null in both tiers on DEV.** Tier 1: LLM vs control better {t1x.llm_better} / equal {t1x.equal} / worse {t1x.llm_worse}
   in exact mode and {t1r.llm_better} / {t1r.equal} / {t1r.llm_worse} (no valid plan on {t1r.llm_no_valid_plan}) in relaxed mode over
   {t1x.circuits} circuits. Tier 2: total DEV T {T2.start_T[0]} → {T2.final_T[0]} (LLM) and {T2.start_T[1]} → {T2.final_T[1]} (control); the
   frozen library is {lib.version} with {len(lib.rules)} rules. The verified LLM rule shown in section 4 matched {app.matches.sum()} times on
   the {len(app)} start circuits, and {diag['t_reducing_pool_rules_matching_any_start']} of {diag['pool_t_reducing']:,} enumerated T-reducing identities match anywhere.
2. **Measurement-based gains are known constructions applied by a fixed rule.** On held-out, the relaxed control is below the
   best classical unitary-preserving T on {SUM['relaxed_lower']}/{SUM['n']} circuits (higher on {SUM['relaxed_higher']}), total
   {SUM['relaxed_total']} vs {SUM['classical_total']} ({SUM['relaxed_pct']:+.1f} %), at +{SUM['anc_min']} to +{SUM['anc_max']} ancillas and
   {SUM['meas_min']}-{SUM['meas_max']} mid-circuit measurements. Every relaxed winner is {', '.join(SUM['variants'])}: Gidney temporary AND, Jones
   Toffoli and the compute-only AND, chosen by the deterministic control. On DEV cuccaro_8 the replayed LLM plan gives
   {naive['t_count']} → {ev8['t_count']} T vs {bc8['t_count']:.0f} for {bc8['arm']}; the control reaches {piv.loc['cuccaro_8', 'relaxed_control']:.0f} with the same budget.
3. **Unitary-preserving: no gain over the classical bar.** Held-out exact tier 1 equals our best classical run on {SUM['exact_eq']}/{SUM['n']}
   circuits (worse on {SUM['exact_worse']}, better on {SUM['exact_better']}); tier-2 v0 changes T on {SUM['t2_changed']}. Published values (mostly
   pyzx+TODD, Kissinger & van de Wetering 2020) are lower than our best run on {SUM['pub_lower']} of {SUM['pub_n']} held-out circuits with a published
   value; on DEV the tier-2 start circuits total {T2.start_T[0]} T vs {T2.best_classical_T[0]} for the best classical incl. published rows ({gap} T gap). That gap is non-local (Reed-Muller / TODD phase-polynomial optimization), which ≤ 4-qubit templates cannot express.
4. **Candidate next directions** (let the LLM choose *non-local* operations, each still verified):
   phase-polynomial regions to hand to a TODD-style optimizer; ancilla reuse across Toffoli gadgets (cuccaro_8 relaxed uses
   {ev8['qubits']} qubits vs {lc8.n}); Toffoli-network restructuring (e.g. carry computation into fresh ancillas, Karatsuba-style gf2 multiplication).
'''))
""")

code(r"""
V.check_integrity()
print(f"frozen verifier digest unchanged: {integrity.frozen_digest() == DIGEST0}; notebook runtime {time.time() - T0:.1f} s")
""")


def main():
    nb = nbformat.v4.new_notebook()
    nb.cells = CELLS
    nb.metadata["kernelspec"] = {"display_name": ".venv (3.11)", "language": "python", "name": "python3"}
    nb.metadata["language_info"] = {"name": "python"}
    nbformat.validate(nb)
    nbformat.write(nb, NB)
    print(f"wrote {NB} ({len(CELLS)} cells)")


if __name__ == "__main__":
    main()
