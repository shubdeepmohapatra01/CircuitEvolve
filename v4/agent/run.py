"""Drive the loop with real LLM calls - the only place in v4 that calls an LLM.

    .venv/bin/python -m v4.agent.run                      # start, or RESUME from results/<tag>/state.json
    .venv/bin/python -m v4.agent.run --dry-run            # print the scout's context and stop, no calls
    .venv/bin/python -m v4.agent.run --budget 60 --loops 4 --tag run1
    touch v4/results/<tag>/STOP                           # stop cleanly after the current attempt

Two subprocess calls per attempt, and NOTHING else is an LLM:

  scout        `claude -p` with Read / WebSearch / WebFetch, cwd = a per-attempt context folder, so Read
               reaches only that folder. Returns ONE rule card as JSON.
  implementer  `claude -p` with Read / Write / Edit / Bash, writes allowed only under
               `v4/rules/candidates/`, Bash restricted to `v4.tools.test_rule`, permission mode dontAsk
               so everything else is denied. Returns one `.py` file.

Caps, per V4_README section 10: **the LLM is capped on wall clock and dollars, verification never is.**
A timed-out agent call retries or moves on and cannot bias which rules are admitted; a timed-out
verification discards correct, verified, improving rules, which is exactly what v3's 300 s limit did to
`staircase_knapsack_exact_angle_assignment` and `joint_budget_direct_rotation_synthesis`.

Integrity, as in v3: `check_frozen()` at the start and the end, and a hash snapshot of `v4/` outside
`candidates/`, `results/` and the caches compared before and after every implementer call. Any change
outside `candidates/` stops the run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .. import baselines as Ba, book as B, fingerprint as FP
from ..judge import dv as J
from ..judge.frozen import check_frozen, recheck_frozen
from ..loop import CIRCUIT_ORDER, GAIN_ORDER, Loop, LoopConfig
from ..paths import CANDIDATES, MANIFEST, REPO, RESULTS, RULES, V4

SCOUT_MODEL = "claude-opus-5"
IMPL_MODEL = "claude-sonnet-5-5"
TIMEOUT = dict(scout=1200, implementer=2700)
BUDGET_USD = dict(scout=4.0, implementer=8.0)
PROMPTS = V4 / "agent"
FATAL = re.compile(r"usage limit|limit reached|rate.?limit|hit your limit|credit balance|"
                   r"insufficient (credit|funds)|billing|authenticat|not logged in|please (run )?/?login|"
                   r"invalid api key|unauthori[sz]ed|\b401\b|\b403\b|oauth|token (has )?expired|"
                   r"subscription", re.I)


class Fatal(RuntimeError):
    """Usage-limit / credential error: stop the whole run cleanly, leaving the rest 'not run'."""


# ------------------------------------------------------------------------------------------ integrity
# What the integrity snapshot IGNORES. The guard exists to stop an implementer touching the judge, the
# api, the runner, the loop or the rule book - anything that could change what gets accepted. The
# top-level prose files cannot, and including them means any edit to BUILD_LOG.md while a run is in
# flight kills the run: that happened, with "the implementer changed files outside rules/candidates/:
# ['BUILD_LOG.md']", after two perfectly good attempts.
SKIP = ("rules/candidates/", "results/", ".cache/", "__pycache__", "tests/fixtures/")
SKIP_FILES = ("BUILD_LOG.md", "README.md", "SCOPE.md", "V4_README.md")


def tree_digest() -> dict:
    out = {}
    for p in sorted(V4.rglob("*")):
        rel = p.relative_to(V4).as_posix()
        if p.is_file() and not any(s in rel for s in SKIP) and rel not in SKIP_FILES:
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# ------------------------------------------------------------------------------------------ context
def circuit_summary(ctx: dict) -> dict:
    """The circuit AFTER the book, as the scout sees it. Everything here is measured, not described."""
    from collections import Counter
    from ..api import dv
    c = ctx["circuit"]
    if J.is_ir(c):
        names = [g.name for g in c.gates]
        hist = Counter(names)
        tri = Counter(tuple(names[i:i + 3]) for i in range(len(names) - 2))
        return dict(label=ctx["label"], kind="Toffoli-level ir.Circuit", qubits=c.n_qubits,
                    gates=len(names), gate_histogram=dict(hist),
                    toffoli_ccz=hist.get("ccz", 0) + hist.get("ccx", 0),
                    current_t_with_book=ctx["current_t"],
                    top_gate_trigrams=[[" ".join(k), v] for k, v in tri.most_common(10)],
                    input_file="circuit.qasm (the ORIGINAL input; your rule runs on the circuit after "
                               "the book, whose statistics are the ones above)")
    names = [g for g, _, _ in c.ops]
    hist = Counter(names)
    angs = Counter(round(dv.reduce_angle(a), 8) for g, _, a in c.ops if g == "rz")
    tri = Counter(tuple(names[i:i + 3]) for i in range(len(names) - 2))
    return dict(label=ctx["label"], kind="Clifford+Rz op list, AFTER the current book",
                qubits=c.n, ops=len(names), gate_histogram=dict(hist),
                nonclifford_rotations=ctx["cost"].get("rotations"),
                explicit_t=hist.get("t", 0) + hist.get("tdg", 0), distinct_rz_angles=len(angs),
                rz_angle_histogram_top30=[[a, n] for a, n in angs.most_common(30)],
                current_t_with_book=ctx["current_t"], eps_total=ctx["eps"],
                eps_rz=ctx["cost"].get("eps_rz"),
                top_gate_trigrams=[[" ".join(k), v] for k, v in tri.most_common(10)],
                input_file="circuit.qasm (the ORIGINAL input; your rule runs on the circuit after the "
                           "book, whose statistics are the ones above)")


def make_context(ctx: dict, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    (out / "circuit_summary.json").write_text(json.dumps(circuit_summary(ctx), default=str, indent=1))
    (out / "fingerprint.json").write_text(json.dumps(ctx["fingerprint"], default=str, indent=1))
    (out / "baselines.json").write_text(json.dumps(ctx["baselines"], default=str, indent=1))
    (out / "history.json").write_text(json.dumps(ctx["history"], default=str, indent=1))
    shutil.copy(RULES / "BOOK.md", out / "BOOK.md")
    shutil.copy(PROMPTS / "api.md", out / "api.md")
    entry = next(c for c in json.loads(MANIFEST.read_text())["circuits"]
                 if c["label"] == ctx["label"])
    shutil.copy(Path("v3") / entry["input"], out / "circuit.qasm")
    refs = PROMPTS / "references"
    if refs.is_dir() and any(refs.iterdir()):
        shutil.copytree(refs, out / "references", dirs_exist_ok=True)
    return out


# ------------------------------------------------------------------------------------------ llm
def claude(role: str, prompt: str, cwd: Path, model: str, tools: str, allowed: list, log, meta: dict,
           env_extra=None) -> dict:
    cmd = ["claude", "-p", prompt, "--model", model, "--tools", tools, "--allowedTools", *allowed,
           "--permission-mode", "dontAsk", "--output-format", "json", "--no-session-persistence",
           "--max-budget-usd", str(BUDGET_USD[role])]
    env = dict(os.environ, **(env_extra or {}))
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT[role], env=env)
        out, err, rc = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        raw = e.stdout or b""
        out = raw.decode() if isinstance(raw, bytes) else raw
        err, rc = f"wall clock {TIMEOUT[role]}s exceeded", -9
    try:
        d = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    except (json.JSONDecodeError, IndexError):
        d = {}
    u = d.get("usage", {})
    row = dict(meta, time=time.time(), role=role, model=model, rc=rc,
               seconds=round(time.time() - t0, 1), is_error=d.get("is_error"), subtype=d.get("subtype"),
               terminal_reason=d.get("terminal_reason"), cost_usd=d.get("total_cost_usd"),
               num_turns=d.get("num_turns"), input_tokens=u.get("input_tokens"),
               output_tokens=u.get("output_tokens"), cache_read=u.get("cache_read_input_tokens"),
               cache_creation=u.get("cache_creation_input_tokens"),
               web_searches=u.get("server_tool_use", {}).get("web_search_requests"),
               permission_denials=[x.get("tool_name") for x in d.get("permission_denials", [])])
    log(row)
    text = d.get("result") or ""
    blob = " ".join([text if d.get("is_error") else "", err or "", "" if d else out[-2000:]])
    if (rc != 0 or d.get("is_error") or not d) and FATAL.search(blob):
        raise Fatal(f"{role}: {blob.strip()[:400]}")
    return dict(text=text, ok=rc == 0 and bool(d) and not d.get("is_error"), row=row)


def parse_card(text: str):
    for m in reversed(list(re.finditer(r"\{.*\}", text, re.S))):
        try:
            card = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(card, dict) and "name" in card:
            n = re.sub(r"\W", "_", str(card["name"])).strip("_").lower() or "rule"
            card["name"] = ("r_" + n) if n[0].isdigit() else n
            return card
    return None


def unique_name(name: str) -> str:
    taken = {p.stem for p in RULES.rglob("*.py")}
    if name not in taken:
        return name
    i = 2
    while f"{name}_{i}" in taken:
        i += 1
    return f"{name}_{i}"


# ------------------------------------------------------------------------------------------ driver
class AgentDriver:
    def __init__(self, cfg: LoopConfig, dry_run: bool = False):
        self.cfg = cfg
        self.dry = dry_run
        self.dir = RESULTS / cfg.tag
        self.dir.mkdir(parents=True, exist_ok=True)

    def log(self, row: dict) -> None:
        with open(self.dir / "tokens.jsonl", "a") as f:
            f.write(json.dumps(row, default=str) + "\n")

    def stop_requested(self) -> bool:
        return (self.dir / "STOP").exists()

    def scout(self, ctx: dict):
        if self.stop_requested():
            raise Fatal("STOP file present")
        k = len(ctx["history"]) + 1
        d = make_context(ctx, self.dir / "runs" / ctx["label"] / f"a{k}" / "context")
        if self.dry:
            print(json.dumps(dict(label=ctx["label"], attempt=k, context=str(d),
                                  current_t=ctx["current_t"], best_baseline_t=ctx["best_baseline_t"],
                                  headroom=ctx["fingerprint"]["headroom"]), indent=1))
            return None
        prompt = ((PROMPTS / "scout.md").read_text() +
                  f"\n\nTarget circuit: {ctx['label']} (eps = {ctx['eps']:g}). "
                  f"Its T-count with the current book is {ctx['current_t']}; the best baseline is "
                  f"{ctx['best_baseline']} at {ctx['best_baseline_t']}.\n")
        r = claude("scout", prompt, d, SCOUT_MODEL, "Read,WebSearch,WebFetch",
                   ["Read", "WebSearch", "WebFetch"], self.log,
                   dict(label=ctx["label"], attempt=k, step="scout"))
        card = parse_card(r["text"])
        if card:
            card["name"] = unique_name(card["name"])
            (d.parent / "card.json").write_text(json.dumps(card, indent=1) + "\n")
        return card

    def implement(self, card: dict, ctx: dict):
        if self.dry:
            return None
        k = len(ctx["history"]) + 1
        tries = ctx.get("try_", 1)
        prompt = ((PROMPTS / "implementer.md").read_text()
                  .replace("{name}", card["name"]).replace("{target}", ctx["label"]))
        prompt += "\n\nRULE CARD:\n" + json.dumps(card, indent=1)
        if ctx.get("feedback"):
            prompt += ("\n\nYour previous file was REJECTED for an IMPLEMENTATION-level reason. The idea "
                       "stands; fix the implementation. Report:\n"
                       + json.dumps(ctx["feedback"], default=str)[:8000])
        allowed = ["Read", f"Write(./v4/rules/candidates/**)", "Edit(./v4/rules/candidates/**)",
                   "Bash(.venv/bin/python -m v4.tools.test_rule:*)"]
        before = tree_digest()
        claude("implementer", prompt, REPO, IMPL_MODEL, "Read,Write,Edit,Bash", allowed, self.log,
               dict(label=ctx["label"], attempt=k, step=f"implementer_{tries}"),
               env_extra=dict(V4_ATTEMPT_ID=f"{ctx['label']}_a{k}_t{tries}"))
        after = tree_digest()
        changed = sorted({kk for kk in set(before) | set(after) if before.get(kk) != after.get(kk)})
        check_frozen()
        if changed:
            raise Fatal(f"the implementer changed files outside rules/candidates/: {changed}")
        p = CANDIDATES / f"{card['name']}.py"
        return p if p.is_file() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="run1")
    ap.add_argument("--eps", type=float, default=1e-3)
    ap.add_argument("--budget", type=int, default=60, help="global attempt budget (ONE pool)")
    ap.add_argument("--loops", type=int, default=4)
    ap.add_argument("--order", default=",".join(CIRCUIT_ORDER),
                    help="comma-separated circuit labels, or 'gain' for loop.GAIN_ORDER "
                         "(most reachable gain per unit of wall clock first)")
    ap.add_argument("--retire-after", type=int, default=2,
                    help="retire an accepted rule after this many loops with no accepted application; "
                         "0 disables retirement (book hygiene for long runs, no upside in a short one)")
    ap.add_argument("--hours", type=float, default=None,
                    help="stop cleanly after this many hours, mid-loop if need be")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    order = GAIN_ORDER if a.order == "gain" else tuple(a.order.split(","))
    cfg = LoopConfig(eps=a.eps, circuit_order=order, global_budget_attempts=a.budget,
                     max_loops=a.loops, tag=a.tag,
                     retire_after_loops=(10 ** 6 if a.retire_after == 0 else a.retire_after),
                     wall_clock_s=None if a.hours is None else a.hours * 3600)
    n = check_frozen()
    print(f"frozen files checked: {n}", flush=True)
    if a.dry_run:
        # A dry run must never share a results namespace with a real one. It did once: the dry run wrote
        # 36 stub attempts to results/<tag>/, and the live run under the same tag RESUMED from them and
        # would have exited having done no work at all.
        cfg.tag = f"{cfg.tag}_dry"
    drv = AgentDriver(cfg, a.dry_run)
    lp = Loop(cfg, drv.scout, drv.implement, drv.dir)
    try:
        out = lp.run()
    except Fatal as e:
        out = dict(stopped=str(e), loops=lp.loop, attempts_used=lp.attempts_used,
                   book=[r.name for r in lp.book])
        (drv.dir / "summary.json").write_text(json.dumps(out, default=str, indent=1) + "\n")
        print(json.dumps(out, default=str, indent=1))
        recheck_frozen()
        sys.exit(0)
    recheck_frozen()
    print(json.dumps(out, default=str, indent=1))


if __name__ == "__main__":
    main()
