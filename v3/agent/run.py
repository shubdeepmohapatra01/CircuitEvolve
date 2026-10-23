"""P2 agent loop: scout -> implementer -> admit, the only place an LLM is called. DV only, eps 1e-3.

    .venv/bin/python -m v3.agent.run [--max-attempts N]   # start or RESUME (state in v3/results/p2/state.json)
    touch v3/results/p2/STOP                         # stop cleanly after the current step

Schedule: round-robin over PLAN (priority order): attempt 1 on every circuit, then attempt 2 on each circuit with
budget left, and so on until the per-circuit budgets are used up.
One attempt on a circuit:
  scout (agent CLI `$V3_AGENT_CLI -p`, model SCOUT_MODEL, tools Read / WebSearch / WebFetch, cwd = a per-attempt context folder, so
  Read only reaches that folder) -> one JSON rule card;
  implementer (agent CLI, model IMPL_MODEL, tools Read / Write / Edit / Bash; writes allowed only under
  v3/rules/candidates/, Bash only `.venv/bin/python -m v3.tools.test_rule`, permission mode dontAsk = everything
  else denied) -> v3/rules/candidates/<name>.py;
  harness admission (tools/admit.py, full DV suite at eps 1e-3, 300 s per circuit).
  On reject: implementation-level (static / invalid RULE / exception / verification failure / runtime / no file)
  -> one more implementer try with the failure JSON; idea-level (never fires / no improvement / IDEA_FAILS) -> the
  failure goes back to the scout once (new card, one implementer try). Then the attempt ends.
Guards: FROZEN.sha256 checked and a hash snapshot of v3/ (outside candidates / results / caches) compared before
and after every implementer call; any change outside candidates stops P2.
Results are written after EVERY attempt: results/p2/attempts.jsonl, tokens.jsonl (one line per LLM call, with
tokens and cost from --output-format json), state.json; after an admission the book is re-run on all DV circuits
(results/p2/ours.jsonl); then the report (figures + SUMMARY.md) is regenerated.
A usage-limit / credential / auth error stops the run cleanly: the remaining circuits are marked "not run".
A call stopped by --max-budget-usd aborts only its attempt (decision aborted_budget, no retries, any candidate
file set aside unadmitted).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

from ..judge import dv as J
from ..judge.frozen import check_frozen
from ..paths import BASELINES_CSV, DV_PY, REPO, RESULTS, RULES, V3

# The agent CLI and the two model ids are configured by environment variables (see README).
AGENT_CLI = os.environ.get("V3_AGENT_CLI", "")
SCOUT_MODEL = os.environ.get("V3_SCOUT_MODEL", "")
IMPL_MODEL = os.environ.get("V3_IMPL_MODEL", "")
EPS = 1e-3
PLAN = [("qpe_8", 5), ("hhl_8", 5), ("adder_8", 4), ("mult_4", 4), ("mcx_10", 4), ("adder_6", 3),
        ("modred_21", 3), ("qft_8", 3), ("qae_13", 3), ("tfim_6", 2)]
P2 = RESULTS / "p2"
STATE = P2 / "state.json"
STOP = P2 / "STOP"
PROMPTS = V3 / "agent" / "prompts"
TIMEOUT = dict(scout=1200, implementer=2700, admit=4200)
BUDGET_USD = dict(scout=4.0, implementer=8.0)
FATAL = re.compile(r"usage limit|limit reached|rate.?limit|hit your limit|credit balance|insufficient (credit|funds)|"
                   r"billing|authenticat|not logged in|please (run )?/?login|invalid api key|unauthori[sz]ed|"
                   r"\b401\b|\b403\b|oauth|token (has )?expired|subscription", re.I)
IMPL_LEVEL = ("static check", "invalid RULE", "exception", "verification failed", "runtime limit", "no candidate file")


class Fatal(RuntimeError):
    """Usage-limit / credential error: stop the whole run cleanly."""


class BudgetAbort(RuntimeError):
    """A call stopped by --max-budget-usd (subtype error_max_budget_usd / terminal_reason budget_exhausted): the
    attempt is recorded as aborted; it does NOT enter the implementation- or idea-level retry path."""


# ------------------------------------------------------------------------------------------------ io helpers
def now() -> float:
    return time.time()


def append(name: str, row: dict):
    P2.mkdir(parents=True, exist_ok=True)
    with open(P2 / name, "a") as f:
        f.write(json.dumps(row, default=str) + "\n")


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return dict(plan=PLAN, done={l: 0 for l, _ in PLAN}, status={l: "pending" for l, _ in PLAN}, stopped=None,
                started=now())


def save_state(st: dict):
    P2.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1))
    tmp.replace(STATE)


def tree_digest() -> dict:
    """sha256 of every file under v3/ except candidates, results, caches, figures, bytecode."""
    skip = ("rules/candidates/", "results/", ".cache/", "report/figures/", "__pycache__")
    out = {}
    for p in sorted(V3.rglob("*")):
        rel = p.relative_to(V3).as_posix()
        if p.is_file() and not any(s in rel + ("/" if p.is_dir() else "") for s in skip):
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# ------------------------------------------------------------------------------------------------ context
def circuit_summary(label: str, current_t: dict) -> dict:
    c = J.load(label)
    m = J.manifest_entry(label)
    if J.is_ir(c):
        names = [g.name for g in c.gates]
        hist = Counter(names)
        tri = Counter(tuple(names[i:i + 3]) for i in range(len(names) - 2))
        return dict(label=label, family=m["family"], kind="Toffoli-level ir.Circuit", qubits=c.n_qubits,
                    gates=len(names), gate_histogram=dict(hist), toffoli_ccz=hist.get("ccz", 0) + hist.get("ccx", 0),
                    t_count_naive_7_per_toffoli=J.measure(c)["t_count"], current_t_with_book=current_t.get(label),
                    top_gate_trigrams=[[" ".join(k), v] for k, v in tri.most_common(10)],
                    input_file="circuit.qasm (OpenQASM 2, `gate ccz` = h-ccx-h)")
    names = [g for g, _, _ in c.ops]
    hist = Counter(names)
    angs = Counter(round(a, 6) for g, _, a in c.ops if g == "rz")
    tri = Counter(tuple(names[i:i + 3]) for i in range(len(names) - 2))
    meas = J.measure(c, EPS)
    return dict(label=label, family=m["family"], kind="Clifford+Rz op list (TKET FullPeepholeOptimise output)",
                qubits=c.n, ops=len(names), gate_histogram=dict(hist), nonclifford_rotations=meas["rotations"],
                explicit_t=hist.get("t", 0) + hist.get("tdg", 0), distinct_rz_angles=len(angs),
                rz_angle_histogram_top30=[[a, n] for a, n in angs.most_common(30)],
                t_count_input=meas["t_count"], eps_total=EPS, eps_rz_input=meas["eps_rz"],
                current_t_with_book=current_t.get(label),
                top_gate_trigrams=[[" ".join(k), v] for k, v in tri.most_common(10)],
                input_file="circuit.qasm (OpenQASM 2, rz angles in radians)")


def baselines_for(label: str) -> dict:
    import csv
    rows = [r for r in csv.DictReader(open(BASELINES_CSV)) if r["label"] == label and r["eps"] and
            float(r["eps"]) in (EPS, 0.0)]
    return {r["method"]: dict(t_count=int(r["t_count"]), qubits=int(r["qubits"])) for r in rows}


def history(label: str) -> list:
    """Earlier attempts on `label`: cards, decision, reason, scout's estimated gain vs measured gain, limitation note.
    Annotation lines (type 'annotation', appended later for an attempt) override estimate / measured / limitation."""
    f = P2 / "attempts.jsonl"
    if not f.exists():
        return []
    out, ann = [], {}
    for line in f.read_text().splitlines():
        r = json.loads(line)
        if r.get("label") != label:
            continue
        if r.get("type") == "annotation":
            ann.setdefault(r["attempt"], {}).update({k: r[k] for k in ("estimate", "measured", "limitation", "voided",
                                                                       "note") if k in r})
            continue
        out.append(dict(attempt=r["attempt"], cards=[s.get("card") for s in r.get("steps", []) if s.get("card")],
                        decision=r.get("decision"), reason=r.get("reason"), admitted=r.get("admitted"),
                        estimate=r.get("estimate"), measured=r.get("measured"), limitation=r.get("limitation")))
    for h in out:
        h.update(ann.get(h["attempt"], {}))
    return out


def gain_record(label: str, card: dict, dec: dict, impl_text: str) -> dict:
    """Scout's estimate next to the measured gain on the target (from the admission report), plus LIMITATION."""
    est = card.get("expected_t_saving_on_target") if card else None
    rows = [r for r in (dec.get("report") or {}).get("circuits", []) if r.get("label") == label]
    meas = None
    if rows and rows[0].get("cost_before") is not None:
        r = rows[0]
        meas = dict(t_before=r["cost_before"], t_after=r["cost_after"], t_saving=r["cost_before"] - r["cost_after"],
                    fired=r["fired"], applications=r.get("accepted"))
    lim = re.findall(r"^LIMITATION:\s*(.+)$", impl_text or "", re.M)
    return dict(estimate=dict(t_saving=est, text=(card or {}).get("expected_effect", "")[:400]), measured=meas,
                limitation=lim[-1].strip() if lim else None)


def make_context(label: str, k: int, current_t: dict) -> Path:
    d = P2 / "runs" / label / f"a{k}" / "context"
    d.mkdir(parents=True, exist_ok=True)
    (d / "circuit_summary.json").write_text(json.dumps(circuit_summary(label, current_t), indent=1))
    (d / "baselines.json").write_text(json.dumps(baselines_for(label), indent=1))
    (d / "history.json").write_text(json.dumps(history(label), indent=1))
    shutil.copy(RULES / "BOOK.md", d / "BOOK.md")
    shutil.copy(V3 / "agent" / "api.md", d / "api.md")
    shutil.copy(V3 / J.manifest_entry(label)["input"], d / "circuit.qasm")
    return d


# ------------------------------------------------------------------------------------------------ LLM calls
def agent_call(role: str, prompt: str, cwd: Path, model: str, tools: str, allowed: list, label: str, k: int,
           step: str, env_extra=None) -> dict:
    cmd = [AGENT_CLI, "-p", prompt, "--model", model, "--tools", tools, "--allowedTools", *allowed,
           "--permission-mode", "dontAsk", "--output-format", "json", "--no-session-persistence",
           "--max-budget-usd", str(BUDGET_USD[role])]
    import os
    env = dict(os.environ, **(env_extra or {}))
    t0 = now()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT[role], env=env)
        out, err, rc = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out, err, rc = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout", -9
    try:
        d = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    except (json.JSONDecodeError, IndexError):
        d = {}
    usage = d.get("usage", {})
    row = dict(time=now(), label=label, attempt=k, step=step, role=role, model=model, rc=rc,
               seconds=round(now() - t0, 1), is_error=d.get("is_error"), subtype=d.get("subtype"),
               terminal_reason=d.get("terminal_reason"), cost_usd=d.get("total_cost_usd"), num_turns=d.get("num_turns"),
               errors=d.get("errors"),
               input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
               cache_read_tokens=usage.get("cache_read_input_tokens"),
               cache_creation_tokens=usage.get("cache_creation_input_tokens"),
               web_search_requests=usage.get("server_tool_use", {}).get("web_search_requests"),
               permission_denials=[x.get("tool_name") for x in d.get("permission_denials", [])],
               model_usage=d.get("modelUsage"))
    append("tokens.jsonl", row)
    text = d.get("result") or ""
    if d.get("subtype") == "error_max_budget_usd" or d.get("terminal_reason") == "budget_exhausted":
        raise BudgetAbort(f"{role} call stopped by --max-budget-usd {BUDGET_USD[role]} "
                          f"(cost {d.get('total_cost_usd')}, turns {d.get('num_turns')})")
    blob = " ".join([text if d.get("is_error") else "", err or "", "" if d else out[-2000:]])
    if (rc != 0 or d.get("is_error") or not d) and FATAL.search(blob):
        raise Fatal(f"{role} call: {blob.strip()[:400]}")
    return dict(text=text, row=row, ok=rc == 0 and bool(d) and not d.get("is_error"), stderr=(err or "")[-1500:])


def parse_card(text: str):
    for m in reversed(list(re.finditer(r"\{.*\}", text, re.S))):
        try:
            card = json.loads(m.group(0))
            if isinstance(card, dict) and "name" in card:
                card["name"] = re.sub(r"\W", "_", str(card["name"])).strip("_").lower() or "rule"
                if card["name"][0].isdigit():
                    card["name"] = "r_" + card["name"]
                return card
        except json.JSONDecodeError:
            continue
    return None


def unique_name(name: str) -> str:
    taken = {p.stem for p in RULES.rglob("*.py")}
    if name not in taken:
        return name
    i = 2
    while f"{name}_{i}" in taken:
        i += 1
    return f"{name}_{i}"


def scout(ctx: Path, label: str, k: int, feedback=None) -> tuple:
    prompt = (PROMPTS / "scout.md").read_text() + f"\n\nTarget circuit: {label} (eps = {EPS:g}).\n"
    if feedback:
        prompt += ("\nYour previous card for this attempt FAILED at the idea level. Failure report:\n"
                   + json.dumps(feedback, default=str)[:6000] + "\nPropose a DIFFERENT idea.\n")
    r = agent_call("scout", prompt, ctx, SCOUT_MODEL, "Read,WebSearch,WebFetch", ["Read", "WebSearch", "WebFetch"],
               label, k, "scout" + ("_retry" if feedback else ""))
    return parse_card(r["text"]), r


def implement(card: dict, label: str, k: int, step: str, failure=None) -> tuple:
    prompt = (PROMPTS / "implementer.md").read_text().replace("{name}", card["name"]).replace("{target}", label)
    prompt += "\n\nRULE CARD:\n" + json.dumps(card, indent=1)
    if failure:
        prompt += ("\n\nThe harness admission REJECTED your previous file for an implementation-level reason. The "
                   "file is back at v3/rules/candidates/" + card["name"] + ".py. Fix the implementation (not the "
                   "idea). Admission report:\n" + json.dumps(failure, default=str)[:8000])
    allowed = ["Read", "Write(./v3/rules/candidates/**)", "Edit(./v3/rules/candidates/**)",
               "Bash(.venv/bin/python -m v3.tools.test_rule:*)"]
    before = tree_digest()
    r = agent_call("implementer", prompt, REPO, IMPL_MODEL, "Read,Write,Edit,Bash", allowed, label, k, step,
               env_extra=dict(V3_ATTEMPT_ID=f"{label}_a{k}_{step}"))
    after = tree_digest()
    changed = sorted(set(before.items()) ^ set(after.items()))
    check_frozen()
    if changed:
        raise RuntimeError(f"implementer changed files outside rules/candidates/: {sorted({c[0] for c in changed})}")
    return r


def admit(path: Path, label: str, k: int, step: str) -> dict:
    t0 = now()
    try:
        p = subprocess.run([str(DV_PY), "-m", "v3.tools.admit", str(path), "--origin", f"LLM (P2, {label} a{k})",
                            "--limit", "300", "--eps", str(EPS)], cwd=REPO, capture_output=True, text=True,
                           timeout=TIMEOUT["admit"])
        res = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 and p.stdout.strip() else \
            dict(decision="error", reason=f"admit exit {p.returncode}: {p.stderr[-1500:]}")
    except subprocess.TimeoutExpired:
        dest = RULES / "rejected" / path.name
        if path.exists():
            shutil.move(str(path), dest)
        res = dict(decision="reject", reason=f"runtime limit: admission exceeded {TIMEOUT['admit']} s",
                   moved_to=str(dest))
    res["seconds"] = round(now() - t0, 1)
    rep = None
    for line in reversed((RESULTS / "events.jsonl").read_text().splitlines()):
        e = json.loads(line)
        if e.get("event") == "admission" and Path(e.get("candidate", "")).name == path.name:
            rep = e
            break
    res["report"] = rep
    return res


def level(dec: dict, impl_text: str) -> str:
    if "IDEA_FAILS" in impl_text:
        return "idea"
    if dec["decision"] == "never_fires" or "lowers the primary metric on no circuit" in dec.get("reason", ""):
        return "idea"
    return "implementation" if any(s in dec.get("reason", "") for s in IMPL_LEVEL) or dec["decision"] == "error" \
        else "idea"


# ------------------------------------------------------------------------------------------------ attempt
def clear_candidates(dest: Path):
    for p in (RULES / "candidates").glob("*.py"):
        dest.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), dest / p.name)


def one_try(card, label, k, step, steps, failure=None):
    """Implementer -> admission for one card. Returns the admission dict (or a synthetic failure)."""
    path = RULES / "candidates" / f"{card['name']}.py"
    r = implement(card, label, k, step, failure)
    s = dict(step=step, card=card, impl_ok=r["ok"], impl_tail=r["text"][-1500:], impl_cost=r["row"]["cost_usd"],
             impl_turns=r["row"]["num_turns"], impl_text=r["text"])
    if not path.exists():
        dec = dict(decision="reject", reason="no candidate file written by the implementer")
    else:
        dec = admit(path, label, k, step)
    s.update(decision=dec["decision"], reason=dec.get("reason"), moved_to=dec.get("moved_to"),
             level=None if dec["decision"] == "admit" else level(dec, r["text"]),
             supersedes=dec.get("supersedes"), **gain_record(label, card, dec, r["text"]))
    steps.append(s)
    clear_candidates(P2 / "runs" / label / f"a{k}" / "stray")
    return dec, s


def attempt(label: str, k: int, current_t: dict) -> dict:
    steps = []
    try:
        return _attempt(label, k, current_t, steps)
    except BudgetAbort as e:
        clear_candidates(P2 / "runs" / label / f"a{k}" / "aborted_candidates")     # never admitted
        return dict(label=label, attempt=k, decision="aborted_budget", reason=str(e), steps=steps,
                    test_rule_calls=test_rule_calls(label, k))


def test_rule_calls(label: str, k: int) -> dict:
    f = RESULTS / "test_rule_calls.json"
    if not f.exists():
        return {}
    pre = f"{label}_a{k}_"
    return {key[len(pre):]: n for key, n in json.loads(f.read_text()).items() if key.startswith(pre)}


def _attempt(label: str, k: int, current_t: dict, steps: list) -> dict:
    t0 = now()
    ctx = make_context(label, k, current_t)
    rec = dict(label=label, attempt=k, started=t0)
    card, sr = scout(ctx, label, k)
    steps.append(dict(step="scout", card=card, scout_ok=sr["ok"], scout_cost=sr["row"]["cost_usd"],
                      scout_tail=None if card else sr["text"][-2000:]))
    if not card:
        rec.update(decision="scout_failed", reason="no valid JSON rule card", steps=steps)
        return rec
    card["name"] = unique_name(card["name"])
    dec, s = one_try(card, label, k, "implement", steps)
    if dec["decision"] != "admit" and s["level"] == "implementation":
        moved = Path(dec.get("moved_to") or "")
        src = V3 / moved if moved and not moved.is_absolute() else moved
        if src and src.is_file():
            shutil.copy(src, RULES / "candidates" / f"{card['name']}.py")
            src.rename(src.with_name(src.stem + ".try1.py"))
        dec, s = one_try(card, label, k, "implement_retry", steps, failure=dec.get("report") or dec)
    elif dec["decision"] != "admit":
        card2, sr2 = scout(ctx, label, k, feedback=dict(card=card, decision=dec["decision"], reason=dec.get("reason"),
                                                         implementer=s.get("impl_tail")))
        steps.append(dict(step="scout_retry", card=card2, scout_ok=sr2["ok"], scout_cost=sr2["row"]["cost_usd"]))
        if card2:
            card2["name"] = unique_name(card2["name"])
            dec, s = one_try(card2, label, k, "implement_after_scout_retry", steps)
    for x in steps:
        x.pop("impl_text", None)
    rec.update(decision=dec["decision"], reason=dec.get("reason"), steps=steps,
               admitted=s["card"]["name"] if dec["decision"] == "admit" else None, seconds=round(now() - t0, 1),
               test_rule_calls=test_rule_calls(label, k), supersedes=dec.get("supersedes"),
               estimate=s.get("estimate"), measured=s.get("measured"), limitation=s.get("limitation"))
    return rec


# ------------------------------------------------------------------------------------------------ main
def refresh_ours(reason: str) -> dict:
    p = subprocess.run([str(DV_PY), "-m", "v3.report.ours", "--reason", reason], cwd=REPO, capture_output=True,
                       text=True, timeout=7200)
    if p.returncode != 0:
        append("errors.jsonl", dict(time=now(), where="ours", stderr=p.stderr[-3000:]))
    return current_ours()


def current_ours() -> dict:
    f = P2 / "ours.jsonl"
    out = {}
    if f.exists():
        for line in f.read_text().splitlines():
            r = json.loads(line)
            out[r["label"]] = r["t_count"]
    return out


def report():
    p = subprocess.run([str(DV_PY), "-m", "v3.report.p2_report"], cwd=REPO, capture_output=True, text=True,
                       timeout=1800)
    if p.returncode != 0:
        append("errors.jsonl", dict(time=now(), where="report", stderr=p.stderr[-3000:]))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-attempts", type=int, default=None, help="stop cleanly after this many attempts")
    args = ap.parse_args()
    missing = [v for v, x in (("V3_AGENT_CLI", AGENT_CLI), ("V3_SCOUT_MODEL", SCOUT_MODEL),
                              ("V3_IMPL_MODEL", IMPL_MODEL)) if not x]
    if missing:
        sys.exit(f"set {', '.join(missing)} (agent CLI command and the scout / implementer model ids)")
    check_frozen()
    st = load_state()
    st["stopped"] = None
    st.setdefault("resumes", []).append(now())
    budgets = dict(st["plan"])
    for label, budget in st["plan"]:                # resume: everything with budget left is pending again
        if st["done"][label] < budget:
            st["status"][label] = "pending"
    save_state(st)
    clear_candidates(P2 / "stale_candidates")
    if not (P2 / "ours.jsonl").exists():
        refresh_ours("P2 start (book as is)")
    report()
    n_this_run = 0
    try:
        # round-robin: attempt 1 for every circuit in priority order, then attempt 2 where budget is left, ...
        for rnd in range(1, max(budgets.values()) + 1):
            for label, budget in st["plan"]:
                if st["done"][label] >= budget or st["done"][label] >= rnd:
                    continue
                if STOP.exists():
                    raise KeyboardInterrupt("STOP file")
                if args.max_attempts is not None and n_this_run >= args.max_attempts:
                    raise KeyboardInterrupt(f"--max-attempts {args.max_attempts} reached")
                k = st["done"][label] + 1
                st["status"][label] = "running"
                save_state(st)
                try:
                    rec = attempt(label, k, current_ours())
                except Fatal as e:
                    append("attempts.jsonl", dict(label=label, attempt=k, decision="aborted",
                                                  reason=f"usage-limit / credential error: {e}", finished=now(),
                                                  test_rule_calls=test_rule_calls(label, k)))
                    st["done"][label] = k
                    raise
                except Exception as e:  # noqa: BLE001  (record and continue with the next attempt)
                    rec = dict(label=label, attempt=k, decision="harness_error", reason=f"{type(e).__name__}: {e}",
                               traceback=traceback.format_exc()[-3000:])
                    if "outside rules/candidates" in str(e):
                        append("attempts.jsonl", dict(rec, finished=now()))
                        st["done"][label] = k
                        raise
                rec["finished"] = now()
                append("attempts.jsonl", rec)
                st["done"][label] = k
                st["status"][label] = "done" if k >= budget else "in progress"
                save_state(st)
                n_this_run += 1
                if rec.get("decision") == "admit":
                    refresh_ours(f"admitted {rec.get('admitted')}")
                report()
    except Fatal as e:
        st["stopped"] = f"usage-limit / credential error: {e}"
    except KeyboardInterrupt as e:
        st["stopped"] = f"stopped: {e}"
    except Exception as e:  # noqa: BLE001
        st["stopped"] = f"harness stop: {type(e).__name__}: {e}"
    finally:
        for label, budget in st["plan"]:
            d = st["done"][label]
            st["status"][label] = "done" if d >= budget else ("not run" if d == 0 else f"partial ({d}/{budget})")
        st["finished"] = now()
        save_state(st)
        report()
        print(json.dumps(dict(stopped=st["stopped"], status=st["status"])))


if __name__ == "__main__":
    sys.exit(main())
