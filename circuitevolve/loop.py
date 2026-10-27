"""The training loop and the test pass.

    train(arm, circuits, ask):
        for every circuit i:
            i' = apply every playbook rule to i, in order       (skip non-equivalent applications; keep worse ones; log all)
            ideas = scout(i')
            for each idea: implementer writes a rule (<= ATTEMPTS tries, verifier/metric feedback fed back)
                if it verifies AND lowers the final T-count of i': add it to the playbook, and continue from the new i'
    test(arm, circuits): prepare + apply the final playbook, no LLM calls.

Arms: L0 = TKET -> playbook -> gridsynth;  L1 = TKET -> pyzx -> playbook -> gridsynth;  L2 = TKET -> DPF -> playbook -> gridsynth.
Files: playbook/<arm>/NNN_<name>.py (accepted rules only), playbook/<arm>/log.jsonl (every application and attempt,
rejected code included), results/prepared/<arm>/<circuit>.qasm (+ .json eps used) as a cache.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import tempfile
import time

from . import agents, library, metric
from .circuit import Circuit, counts, from_qasm, load, save, to_qasm
from .verifier import Req, check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDEAS, ATTEMPTS = 5, 3
RULE_TIMEOUT, CIRCUIT_BUDGET_S = 30, 30 * 60


# ---- preparation (baseline stages before the playbook) -------------------------------------------------------------
def prepare(entry: dict, arm: str) -> tuple[Circuit, float]:
    """Load, TKET, then the arm's library stage. Cached on disk (DPF is slow). Returns (circuit, eps_used)."""
    path = os.path.join(ROOT, "results", "prepared", arm, entry["name"])
    if os.path.exists(path + ".qasm"):
        return load(path + ".qasm"), json.load(open(path + ".json"))["eps_used"]
    c, eps = library.tket(library.load(os.path.join(ROOT, entry["path"]))), 0.0
    if arm == "L1":
        c = library.pyzx_reduce(c)
    elif arm == "L2" and counts(c)["rz"]:
        from .dpf import dpf
        c, eps = dpf(c, metric.EPS_TOTAL, label=entry.get("plot_name", entry["name"]))
        assert eps <= metric.EPS_DPF, f"DPF spent {eps} > {metric.EPS_DPF}"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save(c, path + ".qasm")
    json.dump({"eps_used": eps}, open(path + ".json", "w"))
    return c, eps


# ---- running one rule (in a subprocess: hard timeout, LLM code never shares a process with the verifier) ------------
def run_rule(rule_path: str, c: Circuit, timeout: int = RULE_TIMEOUT) -> tuple[Circuit, Req]:
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "in.qasm"), os.path.join(d, "out.qasm")
        save(c, src)
        r = subprocess.run([sys.executable, "-m", "circuitevolve.loop", "--apply", rule_path, src, dst],
                           capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout)[-1500:])
        req = json.load(open(dst + ".req.json"))
        return load(dst), Req(**req)


def _worker(rule_path, src, dst):
    import importlib.util
    spec = importlib.util.spec_from_file_location("rule", rule_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out, req = mod.rewrite(load(src))
    save(out, dst)
    json.dump(dict(eps=float(req.eps), ancillas=int(req.ancillas), measure=bool(req.measure)), open(dst + ".req.json", "w"))


# ---- one application of one rule: run, verify, budget, measure ----------------------------------------------------
def apply_once(rule_path: str, c: Circuit, eps: float, eps_llm: float) -> dict:
    """Returns a log record; record['new'] holds the (circuit, eps, eps_llm) to continue from, or None if skipped."""
    t0 = time.time()
    rec = dict(rule=os.path.basename(rule_path), t_before=metric.t(c, eps), new=None)
    try:
        new, req = run_rule(rule_path, c)
    except Exception as e:                                       # includes subprocess.TimeoutExpired
        return rec | dict(verdict="error", reason=str(e)[-600:], s=round(time.time() - t0, 2))
    req = Req(eps=min(req.eps, metric.EPS_LLM - eps_llm), ancillas=req.ancillas, measure=req.measure)
    v = check(c, new, req)
    rec |= dict(verdict="ok" if v.ok else "rejected", mode=v.mode, dist=v.dist, reason=v.reason, req=req.kind)
    if v.ok and v.mode != "nochange":
        d = v.dist if req.eps > 0 else 0.0
        rec |= dict(t_after=metric.t(new, eps + d), qubits_after=new.n, new=(new, eps + d, eps_llm + d))
    return rec | dict(s=round(time.time() - t0, 2))


def playbook_rules(arm: str) -> list:
    return sorted(glob.glob(os.path.join(ROOT, "playbook", arm, "[0-9][0-9][0-9]_*.py")))


def apply_playbook(arm: str, c: Circuit, eps: float, log, circuit_name: str):
    eps_llm = 0.0
    for path in playbook_rules(arm):
        rec = apply_once(path, c, eps, eps_llm)
        if rec["new"] is not None:
            c, eps, eps_llm = rec["new"]
        log(dict(phase="apply", circuit=circuit_name) | {k: v for k, v in rec.items() if k != "new"})
    return c, eps, eps_llm


def _doc(path):
    import ast
    return (ast.get_docstring(ast.parse(open(path).read())) or "").split("\n\n")[0].replace("\n", " ")


def _logger(arm):
    os.makedirs(os.path.join(ROOT, "playbook", arm), exist_ok=True)
    f = open(os.path.join(ROOT, "playbook", arm, "log.jsonl"), "a")
    def log(rec):
        f.write(json.dumps(rec | dict(time=time.strftime("%Y-%m-%dT%H:%M:%S"))) + "\n"); f.flush()
    return log


# ---- training -----------------------------------------------------------------------------------------------------
def train(arm: str, circuits: list, ask, ideas: int = IDEAS, attempts: int = ATTEMPTS):
    log = _logger(arm)
    for entry in circuits:
        start, name = time.time(), entry["name"]
        c, eps = prepare(entry, arm)
        c, eps, eps_llm = apply_playbook(arm, c, eps, log, name)
        t_cur = metric.t(c, eps)
        log(dict(phase="start", circuit=name, t=t_cur, counts=counts(c)))
        book = [dict(name=os.path.basename(p)[4:-3], doc=_doc(p)) for p in playbook_rules(arm)]
        try:
            found = agents.scout(ask, arm, c, metric.EPS_LLM - eps_llm, book, ideas)
        except Exception as e:
            log(dict(phase="scout", circuit=name, error=str(e)[-600:])); continue
        log(dict(phase="scout", circuit=name, ideas=found))
        for idea in found:
            code, feedback = "", ""
            for k in range(attempts):
                if time.time() - start > CIRCUIT_BUDGET_S:
                    break
                try:
                    code = agents.implement(ask, arm, c, metric.EPS_LLM - eps_llm, book, idea, feedback, code)
                except Exception as e:
                    feedback = f"implementer error: {e}"
                    log(dict(phase="attempt", circuit=name, idea=idea["name"], attempt=k, accepted=False,
                             verdict="implementer_error", reason=str(e)[-600:]))
                    continue
                os.makedirs(os.path.join(ROOT, ".cache", "candidates"), exist_ok=True)
                with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=os.path.join(ROOT, ".cache", "candidates")) as f:
                    f.write(code)
                rec = apply_once(f.name, c, eps, eps_llm)
                accepted = rec["new"] is not None and rec["t_after"] < t_cur
                if accepted:
                    n = len(playbook_rules(arm)) + 1
                    dest = os.path.join(ROOT, "playbook", arm, f"{n:03d}_{_safe(idea['name'])}.py")
                    os.replace(f.name, dest)
                    c, eps, eps_llm = rec["new"]
                    t_cur = rec["t_after"]
                    book.append(dict(name=_safe(idea["name"]), doc=_doc(dest)))
                else:
                    os.unlink(f.name)
                    feedback = (rec.get("reason") or "") if rec["verdict"] != "ok" else (
                        f"verified (mode {rec.get('mode')}) but final T-count {rec.get('t_after', rec['t_before'])} "
                        f"is not below {t_cur}" + (" - the rule changed nothing" if rec.get("mode") == "nochange" else ""))
                log(dict(phase="attempt", circuit=name, idea=idea["name"], attempt=k, accepted=accepted, code=code)
                    | {k2: v for k2, v in rec.items() if k2 != "new"})
                if accepted:
                    break
        log(dict(phase="end", circuit=name, t=t_cur, s=round(time.time() - start, 1)))


def _safe(s):
    return "".join(ch if ch.isalnum() else "_" for ch in s.lower())[:50]


# ---- test (no LLM) ------------------------------------------------------------------------------------------------
def test(arm: str, circuits: list) -> list:
    log, rows = _logger(arm), []
    for entry in circuits:
        start = time.time()
        c0, eps0 = prepare(entry, arm)
        c, eps, _ = apply_playbook(arm, c0, eps0, lambda r: log(r | dict(split="test")), entry["name"])
        v = check(c0, c, Req(eps=metric.EPS_LLM, ancillas=c.n - c0.n, measure=True))   # end-to-end re-check
        rows.append(dict(circuit=entry.get("plot_name", entry["name"]), arm=arm, **metric.final(c, eps),
                         t_prepared=metric.t(c0, eps0), e2e_check=("ok" if v.ok else "too large" if v.mode == "refused" else "FAILED"),
                         e2e_mode=v.mode, e2e_reason=v.reason, s=round(time.time() - start, 1)))
    return rows


if __name__ == "__main__":
    if sys.argv[1] == "--apply":
        _worker(*sys.argv[2:5])
