"""Insert the playbook-ablation section (train / freeze / test) into group_meeting_demo.ipynb.

Idempotent: if the section marker is already present the cells are replaced in place, otherwise they are inserted
right after the stage-1 playbook section (section 5). Section 6 (stage-1 results) is renumbered to 7.
Every number shown by the new cells is read from results/window_runs/ablation_v1/ or playbooks/ at run time.

    .venv/bin/python notebooks/demo_assets/add_ablation_section.py
"""
import os
import sys

import nbformat

NB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "group_meeting_demo.ipynb")
MARK = "<!-- ablation_v1 section -->"

MD_HEAD = MARK + """
## 6. Does the shared playbook help? (train / freeze / test)

The stage-1 playbook in section 5 was learned and used on the same circuits, so it cannot show that its rules
transfer. This experiment separates learning from testing: a fresh, empty playbook is learned on **development**
circuits only (smaller members of the qft / qpe / qae families), then **frozen** and hashed, then **tested** on
held-out circuits in three arms: no playbook, the frozen learned playbook, and a placebo playbook holding one
hand-written generic rule of similar length that is rendered into the prompt by the same code path. Every arm gets
the same number of proposer calls per run and no reflector calls, so the playbook block is the only difference
in the prompt. The design parameters below are read from the run files in `results/window_runs/ablation_v1/`."""

CODE_DESIGN = r'''import hashlib
from circuitevolve.search.playbook import Playbook

AB = ROOT / "results" / "window_runs" / "ablation_v1"
PBDIR = ROOT / "playbooks"
abl = pd.read_csv(AB / "ablation_results.csv")
dev_prog = [json.loads(l) for l in (AB / "_dev_progress.jsonl").read_text().splitlines() if l.strip()]
frozen_sha = {name: sha for sha, name in (l.split() for l in (AB / "FROZEN.sha256").read_text().splitlines() if l.strip())}
sha_ok = {name: hashlib.sha256((PBDIR / name).read_bytes()).hexdigest() == sha for name, sha in frozen_sha.items()}
assert all(sha_ok.values()), f"playbook file changed after freezing: {sha_ok}"

dev_names = [r["name"] for r in dev_prog]
dev_prop = sum(r["stats"]["proposal_calls"] for r in dev_prog); dev_refl = sum(r["stats"]["reflect_calls"] for r in dev_prog)
dev_tok = sum(r["tokens"]["input"] + r["tokens"]["output"] for r in dev_prog)
ho = list(dict.fromkeys(abl.circuit)); arms = list(dict.fromkeys(abl.arm)); seeds = sorted(abl.seed.unique())
dev_eps = sorted({json.loads((AB / f"{r['tag']}_summary.json").read_text())["eps"] for r in dev_prog})
ho_eps = sorted({json.loads((AB / f"{t}_summary.json").read_text())["eps"] for t in abl.tag})
calls = sorted(abl.proposal_calls.unique()); assert int(abl.reflect_calls.sum()) == 0
assert abl[abl.arm == "learned"].playbook_sha256.eq(frozen_sha["dev_v1.json"]).all()
assert abl[abl.arm == "placebo"].playbook_sha256.eq(frozen_sha["placebo_v1.json"]).all()
display(Markdown("\n".join([
    f"* **Train** (development only): {', '.join(dev_names)} — {dev_prop} proposer + {dev_refl} reflector calls, "
    f"{dev_tok:,} tokens, eps_total {', '.join(f'{e:g}' for e in dev_eps)}.",
    f"* **Freeze**: " + "; ".join(f"`playbooks/{n}` SHA-256 `{s}` (file re-hashed now: {'match' if sha_ok[n] else 'MISMATCH'})"
                                  for n, s in frozen_sha.items()),
    f"* **Test** (held out): {', '.join(ho)} x arms {', '.join(arms)} x seeds {', '.join(map(str, seeds))}; "
    f"{'/'.join(map(str, calls))} proposer calls per run, reflector calls in all arms: {int(abl.reflect_calls.sum())}; "
    f"eps_total {', '.join(f'{e:g}' for e in ho_eps)}; model {', '.join(abl.model.unique())}.",
])))
dev_tab = pd.DataFrame([{"dev circuit": r["name"], "n": r["n"], "T start (=B0)": r["t_before"], "T end": r["t_after"],
                         "proposer": r["stats"]["proposal_calls"], "reflector": r["stats"]["reflect_calls"],
                         "accepted": r["stats"]["accepted"], "rules live after": r["playbook"]["live"],
                         "active after": r["playbook"]["active"]} for r in dev_prog]).set_index("dev circuit")
display(dev_tab)'''

CODE_RULES = r'''import textwrap
dev_pb = Playbook.load(PBDIR / "dev_v1.json", frozen=True)
plc_pb = Playbook.load(PBDIR / "placebo_v1.json", frozen=True)
zf = lambda r: Playbook.z_score(r, "improvement")
st = pd.Series([r.status for r in dev_pb.rules]).value_counts()
print(f"dev_v1: {len(dev_pb.rules)} rules proposed by the reflector -> active {st.get('active', 0)}, "
      f"candidate {st.get('candidate', 0)}, retired {st.get('retired', 0)} | promote at z >= {dev_pb.z_promote} "
      f"with >= {dev_pb.min_pass_with} improving prompts | frozen mode shows ACTIVE rules only\n")
act = [r for r in dev_pb.rules if r.status == "active"]
cand = sorted((r for r in dev_pb.rules if r.status == "candidate"), key=zf, reverse=True)[:3]
rows = []
for label, rs in (("ACTIVE (shown in the learned arm)", act), ("top-3 CANDIDATE (never shown when frozen)", cand),
                  ("PLACEBO (shown in the placebo arm)", [r for r in plc_pb.rules if r.status == "active"])):
    print(f"--- {label}")
    for r in rs:
        print(textwrap.fill(f"{r.id} [{r.status}] {r.text}", 116, subsequent_indent="    "))
        print(f"    evidence: improving prompts shown {r.with_improvements}/{r.with_prompts} vs hidden "
              f"{r.without_improvements}/{r.without_prompts}; z(now) = {zf(r):+.2f} {r.note}".rstrip())
        rows.append({"rule": r.id, "group": label.split(" (")[0], "chars": len(r.text), "shown improving": r.with_improvements,
                     "shown prompts": r.with_prompts, "hidden improving": r.without_improvements,
                     "hidden prompts": r.without_prompts, "z(now)": round(zf(r), 2)})
display(pd.DataFrame(rows).set_index("rule"))'''

MD_EXCERPT = """**6b — the same prompt with and without the playbook block.** From the held-out logs: the same circuit, seed and
call number, the same parent circuit and window, in the no-playbook and learned arms. In the first batch both arms
see identical prompts except for the inserted rule block (checked below with a character diff). The pair shown was
picked because the verdicts differ; the tally over all such matched pairs follows it, so one example is not read as
evidence (the LLM's own sampling is not seeded)."""

CODE_EXCERPT = r'''import difflib
def calls_of(tag):
    return {r["call"]: r for r in map(json.loads, (AB / f"{tag}.jsonl").read_text().splitlines()) if r["kind"] == "propose"}

def verdict(r):
    if r.get("error"):
        return "LLM error"
    if r.get("accepted"):
        best = min((c for c in r["candidates"] if c.get("verify", {}).get("ok") and c.get("cost")), key=lambda c: c["cost"]["t"])
        return f"accepted (circuit T after splice {best['cost']['t']:,})"
    if r.get("candidates"):
        return "rejected: " + "; ".join(sorted({c.get("decision", "?") for c in r["candidates"]}))
    return "declined (NONE)" if r.get("declined") else "no parsable proposal"

def matched_pairs(arm_b="learned"):
    out = []
    for c in ho:
        for s in seeds:
            A, B = calls_of(f"ho_{c}_none_s{s}"), calls_of(f"ho_{c}_{arm_b}_s{s}")
            for k, a in A.items():
                b = B.get(k)
                if not b or a["parent"] != b["parent"] or a["window"] != b["window"] or "prompt" not in a or "prompt" not in b:
                    continue
                ops = [o for o in difflib.SequenceMatcher(None, a["prompt"], b["prompt"], autojunk=False).get_opcodes() if o[0] != "equal"]
                if len(ops) == 1 and ops[0][0] == "insert":
                    out.append((c, s, k, a, b, ops[0]))
    return out

pairs = matched_pairs()
EX = ("qpe_8", 0, 4)                                   # circuit, seed, call (a pair whose verdicts differ)
c_, s_, k_, a, b, op = next(p for p in pairs if p[:3] == EX)
w = a["window"]
print(f"{c_} seed {s_} call {k_} | window {w['index']} on qubits {w['qubits']}, {w['n_ops']} ops, window T-cost {w['t_cost']} "
      f"| allowance {a['allowance']:.3g} | prompt {len(a['prompt'])} vs {len(b['prompt'])} chars; the only difference is "
      f"one insertion of {op[4] - op[3]} chars:")
ctx = b["prompt"][op[3] - 160: op[4] + 90]
print("\n...", ctx.replace(b["prompt"][op[3]:op[4]], ">>> " + b["prompt"][op[3]:op[4]].rstrip("\n").replace("\n", "\n>>> ") + "\n"), "...\n", sep="")
for arm, r in (("none", a), ("learned", b)):
    print(f"=== {arm} response (first 900 chars) -> VERDICT: {verdict(r)}")
    print(textwrap.indent(r["response"][:900] + (" [...]" if len(r["response"]) > 900 else ""), "  | "))
    fence = re.findall(r"```(?:fix|window)\n.*?```", r["response"], re.S)
    if fence:
        print("  proposals parsed from fenced blocks:", " / ".join(f.replace("\n", " ") for f in fence))
    print()
cls = lambda r: verdict(r).split(" (")[0].split(":")[0]
tally = pd.crosstab(pd.Series([cls(p[3]) for p in pairs], name="none arm"),
                    pd.Series([cls(p[4]) for p in pairs], name="learned arm"), margins=True)
print(f"All matched first-batch pairs (prompt differs only by the inserted rule): {len(pairs)} pairs over "
      f"{len({p[:2] for p in pairs})} circuit x seed blocks")
display(tally)
n_none_only = sum(cls(p[3]) == "accepted" and cls(p[4]) != "accepted" for p in pairs)
n_learned_only = sum(cls(p[4]) == "accepted" and cls(p[3]) != "accepted" for p in pairs)
print(f"discordant on acceptance: accepted only without the rule {n_none_only}, accepted only with the rule {n_learned_only}")'''

MD_TABLE = """**6c — held-out results.** T reduction vs B0 (TKET + gridsynth), % (higher is better), per seed and averaged over
the runs that enter the paired statistics, next to the no-LLM same-Pauli merge control (section 7). Runs flagged
`INVALID` hit an infrastructure error in the LLM backend (reason read from the call log); the whole circuit x seed
block they belong to is excluded from the means and the paired statistics."""

CODE_TABLE = r'''def flag(r):
    if not r.valid:
        errs = [x["error"] for x in calls_of(r.tag).values() if x.get("error")]
        why = re.search(r"per-frame token ceiling \([^)]*\)", errs[0]) if errs else None
        return f"INVALID: {r.llm_errors}/{r.llm_calls} calls errored ({why.group(0) if why else (errs[0][:60] if errs else '?')})"
    return "" if r.in_paired else "valid, excluded (block incomplete)"
abl["flag"] = abl.apply(flag, axis=1)
abl["cell"] = abl.apply(lambda r: f"{r.reduction_pct:.2f}" + (" [INVALID]" if not r.valid else " [excl.]" if not r.in_paired else ""), axis=1)
per_seed = abl.pivot_table(index=["circuit", "arm"], columns="seed", values="cell", aggfunc="first", sort=False)
per_seed.columns = [f"seed {s} %" for s in per_seed.columns]
per_seed["mean % (paired runs)"] = abl[abl.in_paired].groupby(["circuit", "arm"], sort=False).reduction_pct.mean().round(2)
per_seed["flags"] = abl.groupby(["circuit", "arm"], sort=False).flag.apply(lambda f: "; ".join(f"s{s}: {x}" for s, x in zip(abl.loc[f.index, "seed"], f) if x))
display(per_seed)
print("Flagged rows (from ablation_results.csv valid / in_paired and the call logs):")
for _, r in abl[abl.flag != ""].iterrows():
    print(f"  {r.tag}: {r.flag}")

ctrl = pd.DataFrame(json.loads((AB / "control_pmerge.json").read_text())["rows"]).set_index("name")
b0 = abl.groupby("circuit", sort=False).B0.first()
summ = abl[abl.in_paired].pivot_table(index="circuit", columns="arm", values="reduction_pct", aggfunc="mean", sort=False)[arms].round(2)
summ.columns = [f"{a} mean %" for a in arms]
summ.insert(0, "B0 T", b0)
summ["merge rule T"] = ctrl.loc[summ.index, "t"]
summ["merge rule %"] = (100 * (1 - ctrl.loc[summ.index, "t"] / b0)).round(2)
summ["paired blocks"] = abl[abl.in_paired].groupby("circuit").seed.nunique()
display(summ)

PS = json.loads((AB / "paired_stats.json").read_text())
paired = pd.DataFrame([{"comparison": k, "pairs": v["n_pairs"], "mean pp": v["mean_pp"], "median pp": v["median_pp"],
                        "+ / - / tie": f"{v['positive']} / {v['negative']} / {v['ties']}", "sign test p": round(v["sign_test_p"], 3),
                        "bootstrap 95% CI": f"[{v['boot95'][0]:+.2f}, {v['boot95'][1]:+.2f}]",
                        "CI contains 0": v["boot95"][0] <= 0 <= v["boot95"][1],
                        **{f"{c} diffs": ", ".join(f"{d:+.2f}" for d in pc["diffs"]) for c, pc in v["per_circuit"].items()}}
                       for k, v in PS.items()]).set_index("comparison")
display(paired)
# cross-check paired_stats.json against the CSV (recomputed here, no new statistics)
red = abl[abl.in_paired].pivot_table(index=["circuit", "seed"], columns="arm", values="reduction_pct")
for k, v in PS.items():
    x, y = k.split("-"); d = (red[x] - red[y]).dropna()
    assert len(d) == v["n_pairs"] and abs(d.mean() - v["mean_pp"]) < 5e-3, (k, d.mean(), v["mean_pp"])
    assert ((d > 0).sum(), (d < 0).sum(), (d == 0).sum()) == (v["positive"], v["negative"], v["ties"]), k
print("paired_stats.json means and sign counts reproduced from ablation_results.csv:", list(PS))'''

CODE_FIG = r'''display(Image(filename=str(AB / "ablation_figure.png"), width=820))'''

MD_TAKE = """**Takeaway (computed from the files above).**"""

CODE_TAKE = r'''ln, lp = PS["learned-none"], PS["learned-placebo"]
both_zero = all(v["boot95"][0] <= 0 <= v["boot95"][1] for v in (ln, lp))
valid_runs = abl[abl.valid]
best_llm = valid_runs.loc[valid_runs.reduction_pct.idxmax()]
ctrl_pct = (100 * (1 - ctrl.t / b0.reindex(ctrl.index)))
beats_all = all(ctrl_pct[c] > valid_runs[valid_runs.circuit == c].reduction_pct.max() for c in ctrl.index)
n_act = len(act)
display(Markdown("\n".join([
    f"1. **Null result.** learned - none = {ln['mean_pp']:+.2f} pp (95% CI {ln['boot95'][0]:+.2f} to {ln['boot95'][1]:+.2f}, "
    f"sign test p = {ln['sign_test_p']:.2f}); learned - placebo = {lp['mean_pp']:+.2f} pp (CI {lp['boot95'][0]:+.2f} to "
    f"{lp['boot95'][1]:+.2f}, p = {lp['sign_test_p']:.2f}), over {ln['n_pairs']} paired circuit x seed blocks. "
    f"Both CIs contain zero: **{both_zero}**. The placebo arm is as far from 'none' as the learned arm "
    f"(placebo - none = {PS['placebo-none']['mean_pp']:+.2f} pp).",
    f"2. **One generic rule.** Of {len(dev_pb.rules)} rules the reflector proposed on the development circuits, "
    f"{n_act} became active ({', '.join(r.id for r in act)}: track the Pauli frame before deleting a rotation), which largely "
    f"restates what the prompt already provides; so this tests a single generic rule, not a rich playbook.",
    f"3. **The no-LLM merge rule beats every LLM run.** Merge rule {ctrl_pct.min():.1f}-{ctrl_pct.max():.1f} % vs B0; best valid "
    f"LLM run {best_llm.reduction_pct:.2f} % ({best_llm.tag}). Control above every valid run on every circuit: **{beats_all}**.",
    "",
    "**So:** more rules in the prompt is not where the gain is. The next step is to change *what the LLM decides*: let it "
    "choose the strategy and the error-budget allocation (which windows to spend the approximation budget on, which "
    "rotations to fix vs. synthesize) on top of the deterministic merge pass, rather than asking it for local window "
    "rewrites the merge rule already finds.",
])))'''

NEW = [nbformat.v4.new_markdown_cell(MD_HEAD), nbformat.v4.new_code_cell(CODE_DESIGN),
       nbformat.v4.new_markdown_cell("**6a — the frozen rules.** The learned arm sees only ACTIVE rules; the top candidate "
                                     "rules by evidence (z of improving-prompt rates, shown vs hidden) are listed to show "
                                     "what nearly made it. The placebo rule is the control."),
       nbformat.v4.new_code_cell(CODE_RULES), nbformat.v4.new_markdown_cell(MD_EXCERPT), nbformat.v4.new_code_cell(CODE_EXCERPT),
       nbformat.v4.new_markdown_cell(MD_TABLE), nbformat.v4.new_code_cell(CODE_TABLE),
       nbformat.v4.new_markdown_cell("**6d — figure** (`results/window_runs/ablation_v1/ablation_figure.png`, written by "
                                     "`experiments/window_ablation_report.py`)."),
       nbformat.v4.new_code_cell(CODE_FIG), nbformat.v4.new_markdown_cell(MD_TAKE), nbformat.v4.new_code_cell(CODE_TAKE)]

nb = nbformat.read(NB, as_version=4)
cells = nb.cells
idx = [i for i, c in enumerate(cells) if c.cell_type == "markdown" and c.source.startswith(MARK)]
if idx:                                      # replace an earlier insertion
    i0 = idx[0]
    i1 = next(i for i in range(i0 + 1, len(cells)) if cells[i].cell_type == "markdown" and cells[i].source.startswith("## "))
    cells[i0:i1] = NEW
else:
    i_s5 = next(i for i, c in enumerate(cells) if c.cell_type == "markdown" and c.source.startswith("## 5."))
    i_next = next(i for i in range(i_s5 + 1, len(cells)) if cells[i].cell_type == "markdown" and cells[i].source.startswith("## "))
    cells[i_next:i_next] = NEW
for c in cells:
    if c.cell_type == "markdown" and c.source.startswith("## 6. Stage-1 results"):
        c.source = c.source.replace("## 6. Stage-1 results", "## 7. Stage-1 results", 1)
    if c.cell_type == "markdown" and c.source.startswith("**Next steps.**") and "(3) Freeze the stage-1 playbook" in c.source:
        c.source = c.source.replace("rules.", "rules (done with a fresh development playbook in section 6: null result).", 1)
nbformat.validate(nb)
nbformat.write(nb, NB)
print(f"cells: {len(cells)} ({sum(c.cell_type == 'code' for c in cells)} code)")
