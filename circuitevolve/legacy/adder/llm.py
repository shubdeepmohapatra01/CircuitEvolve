"""LLM proposer for SliceProgram search (P4).

The LLM is a mutation operator: it sees a parent program, its score, a few archive elites and recent
verifier rejections, and returns complete FWD/TOP/BWD templates. Responses are parsed as literal data
(ast, never exec), then go through exactly the same Evaluator as the classical arm.

Backends are plain callables `complete(list[str]) -> list[str | Exception]`:
  * make_cli_backend()  - `claude -p` subprocess, run in an EMPTY temp dir (so the agent cannot read
                          this repository, which contains the reference answer), with explicit checks
                          for the silent-failure modes seen in practice (exit 0 + is_error=true), stdout
                          diagnostics on exit != 0, configurable timeout and bounded retries.
  * make_api_backend()  - wraps a batch LLM callable with the `host.llm` signature
                          (`llm(list[dict], max_concurrency=...) -> list[dict]`); thinking disabled by
                          default; error dicts and empty text are errors; bounded retries with backoff.
                          The callable is passed in: this module never imports `host`.
  * any other callable  - e.g. a wrapper around a hosted model API.
A backend may carry a `stats` Counter (calls/ok/errors/retries/tokens); llm_search reports its delta.

Blinded mode renames every identifier that could cue recall of the literature (adder, carry, gadget
names, role names); the mathematical task is unchanged.
"""
from __future__ import annotations

import ast
import json
import random
import re
import subprocess
import tempfile
import time
from collections import Counter, deque

from .evolve import TIERS, Evaluator, mutate
from .slice import ROLES, SliceProgram, to_source

# --------------------------------------------------------------------------------------------- naming
OPEN_NAMES = {"roles": {r: r for r in ROLES}, "gates": {}}
# Words that would cue recall of the literature; a blinded playbook refuses rules containing them.
CUE_WORDS = ("adder", "addition", "carry", "gidney", "cuccaro", "ripple", "and_compute", "and_uncompute",
             "temporary", "toffoli", "majority", "maj", "uma")
BLIND_NAMES = {
    "roles": {"a": "x", "b": "y", "pa": "xp", "pc": "wp", "cout": "w", "z": "o"},
    "gates": {"and_compute": "g4", "and_uncompute": "g0"},
}


def _rename_prog(prog: SliceProgram, names) -> SliceProgram:
    R, Gm = names["roles"], names["gates"]
    f = lambda t: tuple((Gm.get(n, n), tuple(R[r] for r in roles), c, l) for n, roles, c, l in t)
    return SliceProgram(f(prog.fwd), f(prog.top), f(prog.bwd))


# --------------------------------------------------------------------------------------------- prompt
_GATE_DOC = {
    "x": "x(q): NOT", "z": "z(q)", "h": "h(q): Hadamard", "s": "s(q): phase pi/2", "sdg": "sdg(q)",
    "t": "t(q): phase pi/4 (cost 1 T)", "tdg": "tdg(q): phase -pi/4 (cost 1 T)",
    "cx": "cx(c, t): CNOT", "cz": "cz(p, q)",
    "ccx": "ccx(p, q, t): Toffoli, t ^= p&q (cost 7 T)",
    "measure": "measure(q, label='m'): Z-basis measurement into classical bit 'm' (no reset)",
    "and_compute": "and_compute(p, q, t): REQUIRES t = |0>; sets t = p&q (cost 4 T)",
    "and_uncompute": "and_uncompute(p, q, t): REQUIRES t = p&q; resets t to |0> using one measurement "
                     "and a classically controlled CZ (cost 0 T)",
}
_BLIND_GATE_DOC = dict(_GATE_DOC, and_compute=None, and_uncompute=None)
_BLIND_GATE_DOC["g4"] = "g4(p, q, t): REQUIRES t = |0>; sets t = p&q (cost 4 T)"
_BLIND_GATE_DOC["g0"] = ("g0(p, q, t): REQUIRES t = p&q; resets t to |0> using one measurement and a "
                         "classically controlled phase fix-up (cost 0 T)")


def _task_text(blinded: bool) -> str:
    if not blinded:
        return ("Design an n-bit in-place quantum ADDER with the fewest T gates. Registers: a (n qubits), "
                "b (n qubits), carry-out z (1 qubit, starts |0>). Required map: a -> a, b -> (a+b) mod 2^n, "
                "z -> carry out. Every other qubit is a clean ancilla: it starts in |0> and must end in |0>. "
                "Measurements with classically controlled corrections are allowed.")
    return ("Design a reversible quantum circuit family, parameterised by n, with the fewest T gates. "
            "Registers: x (n qubits), y (n qubits), o (1 qubit, starts |0>). Required map on basis states: "
            "x -> x, y -> (x+y) mod 2^n, o -> floor((x+y) / 2^n); it must act linearly on superpositions "
            "(no input-dependent phases). Every other qubit starts in |0> and must end in |0>. "
            "Measurements with classically controlled corrections are allowed.")


def _repr_text(blinded: bool, vocab) -> str:
    R = BLIND_NAMES["roles"] if blinded else OPEN_NAMES["roles"]
    Gm = BLIND_NAMES["gates"] if blinded else {}
    doc = _BLIND_GATE_DOC if blinded else _GATE_DOC
    gates = "\n".join(f"  - {doc[Gm.get(g, g)]}" for g in sorted(vocab))
    return f"""A program is three gate templates applied slice by slice, for bit positions i = 0..n-1:
    for i in 0..n-1:   apply FWD at slice i
    once at i = n-1:   apply TOP
    for i in n-1..0:   apply BWD at slice i
Wire roles inside a template, at slice i:
  {R['a']}, {R['b']}   = bit i of the two n-qubit registers
  {R['pa']}       = bit i-1 of register {R['a']} (at i = 0: a dedicated clean ancilla, shared with {R['pc']})
  {R['pc']}       = work wire of slice i-1 (at i = 0: the same dedicated clean ancilla)
  {R['cout']}       = work wire of slice i (a clean ancilla per slice; it is wire {R['pc']} of slice i+1)
  {R['z']}       = the single output qubit
Write each gate as G('gate', 'role', ...). Classical control: G('measure', 'role', label='m') then
G('cz', 'r1', 'r2', cond='m') applies only if m = 1; labels are local to one template instance.
Allowed gates:
{gates}
Scoring (lexicographic, lower is better): T gates per bit (asymptotic slope), then total T-count at
n = 8, then qubits, then T-depth, then program size. A program scores only if an exact verifier accepts
it for n = 1..4 exhaustively (all inputs, every measurement branch, exact amplitudes) and n = 8 on
sampled inputs. Global phase is ignored; relative phase between inputs is not."""


_FORMAT_RULES = ("Output format (strict): a ```python block must contain ONE final program and nothing else - "
                 "only the three assignments FWD = (...), TOP = (...), BWD = (...) built from G('gate', 'role', ...) "
                 "with string-literal arguments. If you trace a circuit, draw a diagram or derive an identity, write "
                 "it as plain text outside code blocks, never inside a ```python block. Write gate names exactly as "
                 "listed, in ASCII ('tdg', 'sdg'; no dagger symbols).")


def build_prompt(parent, parent_fit, elites, failures, blinded, tier, k, feedback=True, rules_text="",
                 format_rules=True) -> str:
    """format_rules=False reproduces the P4 prompt exactly (used for before/after parse measurements)."""
    vocab = TIERS[tier]
    names = BLIND_NAMES if blinded else OPEN_NAMES
    show = lambda p: to_source(_rename_prog(p, names))
    fit_txt = lambda f: f"T per bit = {f[0]:g}, T-count at n=8 = {f[1]}, qubits at n=8 = {f[2]}"
    parts = [_task_text(blinded), "", _repr_text(blinded, vocab), ""]
    if rules_text:
        parts += [rules_text, ""]
    parts += [f"Current program ({fit_txt(parent_fit)}):", "```python", show(parent).rstrip(), "```"]
    if feedback and elites:
        parts += ["", "Other accepted programs from the archive:"]
        for f, p in elites:
            parts += [f"# {fit_txt(f)}", "```python", show(p).rstrip(), "```"]
    if feedback and failures:
        parts += ["", "Recently rejected proposals and the verifier's reason:"]
        for p, reason in failures:
            parts += [f"# rejected: {reason}", "```python", show(p).rstrip(), "```"]
    parts += ["", f"Propose {k} different programs that you expect to score better than the current one. "
              "Larger structural changes are allowed (new use of work wires, different recurrences). For each, "
              "give one sentence of reasoning, then one ```python block defining FWD, TOP and BWD as tuples "
              "of G(...) calls. Use only the listed gates and roles."]
    if format_rules:
        parts += ["", _FORMAT_RULES]
    return "\n".join(parts)


# --------------------------------------------------------------------------------------------- parse
class ParseError(ValueError):
    pass


def _lit(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    raise ParseError("non-literal argument")


_PY_LANGS = ("", "python", "py", "python3")
_DEFINES = re.compile(r"^[ \t]*(FWD|TOP|BWD)[ \t]*=", re.M | re.I)
_DAGGER_SUFFIXES = ("\u2020", "^\u2020", "dg", "dag", "_dag", "dagger", "_dagger", "^dagger")
_GATE_ALIASES = {**{b + s: b + "dg" for b in ("t", "s") for s in _DAGGER_SUFFIXES},
                 "cnot": "cx", "toffoli": "ccx"}


def _code_blocks(text: str) -> list:
    """Fenced blocks as (lang, body), pairing fence lines in order. An unclosed final block is dropped
    (as before). Line-based pairing avoids the old regex's misalignment, where a ```text fence made the
    *closing* fence of the previous block open a bogus block spanning prose."""
    blocks, cur, lang = [], None, ""
    for ln in text.split("\n"):
        s = ln.strip()
        if s.startswith("```"):
            if cur is None:
                lang, cur = s[3:].strip().lower(), []
            else:
                blocks.append((lang, "\n".join(cur) + "\n"))
                cur = None
        elif cur is not None:
            cur.append(ln)
    return blocks


def normalise_gate(name: str, known) -> str:
    """Map an unambiguous alias ('T\u2020', 'Tdg', 'tdag', 'S^\u2020', 'CNOT', 'H') to its canonical name.
    Only applied when the result is a known gate; anything else is returned unchanged (the verifier
    rejects unknown gates at L0)."""
    if name in known:
        return name
    s = name.strip().lower().replace(" ", "")
    s = _GATE_ALIASES.get(s, s)
    return s if s in known else name


def parse_programs(text: str, blinded: bool, max_programs: int = 8, counts=None) -> tuple:
    """Return (programs, errors). Literal parsing only; nothing is executed.

    Only ```python / ```py / bare fenced blocks that assign at least one of FWD/TOP/BWD are program
    blocks. Other blocks (hand traces, diagrams, ```text) are skipped and counted in
    counts['non_program_block'] - they are not parse errors. Gate-name aliases are normalised
    (counts['normalised_gate']). `counts` is an optional Counter/dict updated in place.
    """
    from circuitevolve.ir import ARITY
    names = BLIND_NAMES if blinded else OPEN_NAMES
    inv_r = {v: k for k, v in names["roles"].items()}
    inv_g = {v: k for k, v in names["gates"].items()}
    known = set(ARITY) | set(names["gates"].values())
    counts = counts if counts is not None else Counter()
    blocks = _code_blocks(text)
    progs, errors = [], []
    n_prog_blocks = 0
    for lang, blk in blocks:
        if lang not in _PY_LANGS or not _DEFINES.search(blk):
            counts["non_program_block"] = counts.get("non_program_block", 0) + 1
            continue
        n_prog_blocks += 1
        if n_prog_blocks > max_programs:
            break
        try:
            tree = ast.parse(blk)
            found = {}
            for stmt in tree.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                    nm = stmt.targets[0].id.upper()
                    if nm in ("FWD", "TOP", "BWD"):
                        elts = stmt.value.elts if isinstance(stmt.value, (ast.Tuple, ast.List)) else None
                        if elts is None and isinstance(stmt.value, ast.Call):
                            elts = [stmt.value]          # FWD = (G(...)) - a 1-tuple missing its comma
                            counts["single_call_template"] = counts.get("single_call_template", 0) + 1
                        if elts is None:
                            raise ParseError(f"{nm} is not a tuple")
                        gates = []
                        for call in elts:
                            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "G"):
                                raise ParseError("template entries must be G(...) calls")
                            args = [_lit(a) for a in call.args]
                            kw = {k.arg: _lit(k.value) for k in call.keywords}
                            if not args:
                                raise ParseError("empty G()")
                            g0 = normalise_gate(args[0], known)
                            if g0 != args[0]:
                                counts["normalised_gate"] = counts.get("normalised_gate", 0) + 1
                            g = inv_g.get(g0, g0)
                            roles = []
                            for r in args[1:]:
                                if r not in inv_r:
                                    raise ParseError(f"unknown role {r!r}")
                                roles.append(inv_r[r])
                            gates.append((g, tuple(roles), kw.get("cond"), kw.get("label")))
                        found[nm] = tuple(gates)
            if set(found) != {"FWD", "TOP", "BWD"}:
                raise ParseError(f"missing templates: {sorted({'FWD', 'TOP', 'BWD'} - set(found))}")
            progs.append(SliceProgram(found["FWD"], found["TOP"], found["BWD"]))
        except (SyntaxError, ParseError) as e:
            errors.append(f"{type(e).__name__}: {e}")
    if not n_prog_blocks:
        errors.append("no program block in response" if blocks else "no code block in response")
    return progs, errors


def parse_programs_p4(text: str, blinded: bool, max_programs: int = 8) -> tuple:
    """The P4 parser, verbatim in behaviour; kept only to measure before/after parse-error rates."""
    names = BLIND_NAMES if blinded else OPEN_NAMES
    inv_r = {v: k for k, v in names["roles"].items()}
    inv_g = {v: k for k, v in names["gates"].items()}
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    progs, errors = [], []
    for blk in blocks[:max_programs]:
        try:
            tree = ast.parse(blk)
            found = {}
            for stmt in tree.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                    nm = stmt.targets[0].id.upper()
                    if nm in ("FWD", "TOP", "BWD"):
                        if not isinstance(stmt.value, (ast.Tuple, ast.List)):
                            raise ParseError(f"{nm} is not a tuple")
                        gates = []
                        for call in stmt.value.elts:
                            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "G"):
                                raise ParseError("template entries must be G(...) calls")
                            args = [_lit(a) for a in call.args]
                            kw = {k.arg: _lit(k.value) for k in call.keywords}
                            if not args:
                                raise ParseError("empty G()")
                            g = inv_g.get(args[0], args[0])
                            roles = []
                            for r in args[1:]:
                                if r not in inv_r:
                                    raise ParseError(f"unknown role {r!r}")
                                roles.append(inv_r[r])
                            gates.append((g, tuple(roles), kw.get("cond"), kw.get("label")))
                        found[nm] = tuple(gates)
            if set(found) != {"FWD", "TOP", "BWD"}:
                raise ParseError(f"missing templates: {sorted({'FWD', 'TOP', 'BWD'} - set(found))}")
            progs.append(SliceProgram(found["FWD"], found["TOP"], found["BWD"]))
        except (SyntaxError, ParseError) as e:
            errors.append(f"{type(e).__name__}: {e}")
    if not blocks:
        errors.append("no code block in response")
    return progs, errors


# --------------------------------------------------------------------------------------------- backends
# moved to circuitevolve/llm_backends.py (shared with the window core); re-exported here unchanged.
from circuitevolve.llm_backends import (_FATAL, _TRANSIENT, is_transient, make_api_backend,  # noqa: F401
                                        make_batch_merger, make_cli_backend)


# --------------------------------------------------------------------------------------------- loop
def llm_search(seed, tier, complete, n_calls, k=4, batch=6, blinded=False, feedback=True, rng_seed=0,
               n_elites=3, n_failures=4, log_path=None, repair_budget=0,
               playbook=None, reflect_every=0, reflect_complete=None, format_rules=True):
    """LLM-driven MAP-Elites. Budget = n_calls LLM calls (evaluations are counted too).

    feedback=False is the zero-shot arm: every call sees only the seed, no archive, no failures.
    repair_budget > 0 is the hybrid arm: each rejected proposal gets up to that many random local
    mutations (1-2 edits each); the first variant that verifies is kept. Repair evaluations count
    toward `evals` like any other.

    playbook (search/playbook.py) is the self-evolving arm: its rules are rendered into each prompt,
    candidates are A/B-tested on raw verifier pass rate, and every `reflect_every` batches a reflector
    call (`reflect_complete`, default `complete`) proposes rule deltas. Reflector calls are counted
    separately in stats["reflect_calls"]; they are extra LLM calls and must be reported as such.
    With playbook=None the loop is identical to the P4 version (same RNG stream).
    format_rules=False sends the P4 prompt verbatim (no output-format paragraph). Responses are parsed
    with parse_programs; non-program code blocks are counted in stats["non_program_block"], not as
    parse errors. If `complete` has a `stats` Counter, its change over this run is stats["backend"].
    """
    from circuitevolve.integrity import check_unchanged, frozen_digest
    digest = frozen_digest()
    if playbook is not None:
        assert playbook.blinded == blinded, "playbook naming (blinded/open) must match the run"
        if blinded and not playbook.banned_words:
            playbook.banned_words = CUE_WORDS
        pb_rng = random.Random(rng_seed + 7919)
        reflect_complete = reflect_complete or complete
        names = BLIND_NAMES if blinded else OPEN_NAMES
        show = lambda p: to_source(_rename_prog(p, names))
        recent_imp, recent_fail = deque(maxlen=4), deque(maxlen=6)
        window = Counter()
    backend_stats0 = Counter(getattr(complete, "stats", {}) or {})
    rng = random.Random(rng_seed)
    ev = Evaluator(tier)
    ok, fit, _ = ev(seed)
    assert ok
    seed_fit = fit
    archive = {(fit[0], fit[4] // 4): (fit, seed)}
    best, best_prog = fit, seed
    failures = deque(maxlen=n_failures)
    counts = Counter()
    traj = [(0, ev.calls, best[0])]
    log = open(log_path, "a") if log_path else None
    calls = 0
    batches = 0
    t0 = time.time()
    while calls < n_calls:
        nb = min(batch, n_calls - calls)
        jobs = []
        for _ in range(nb):
            if feedback:
                elites = list(archive.values())
                pf, parent = min(elites, key=lambda e: e[0]) if rng.random() < 0.5 else rng.choice(elites)
                others = rng.sample(elites, min(n_elites, len(elites)))
                others = [e for e in others if e[1] != parent]
            else:
                pf, parent, others = seed_fit, seed, []
            sel = None
            rules_text = ""
            if playbook is not None:
                texts, shown, hidden = playbook.select(pb_rng)
                sel = (shown, hidden)
                rules_text = playbook.render(texts)
            prompt = build_prompt(parent, pf, others, list(failures), blinded, tier, k, feedback, rules_text,
                                  format_rules=format_rules)
            jobs.append((parent, pf, sel, prompt))
        responses = complete([j[3] for j in jobs])
        calls += nb
        for (parent, pf, sel, prompt), resp in zip(jobs, responses):
            rec = {"call": calls, "blinded": blinded, "feedback": feedback, "prompt_chars": len(prompt)}
            if sel is not None:
                rec["rules_shown"] = sel[0]
            if isinstance(resp, Exception):
                counts["llm_error"] += 1
                rec["error"] = str(resp)
                if log:
                    log.write(json.dumps(rec) + "\n")
                continue
            pc = Counter()
            progs, errs = parse_programs(resp, blinded, counts=pc)
            counts["parse_error"] += len(errs)
            counts.update(pc)
            rec["parse_counts"] = dict(pc)
            counts["proposals"] += len(progs)
            verdicts = []
            improved = False
            for p in progs:
                if ev.seen(p):
                    counts["duplicate"] += 1
                    verdicts.append("duplicate")
                    continue
                okp, fp, rep = ev(p)
                verdicts.append("pass" if okp else rep.level)
                if not okp:
                    counts[f"fail_{rep.level}"] += 1
                    failures.append((p, rep.reason[:160]))
                    if playbook is not None:
                        recent_fail.append((show(p), rep.reason[:160]))
                    fixed = None
                    for _ in range(repair_budget):
                        q = mutate(p, TIERS[tier], rng)
                        if rng.random() < 0.5:
                            q = mutate(q, TIERS[tier], rng)
                        okq, fq, _ = ev(q)
                        if okq:
                            fixed = (q, fq)
                            break
                    if fixed is None:
                        continue
                    counts["repaired"] += 1
                    verdicts[-1] = f"{verdicts[-1]}->repaired"
                    p, fp = fixed
                counts["accepted"] += 1
                cell = (fp[0], fp[4] // 4)
                if cell not in archive or fp <= archive[cell][0]:
                    archive[cell] = (fp, p)
                if fp < best:
                    best, best_prog = fp, p
                if playbook is not None and fp < pf:
                    improved = True
                    recent_imp.append((list(pf[:3]), list(fp[:3]), show(parent), show(p)))
            traj.append((calls, ev.calls, best[0]))
            if playbook is not None:
                n_new = sum(1 for v in verdicts if v != "duplicate")
                n_pass = sum(1 for v in verdicts if v == "pass")          # raw LLM passes, before repair
                playbook.record(sel[0], sel[1], n_new, n_pass, improved)
                window.update(proposals=n_new, raw_pass=n_pass, improved_prompts=int(improved))
                for rid, new, z in playbook.update_status(calls):
                    counts[f"rules_{new}"] += 1
                    rec.setdefault("gate", []).append([rid, new, z])
            rec.update({"verdicts": verdicts, "parse_errors": errs, "best": best, "response": resp})
            if log:
                log.write(json.dumps(rec, default=str) + "\n")
        batches += 1
        if (playbook is not None and reflect_every and batches % reflect_every == 0 and not playbook.frozen
                and window["proposals"] == 0):
            counts["reflect_skipped_no_evidence"] += 1   # never let the reflector write rules from prior knowledge alone
        elif playbook is not None and reflect_every and batches % reflect_every == 0 and not playbook.frozen:
            stats_now = dict(window, best=list(best[:3]), calls=calls)
            rprompt = playbook.reflect_prompt(_task_text(blinded), list(recent_imp), list(recent_fail), stats_now)
            rresp = reflect_complete([rprompt])[0]
            counts["reflect_calls"] += 1
            rrec = {"call": calls, "reflect": True}
            if isinstance(rresp, Exception):
                counts["reflect_error"] += 1
                rrec["error"] = str(rresp)
            else:
                applied, rerrs = playbook.apply_deltas(rresp, calls)
                counts["rules_added"] += sum(1 for a in applied if a[0] in ("add", "edit"))
                rrec.update({"applied": applied, "errors": rerrs, "response": rresp})
            window.clear()
            recent_imp.clear()
            if log:
                log.write(json.dumps(rrec, default=str) + "\n")
    if log:
        log.close()
    check_unchanged(digest)
    stats = {"calls": calls, "evals": ev.calls, "seconds": round(time.time() - t0, 1), "best": best,
             "archive_cells": len(archive), "verifier_digest": digest[:16], **counts}
    if hasattr(complete, "stats"):
        d = Counter(complete.stats)
        d.subtract(backend_stats0)
        stats["backend"] = {k: v for k, v in d.items() if v}
    if playbook is not None:
        stats["playbook"] = {s: sum(1 for r in playbook.rules if r.status == s) for s in ("active", "candidate", "retired")}
    return archive, traj, stats, best_prog
