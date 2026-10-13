"""Program-evolution loop (OpenEvolve / AlphaEvolve style) over optimizer programs.

  * Archive: MAP-Elites grid per island; feature cells = program length (AST nodes, 5 bins) x FAST charged
    runtime (5 bins). A cell keeps the program with the best FAST fitness key.
  * Islands (default 2), round-robin; every `migrate_every` proposer calls each island's best is copied into
    the other islands.
  * Proposal: the LLM sees the toolbox API, a parent program with its per-circuit FAST results, two
    inspiration programs, recent failures, and the playbook's rules. It answers with SEARCH/REPLACE diff
    blocks or a full rewrite in a ```python block. Responses are parsed LITERALLY (string matching / code
    fence extraction, then ast.parse in sandbox.static_check); nothing is executed in the parent.
  * Cascade: FAST subset first; candidates valid on FAST with geomean <= (1 + cascade_tol) x best FAST geomean
    are evaluated on the full development set. The champion is the best full-dev fitness key.
  * Evaluation cache keyed by source hash (evaluate.eval_key), shared across runs.
  * Playbook: rules shown in prompts (A/B for candidates); the evidence gate counts MEASURED IMPROVEMENTS:
    a prompt "improved" iff its child's FAST geomean is strictly lower than its parent's (playbook.py,
    evidence='improvement'). Reflector calls are LLM calls and are counted.
  * Logging: every proposer and reflector call (prompt hash, full response, parse result, evaluation summary)
    to results/<tag>/calls.jsonl; every candidate program to results/<tag>/programs/<hash>.py.
Fitness (lexicographic): valid on all circuits -> geomean T(program)/T(best classical) -> charged runtime.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import random
import re
import time
from pathlib import Path

from . import split
from .evaluate import baseline, evaluate_program, source_hash
from .programs import SEED_PROGRAM
from .sandbox import StaticCheckError, static_check
from .toolbox import API_DOC
from circuitevolve.blocks import REPO

RESULTS = REPO / "results" / "evolve_opt"
LEN_BINS = (60, 120, 200, 350)            # AST nodes
RT_BINS = (15.0, 40.0, 90.0, 200.0)       # FAST charged CPU seconds (sum over circuits)

TASK_TEXT = """You are improving an OPTIMIZER PROGRAM for fault-tolerant quantum circuit compilation. The program
`optimize(circ, tools, budget)` receives a logical circuit (U3+CX) and must return an equivalent Clifford+Rz
circuit with as few T gates as possible after every non-Clifford rz is synthesised with gridsynth at
eps = 1e-9 (about 80-100 T per rotation, so removing or merging rotations matters most; explicit T gates
cost 1). Score = geometric mean over benchmark circuits of T(program) / T(best classical), where best
classical = the lower of pyzx full_reduce and TKET FullPeepholeOptimise. Lower is better; 1.0 = parity.
Every output is checked against the original circuit by an independent verifier (unitary / statevector)
and against the error budget; an invalid output on ANY circuit gives the program no score. Ties are
broken by charged CPU time. The program may ONLY call `tools.*` and use plain Python control flow
(no imports, no attribute access except tools.<name> and list/dict methods, no names starting with '_',
no open/eval/exec/getattr/print). The same program runs on all circuits (it does not see their names)."""

FORMAT_TEXT = """Answer with at most ~150 words of reasoning, then EITHER one or more diff blocks against the parent:
<<<<<<< SEARCH
(exact lines copied from the parent program)
=======
(replacement lines)
>>>>>>> REPLACE
OR a complete new program in a single ```python block. Propose ONE program. Do not print tool output,
tables or simulated results."""


# ------------------------------------------------------------------------------ response parsing
DIFF_RE = re.compile(r"<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n?>>>>>>> REPLACE", re.S)


def _python_blocks(text: str) -> list:
    """Code blocks in fence pairs (line-based); only ```python / ```py / bare fences."""
    out, cur, lang = [], None, None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("```"):
            if cur is None:
                lang = s[3:].strip().lower()
                cur = []
            else:
                if lang in ("python", "py", ""):
                    out.append("\n".join(cur))
                cur = None
            continue
        if cur is not None:
            cur.append(line)
    return out


def parse_response(text: str, parent_src: str) -> dict:
    """-> {'kind': 'diff'|'rewrite'|None, 'source': str|None, 'error': str|None, 'n_diffs': int}.
    Literal parsing only: SEARCH text must occur exactly once in the (progressively edited) parent."""
    if not isinstance(text, str):
        return dict(kind=None, source=None, error=f"llm error: {text}", n_diffs=0)
    diffs = DIFF_RE.findall(text)
    if diffs:
        src = parent_src
        for i, (search, repl) in enumerate(diffs):
            k = src.count(search)
            if k != 1:
                return dict(kind="diff", source=None, n_diffs=len(diffs),
                            error=f"diff {i + 1}: SEARCH text found {k} times in the parent (must be exactly once)")
            src = src.replace(search, repl, 1)
        return dict(kind="diff", source=src, error=None, n_diffs=len(diffs))
    blocks = [b for b in _python_blocks(text) if "def optimize" in b]
    if blocks:
        return dict(kind="rewrite", source=blocks[-1].strip() + "\n", error=None, n_diffs=0)
    return dict(kind=None, source=None, error="no diff block and no ```python block defining optimize", n_diffs=0)


# ------------------------------------------------------------------------------ archive
def features(src: str, fast_runtime: float) -> tuple:
    try:
        nodes = len(list(ast.walk(ast.parse(src))))
    except SyntaxError:
        nodes = 0
    lb = sum(nodes > b for b in LEN_BINS)
    rb = sum(fast_runtime > b for b in RT_BINS)
    return (lb, rb)


class Archive:
    def __init__(self, n_islands: int):
        self.islands = [dict() for _ in range(n_islands)]
        self.programs = {}                   # id -> entry

    def add(self, entry: dict, island: int) -> bool:
        self.programs[entry["id"]] = entry
        if not entry["fast"]["valid"]:
            return False
        cell = tuple(entry["features"])
        cur = self.islands[island].get(cell)
        if cur is None or tuple(entry["fast"]["key"]) < tuple(self.programs[cur]["fast"]["key"]):
            self.islands[island][cell] = entry["id"]
            return True
        return False

    def elites(self, island=None) -> list:
        isl = range(len(self.islands)) if island is None else [island]
        return [self.programs[i] for k in isl for i in self.islands[k].values()]

    def best_fast(self, island=None):
        el = self.elites(island)
        return min(el, key=lambda e: tuple(e["fast"]["key"])) if el else None

    def best_dev(self):
        el = [e for e in self.programs.values() if e.get("dev") and e["dev"]["valid"]]
        return min(el, key=lambda e: tuple(e["dev"]["key"])) if el else None

    def to_json(self) -> dict:
        return dict(islands=[{f"{k[0]},{k[1]}": v for k, v in isl.items()} for isl in self.islands],
                    programs={i: {k: v for k, v in e.items() if k != "src"} for i, e in self.programs.items()})


# ------------------------------------------------------------------------------ prompt
def _result_lines(entry: dict, ref: dict) -> str:
    fit = entry["fast"]
    lines = []
    for nm in sorted(entry.get("fast_results", {})):
        r = entry["fast_results"][nm]
        if r.get("valid"):
            c = r["cost"]
            lines.append(f"  {nm}: T = {c['t']} (best classical {ref[nm]['t']}, ratio {c['t'] / ref[nm]['t']:.4f}), "
                         f"rz = {c['rz']}, cx = {c['cx']}, charged {r.get('charged_s') or 0:.1f} s")
        else:
            lines.append(f"  {nm}: INVALID - {str(r.get('reason'))[:160]}")
    head = (f"score (geomean ratio) = {fit['geomean']:.5f}, charged CPU = {fit['runtime']:.1f} s"
            if fit["valid"] else "INVALID on at least one circuit")
    if entry.get("dev"):
        d = entry["dev"]
        if d["valid"]:
            gains = ", ".join(f"{k} {v:.4f}" for k, v in sorted(d["ratios"].items()) if v < 1 - 1e-12) or "none"
            slow = max(((r.get("charged_s") or 0.0), k) for k, r in entry.get("dev_results", {}).items())
            head += (f"\nfull development set ({len(d['ratios'])} circuits): score {d['geomean']:.5f}; circuits below "
                     f"parity: {gains}; slowest {slow[1]} {slow[0]:.0f} s charged")
        else:
            head += "\nfull development set: INVALID on " + ", ".join(sorted(d["failures"]))[:300]
    return head + "\n" + "\n".join(lines)


def build_prompt(parent: dict, inspirations: list, failures: list, rules_text: str, ref: dict,
                 fast_names: list, time_s: float = 300.0) -> str:
    insp = "\n\n".join(f"## inspiration {i + 1} (score {e['fast']['geomean']:.5f})\n```python\n{e['src']}```"
                       for i, e in enumerate(inspirations)) or "(none)"
    fail = "\n".join(f"  - {why[:240]}" for why in failures[-4:]) or "  (none)"
    return f"""{TASK_TEXT}

{API_DOC}
Benchmark circuits for this round (FAST subset): {', '.join(fast_names)}. Programs within 2 % of the best
FAST score are also run on the full development set (17 circuits, 4-16 qubits, up to ~5,700 gates); the
budget is {time_s:.0f} charged CPU seconds per circuit (pyzx full_reduce on the largest circuit takes ~90 s).

{rules_text}

# Parent program
```python
{parent['src']}```
Parent results:
{_result_lines(parent, ref)}

# Other good programs
{insp}

# Recent failures of proposed programs
{fail}

{FORMAT_TEXT}"""


# ------------------------------------------------------------------------------ the loop
def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def run_evolution(tag: str, complete, n_calls: int = 120, seed: int = 0, batch: int = 4, n_islands: int = 2,
                  playbook=None, reflect_every: int = 16, migrate_every: int = 24, workers: int = 6,
                  time_s: float = 300.0, cascade_tol: float = 0.02, fast_names=None, dev_names=None,
                  seed_source: str = SEED_PROGRAM, out_root: Path = RESULTS, log=print) -> dict:
    """complete(list[str]) -> list[str | Exception] (search/llm.make_api_backend or a fake).
    Writes results under out_root/tag (refuses to overwrite)."""
    from circuitevolve.integrity import check_unchanged, frozen_digest
    from circuitevolve.search.playbook import Playbook
    digest = frozen_digest()
    out = Path(out_root) / tag
    if out.exists():
        raise FileExistsError(f"{out} exists (results are append-only); choose a new tag")
    (out / "programs").mkdir(parents=True)
    fast_names = list(fast_names or split.fast())
    dev_names = list(dev_names or split.dev())
    for nm in dev_names:
        split.check_dev(nm)
    ref = baseline(dev_names)
    rng = random.Random(seed)
    pb = playbook if playbook is not None else Playbook(evidence="improvement")
    calls_f = open(out / "calls.jsonl", "a")
    t_start = time.time()
    stats = dict(proposer_calls=0, reflector_calls=0, llm_errors=0, parse_errors=0, static_errors=0,
                 duplicates=0, fast_evals=0, dev_evals=0, valid_fast=0, improved=0, new_cells=0)
    be_stats0 = dict(getattr(complete, "stats", {}))
    archive = Archive(n_islands)
    failures: list = []
    improvements: list = []
    seen: dict = {}

    def write_prog(src):
        p = out / "programs" / f"{source_hash(src)[:16]}.py"
        if not p.exists():
            p.write_text(src)

    def evaluate(src, parent_id, island, call):
        h = source_hash(src)
        if h in seen:
            stats["duplicates"] += 1
            return archive.programs[seen[h]], True
        write_prog(src)
        fr = evaluate_program(src, fast_names, ref, workers=workers, time_s=time_s)
        stats["fast_evals"] += 1
        entry = dict(id=f"p{len(archive.programs)}", hash=h, src=src, parent=parent_id, island=island, call=call,
                     fast=fr["fitness"], fast_results=fr["results"], dev=None,
                     features=list(features(src, fr["fitness"]["runtime"])), static_error=fr.get("static_error"))
        if fr["fitness"]["valid"]:
            stats["valid_fast"] += 1
            bf = archive.best_fast()
            thr = (bf["fast"]["geomean"] if bf else entry["fast"]["geomean"]) * (1 + cascade_tol)
            if entry["fast"]["geomean"] <= thr:
                rest = [nm for nm in dev_names if nm not in fast_names]
                dr = evaluate_program(src, rest, ref, workers=workers, time_s=time_s)
                allres = dict(fr["results"], **dr["results"])
                from .evaluate import fitness
                entry["dev"] = fitness(allres, dev_names, ref)
                entry["dev_results"] = {k: _slim(v) for k, v in allres.items()}
                stats["dev_evals"] += 1
        entry["fast_results"] = {k: _slim(v) for k, v in fr["results"].items()}
        seen[h] = entry["id"]
        if archive.add(entry, island):
            stats["new_cells"] += 1
        return entry, False

    # seed
    seed_entry, _ = evaluate(seed_source, None, 0, 0)
    for k in range(1, n_islands):
        archive.add(seed_entry, k)
    log(f"[{tag}] seed: fast {seed_entry['fast']['geomean']:.5f} dev "
        f"{seed_entry['dev']['geomean'] if seed_entry['dev'] else None}")
    calls_f.write(json.dumps(dict(kind="seed", id=seed_entry["id"], fast=seed_entry["fast"],
                                  dev=seed_entry["dev"])) + "\n")
    calls_f.flush()

    call = 0
    while call < n_calls:
        nb = min(batch, n_calls - call)
        jobs = []
        for j in range(nb):
            island = (call + j) % n_islands
            el = archive.elites(island)
            parent = (archive.best_fast(island) if rng.random() < 0.5 else rng.choice(el)) if el else seed_entry
            others = [e for e in archive.elites() if e["id"] != parent["id"]]
            insp = []
            bd = archive.best_dev()
            if bd and bd["id"] != parent["id"]:
                insp.append(bd)
            others = [e for e in others if all(e["id"] != x["id"] for x in insp)]
            if others:
                insp.append(rng.choice(others))
            texts, shown, hidden = pb.select(rng)
            prompt = build_prompt(parent, insp[:2], failures, pb.render(texts), ref, fast_names, time_s)
            jobs.append(dict(island=island, parent=parent, shown=shown, hidden=hidden, prompt=prompt))
        t0 = time.time()
        responses = complete([j["prompt"] for j in jobs])
        llm_s = time.time() - t0
        for j, resp in zip(jobs, responses):
            call += 1
            stats["proposer_calls"] += 1
            rec = dict(kind="proposer", call=call, island=j["island"], parent=j["parent"]["id"],
                       prompt_sha=_sha(j["prompt"])[:16], prompt_chars=len(j["prompt"]), shown=j["shown"],
                       hidden=j["hidden"], llm_batch_s=round(llm_s, 1))
            if isinstance(resp, Exception):
                stats["llm_errors"] += 1
                rec.update(error=str(resp)[:300])
                pb.record(j["shown"], j["hidden"], 0, 0, False)
                calls_f.write(json.dumps(rec) + "\n")
                continue
            rec["response"] = resp
            pr = parse_response(resp, j["parent"]["src"])
            rec["parse"] = dict(kind=pr["kind"], error=pr["error"], n_diffs=pr["n_diffs"])
            improved, valid = False, False
            if pr["source"] is None:
                stats["parse_errors"] += 1
                failures.append(f"unparseable response: {pr['error']}")
            else:
                try:
                    static_check(pr["source"])
                except StaticCheckError as e:
                    stats["static_errors"] += 1
                    failures.append(f"static check: {e}")
                    rec["static_error"] = str(e)
                    write_prog(pr["source"])
                    rec["src_hash"] = source_hash(pr["source"])[:16]
                else:
                    entry, dup = evaluate(pr["source"], j["parent"]["id"], j["island"], call)
                    valid = entry["fast"]["valid"]
                    pf, cf = j["parent"]["fast"], entry["fast"]
                    improved = bool(valid and pf["valid"] and cf["geomean"] < pf["geomean"] * (1 - 1e-9))
                    if improved and not dup:
                        stats["improved"] += 1
                        improvements.append((round(pf["geomean"], 5), round(cf["geomean"], 5),
                                             j["parent"]["src"], entry["src"]))
                    if not valid:
                        why = "; ".join(f"{k}: {str(v)[:120]}" for k, v in list(cf["failures"].items())[:2])
                        failures.append(f"invalid output ({why})")
                    rec.update(child=entry["id"], src_hash=entry["hash"][:16], duplicate=dup, fast=cf,
                               dev=entry["dev"], improved=improved)
            pb.record(j["shown"], j["hidden"], 1 if pr["source"] else 0, int(valid), improved)
            for rid, new, z in pb.update_status(call):
                rec.setdefault("playbook_changes", []).append([rid, new, z])
            calls_f.write(json.dumps(rec) + "\n")
            calls_f.flush()
        # migration
        if n_islands > 1 and migrate_every and call % migrate_every < nb:
            for k in range(n_islands):
                b = archive.best_fast(k)
                for m in range(n_islands):
                    if m != k and b:
                        archive.add(b, m)
        # reflection
        if reflect_every and not pb.frozen and call % reflect_every < nb and (improvements or failures):
            rp = pb.reflect_prompt(TASK_TEXT, improvements[-2:] and [(a, b, c[:1500], d[:1500])
                                                                    for a, b, c, d in improvements[-2:]],
                                   [(f"(program)", w) for w in failures[-4:]], dict(stats))
            r = complete([rp])[0]
            stats["reflector_calls"] += 1
            if isinstance(r, Exception):
                applied, errs = [], [str(r)[:200]]
            else:
                applied, errs = pb.apply_deltas(r, call)
            calls_f.write(json.dumps(dict(kind="reflector", call=call, prompt_sha=_sha(rp)[:16],
                                          response=r if isinstance(r, str) else None, applied=applied,
                                          errors=errs)) + "\n")
            calls_f.flush()
            improvements, failures = improvements[-2:], failures[-4:]
        bd, bf = archive.best_dev(), archive.best_fast()
        log(f"[{tag}] call {call}/{n_calls}: best fast {bf['fast']['geomean']:.5f} best dev "
            f"{bd['dev']['geomean'] if bd else float('nan'):.5f} | {json.dumps(stats)}")
    calls_f.close()
    check_unchanged(digest)
    best = archive.best_dev()
    be = getattr(complete, "stats", {})
    backend_delta = {k: be.get(k, 0) - be_stats0.get(k, 0) for k in be}
    (out / "best_program.py").write_text(best["src"])
    (out / "archive.json").write_text(json.dumps(archive.to_json(), indent=1, default=str))
    pb.save(out / "playbook.json")
    (out / "playbook.md").write_text(pb.to_markdown())
    summary = dict(tag=tag, seed=seed, n_calls=n_calls, batch=batch, n_islands=n_islands, time_s=time_s,
                   cascade_tol=cascade_tol, fast=fast_names, dev=dev_names, stats=stats, backend=backend_delta,
                   seed_program=dict(id=seed_entry["id"], fast=seed_entry["fast"], dev=seed_entry["dev"]),
                   best=dict(id=best["id"], hash=best["hash"], call=best["call"], fast=best["fast"], dev=best["dev"],
                             dev_results=best.get("dev_results")),
                   frozen_digest=digest, seconds=round(time.time() - t_start, 1))
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    return summary


def _slim(r: dict) -> dict:
    keep = ("valid", "reason", "cost", "bound", "ledger", "charged_s", "wall_s", "cached", "calls")
    d = {k: r.get(k) for k in keep if k in r}
    if "check" in r:
        d["check"] = r["check"]
    return d
