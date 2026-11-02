"""The run loop: Claude Code rounds with harness feedback, and the playbook.

The LLM proposes, the harness disposes. The agent edits a circuit file in a folder; nothing it says about its own
work is believed. Every round ends with the harness re-deriving equivalence and T-count itself (judge), and a round
is accepted only if that check passes. The agent's own check.py is a convenience for the agent, never the record.

    workspace(name, arm, tk)  runs/<name>_<arm>_<time>/: tket_start/start/circuit .qasm (the agent edits circuit.qasm),
                              check.py, ./py (the agent's own scripts, venv Python), frozen copies of pipeline/verifier
    playbook_stage            (playbook.py) shared arm only, before round 1: try every valid rule in playbook/shared/;
                              keep an output only if it verifies against the TKET start, keeps the qubits, lowers T
    run_agent(dir, log, msg)  one `claude -p` session turn in that folder; round 1 opens session S, later rounds
                              `--resume S` with the harness feedback as the message. Every event is logged live.
                              (a module-level function, so a test can swap in a stand-in agent)
    judge(dir, best, log)     the harness re-checks circuit.qasm with ITS OWN verifier and T-count. Accept only if
                              equivalent AND the T-count is below the best so far; otherwise circuit.qasm is reset
    record_technique(...)     after an accepted round: card + technique.py, replayed on the round's start circuit,
                              stored lean in playbook/<arm>/<run>_r<round>/
    fingerprint()             sha256 of the repo's *.py, prompt, circuits, playbook: unchanged after every round (tamper check)
Usage: python agent.py tfim_4 [rounds] [--arm isolated|shared|opus] [--model ID]     (isolated never reads playbook entries;
       opus = shared behaviour on its own playbook/opus/, seeded with a copy of playbook/shared/)
"""
import argparse, glob, hashlib, json, os, shutil, subprocess, sys, time, uuid

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [ROOT, os.path.join(ROOT, "verifier")]
from qiskit import QuantumCircuit, qasm2
from pipeline import HERE, Log, load, logical, stats, t_count, tket
from playbook import ENTRY_FILES, find_circuit, playbook_stage, try_rule
import verifier_anc, verifier_noanc

PROMPTS = os.path.join(ROOT, "prompts")
# arm -> (prompt, verifier module, check.py template, reads playbook/<arm>/ before round 1); both files in prompts/
ARMS = {"isolated": ("prompt_noanc.md", verifier_noanc, "check_noanc_template.py", False),
        "shared": ("prompt_noanc.md", verifier_noanc, "check_noanc_template.py", True),
        "opus": ("prompt_noanc.md", verifier_noanc, "check_noanc_template.py", True),
        "anc_isolated": ("prompt_anc.md", verifier_anc, "check_anc_template.py", False),
        "anc_shared": ("prompt_anc.md", verifier_anc, "check_anc_template.py", True)}
# Ancilla arms: the reference is ALWAYS the TKET start (round starts may already hold ancillas); stored ancilla rules
# are not chained (each runs alone on the TKET start, reading logical.qasm); playbook/<arm>/ holds their entries.


def is_anc(arm):
    return arm.startswith("anc_")


def verify(old, new, **kw):
    """The final / no-ancilla check: verifier_noanc on the same qubits, verifier_anc if new has extra qubits."""
    return (verifier_anc if new.num_qubits > old.num_qubits else verifier_noanc).verify(old, new, **kw)

MODEL = "claude-sonnet-5-5"
RETRIES = 2
BLOCKED = ["ScheduleWakeup", "Task", "Agent"]   # no deferred work: a turn must finish its own commands
LIMIT_ERRORS = ("hit your session limit", "usage limit", "hit your limit")
NETWORK_ERRORS = ("API Error", "ECONN", "ETIMEDOUT", "ENOTFOUND", "proxy", "Connection error", "overloaded", "socket hang up")
# The sandbox: files in the run folder, plus two commands -- check.py (the agent's own verdict) and ./py (the venv
# interpreter, for scripts it writes). No harness code, no other runs, no network.
TOOLS = ["Read", "Edit", "Write", "Bash(python3 check.py)", "Bash(python3 check.py:*)", "Bash(./py:*)"]
ROUNDS, TIMEOUT_S = 3, 20 * 60
RUNS, PLAYBOOK = os.path.join(HERE, "runs"), os.path.join(HERE, "playbook")     # a test may point these elsewhere


def fingerprint():
    """sha256 of every file the agent must not touch, compared before and after each round. Any change means it
    reached outside its folder, and the run is stopped rather than scored."""
    files = sorted(glob.glob(os.path.join(HERE, "*.py")) + glob.glob(os.path.join(HERE, "*.md"))
                   + [p for d in ("verifier", "prompts", "sweep", "tests", "circuits", "examples")
                      for p in glob.glob(os.path.join(HERE, d, "**"), recursive=True)]
                   + glob.glob(os.path.join(PLAYBOOK, "**"), recursive=True))
    return {os.path.relpath(f, HERE): hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files if os.path.isfile(f)}


def workspace(name, arm, start, src=None):
    d = os.path.join(RUNS, f"{name}_{arm}_{time.strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(d)
    for f in ("tket_start.qasm", "start.qasm", "circuit.qasm"):
        open(os.path.join(d, f), "w").write(qasm2.dumps(start))
    _, ver, template, _ = ARMS[arm]
    shutil.copy(os.path.join(HERE, "pipeline.py"), d)
    shutil.copy(ver.__file__, d)
    if is_anc(arm) and src:                                     # read-only source view (ccx, custom gates kept)
        try:
            qasm2.dump(logical(src), os.path.join(d, "logical.qasm"))
        except Exception:                                       # a gate qasm2 cannot export: copy the file as is
            shutil.copy(src, os.path.join(d, "logical.qasm"))
    # The frozen copies above mean a run is scored by the code as it stood when it started, even if the harness is
    # edited mid-campaign.
    check = open(os.path.join(PROMPTS, template)).read().replace("__VENV_PYTHON__", sys.executable)
    open(os.path.join(d, "check.py"), "w").write(check)
    open(os.path.join(d, "py"), "w").write(f'#!/bin/sh\nCHECK_IN_VENV=1 exec "{sys.executable}" "$@"\n')
    os.chmod(os.path.join(d, "py"), 0o755)
    return d


def _short(x, n=400):
    s = x if isinstance(x, str) else json.dumps(x)
    return s if len(s) <= n else s[:n] + f" ... [{len(s) - n} more chars]"


def _log_event(e, log, names):
    """One stream-json event from Claude Code -> one log entry."""
    if e["type"] == "system" and e.get("subtype") == "init":
        log("agent session started", model=e.get("model"), session=e.get("session_id"), permission_mode=e.get("permissionMode"))
    elif e["type"] == "assistant":
        for b in e["message"]["content"]:
            if b["type"] == "text" and b["text"].strip():
                log("agent says", b["text"])
            elif b["type"] == "tool_use":
                names[b["id"]] = b["name"]
                inp = b["input"]
                if b["name"] == "Edit":
                    text = f"old:\n```\n{_short(inp.get('old_string', ''))}\n```\nnew:\n```\n{_short(inp.get('new_string', ''))}\n```"
                elif b["name"] == "Write":
                    text = (f"writes {len(inp.get('content', '').splitlines())} lines to "
                            f"{os.path.basename(inp.get('file_path', ''))}:\n```\n{_short(inp.get('content', ''), 4000)}\n```")
                else:
                    text = f"`{_short(inp, 1500)}`"
                log(f"agent tool call: {b['name']}", text)
    elif e["type"] == "user":
        for b in e["message"]["content"]:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                c = b["content"] if isinstance(b["content"], str) else " ".join(x.get("text", "") for x in b["content"])
                log(f"tool result: {names.get(b['tool_use_id'], '?')}", "```\n" + _short(c, 1500) + "\n```",
                    error=bool(b.get("is_error")))
    elif e["type"] == "result":
        log("agent turn finished", turns=e.get("num_turns"), seconds=round(e.get("duration_ms", 0) / 1000),
            is_error=e.get("is_error"))


def run_agent(d, log, message, session, first):
    log("message to agent", "```\n" + message + "\n```", model=MODEL, allowed_tools=" ".join(TOOLS),
        session=session, resumed=not first)
    env = dict(os.environ, PATH=os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin",
               CLAUDE_CONFIG_DIR=os.path.join(HERE, ".cache", "claude_config"))   # sessions must persist for --resume
    for attempt in range(1 + RETRIES):                          # retry only on API / network errors
        cmd = ["claude", "-p", "--model", MODEL, "--output-format", "stream-json", "--verbose", "--allowedTools", *TOOLS, "--disallowedTools", *BLOCKED]
        cmd += ["--session-id", session] if first else ["--resume", session]
        p = subprocess.Popen(cmd, cwd=d, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p.stdin.write(message); p.stdin.close()
        names, t0, seen, started = {}, time.time(), [], False
        with open(os.path.join(d, "transcript.jsonl"), "a") as tr:
            for line in p.stdout:                               # live: one log entry per event, as it happens
                tr.write(line); seen.append(line[:2000])
                try:
                    e = json.loads(line)
                    started |= e.get("type") == "system"
                    _log_event(e, log, names)
                except json.JSONDecodeError:
                    pass
                if time.time() - t0 > TIMEOUT_S:
                    p.kill(); log("agent killed", f"turn exceeded {TIMEOUT_S} s"); break
        p.wait()
        err = p.stderr.read()
        if p.returncode not in (0, None, -9):
            log("agent process error", _short(err, 1500), returncode=p.returncode)
        text = err + "".join(seen[-3:])
        if any(k in text for k in LIMIT_ERRORS):                # account limit: stop the run, do not log empty rounds
            log("USAGE LIMIT", "Claude account limit reached; aborting this run", detail=_short(text, 300))
            raise SystemExit("usage limit reached")
        if not any(k in text for k in NETWORK_ERRORS) or attempt == RETRIES:
            return
        if started:
            first = False                                       # the session exists now: resume it
        log("network retry", f"API/network error; retrying in {60 * (attempt + 1)} s", attempt=attempt + 1)
        time.sleep(60 * (attempt + 1))


def judge(d, start, best, log, arm="isolated"):
    """Harness verdict on circuit.qasm with the arm's verifier. Returns (new best (circuit, T), feedback text)."""
    path, anc = os.path.join(d, "circuit.qasm"), is_anc(arm)
    try:
        new = QuantumCircuit.from_qasm_file(path)
        v = ARMS[arm][1].verify(start, new, log=log, label="(harness: circuit.qasm vs start.qasm)")
        T = t_count(new) if v["ok"] else None
    except Exception as e:
        new, v, T = None, dict(ok=False, distance=None, reason=f"does not parse: {str(e)[:200]}"), None
    best_c, best_T = best
    # Lexicographic, never a weighted blend: correctness first, then T-count. A blended score that traded
    # infidelity for T would be maximised by subtly wrong circuits.
    accepted = v["ok"] and T < best_T
    word = "valid" if anc else "equivalent"
    why = ("new best" if accepted else f"not {word}: " + v["reason"] if not v["ok"]
           else f"T-count {T} is not below the best so far ({best_T})")
    log("judge", f"accept only if {word} AND T-count below the best so far", equivalent=v["ok"],
        distance=v["distance"], T=T, best_before=best_T, accepted=accepted, reason=why,
        rotations=stats(new)["arbitrary_rz"] if new is not None else None,
        ancillas=v.get("ancillas"), measurements=v.get("measurements"))
    if accepted:
        best_c, best_T = new, T
    else:                                                       # continue from the best circuit so far
        open(path, "w").write(qasm2.dumps(best_c))
        log("reset", "circuit.qasm reset to the best circuit so far")
    feedback = (f"Harness check of your result:\n"
                + (f"- valid replacement for start.qasm (ancilla rules): {'yes' if v['ok'] else 'NO'} ({v['reason']}); "
                   f"ancillas {v.get('ancillas')}, measurements {v.get('measurements')}\n" if anc else
                   f"- equivalent to start.qasm: {'yes' if v['ok'] else 'NO'} ({v['reason']})\n") +
                f"- your T-count: {T if T is not None else 'n/a'}; best so far: {best_T}; start: {t_count(start)}\n"
                f"- decision: {'ACCEPTED' if accepted else 'REJECTED'} ({why})"
                + ("" if accepted else "; circuit.qasm has been reset to the best circuit so far") + "\n\n"
                "Try to lower the T-count further. If you think your current approach cannot go lower, say why in "
                "one or two sentences and try a different approach.")
    return (best_c, best_T), feedback, accepted


STAGE_NOTE = """
## Rules from earlier runs (playbook)
Before you started, the harness tried these stored rules on this circuit; start.qasm is the best verified result.
Each rule's card and script are in playbook_cards/<rule>/ (`./py playbook_cards/<rule>/technique.py IN.qasm OUT.qasm`).
{rules}
"""


CARD = """Your change was ACCEPTED (T-count {T0} -> {T1}). Do not change circuit.qasm any more. Run every command in the foreground and wait for it to finish: no background commands, no scheduled wake-ups. Turn THIS round's step
into a reusable playbook entry (only technique.md and technique.py are kept; your other scripts stay in this folder):
1. Write `technique.md`: first line `# <short name>`; the idea in 3-6 sentences; a line `**Applies when:** ...` (what
   structure to look for in a circuit) and a line `**Does not apply when:** ...`.
2. Write `technique.py`, a self-contained (one file; qiskit, numpy, scipy) and GENERAL version of this step:
   `./py technique.py IN.qasm OUT.qasm` reads any circuit in this gate set, detects whether the technique applies
   (do not hard-code this circuit's size, qubit count or angles), and writes an equivalent circuit on the same qubits
   to OUT.qasm (an unchanged copy if it does not apply).
3. Run `./py technique.py round_start.qasm replay.qasm`. round_start.qasm is the circuit as it was at the START of this
   round (before your change). The harness replays technique.py on it, verifies the output and counts its T gates,
   so make sure it reproduces this round's result."""
CARD_NOANC_OUT = "writes an equivalent circuit on the same qubits\n   to OUT.qasm (an unchanged copy if it does not apply)."
CARD_ANC_OUT = ("writes a circuit that is valid under this task's\n   ancilla rules to OUT.qasm (the original qubits first, "
                "then 1 to 6 ancillas; an unchanged copy if it does not apply).\n   It may also read `logical.qasm` from "
                "the folder of IN.qasm: the harness puts the circuit's logical form there.")
CARD_NOANC_REPLAY = "3. Run `./py technique.py round_start.qasm replay.qasm`. round_start.qasm is the circuit as it was at the START of this\n   round (before your change). The harness replays technique.py on it, verifies the output and counts its T gates,\n   so make sure it reproduces this round's result."
CARD_ANC_REPLAY = ("3. Run `./py technique.py tket_start.qasm replay.qasm`. Ancilla rules are always applied ALONE to the circuit without\n"
                   "   ancillas (tket_start.qasm, with logical.qasm next to it), never on top of earlier rules. The harness replays\n"
                   "   technique.py on tket_start.qasm, verifies the output and counts its T gates, so make sure it reproduces this\n"
                   "   round's result (or better) from there.")
assert CARD_NOANC_OUT in CARD and CARD_NOANC_REPLAY in CARD


# A rule enters the playbook only after the harness has replayed the stored technique.py on the round's own starting
# circuit and re-verified the result, so what is archived is a script checked to work, not a description of one.
# valid_rules() in playbook.py later filters on that recorded replay.
def record_technique(d, log, session, name, arm, rnd, before, after, T0, T1, ref=None):
    """Ask for a card + technique.py; store them lean in playbook/<arm>/<run>_r<rnd>/ with the replay on `before`,
    verified against `ref` (default `before`; ancilla arms pass the TKET start)."""
    log("PLAYBOOK: request technique card")
    card_text = CARD.replace(CARD_NOANC_OUT, CARD_ANC_OUT).replace(CARD_NOANC_REPLAY, CARD_ANC_REPLAY) if is_anc(arm) else CARD
    run_agent(d, log, card_text.format(T0=T0, T1=T1), session, first=False)
    dest = os.path.join(PLAYBOOK, arm, f"{os.path.basename(d)}_r{rnd}")
    os.makedirs(dest)
    for f in ENTRY_FILES:
        if os.path.exists(os.path.join(d, f)):
            shutil.copy(os.path.join(d, f), dest)
    qasm2.dump(before, os.path.join(dest, "before.qasm")); qasm2.dump(after, os.path.join(dest, "after.qasm"))
    replay = dict(ran=False, equivalent=False, distance=None, T=None, qubits_same=None, reason="no technique.py")
    if os.path.exists(os.path.join(dest, "technique.py")):        # replay the stored copy on the round-start circuit
        if is_anc(arm):                                         # ancilla rules: alone on the TKET start (as in sweeps)
            _, replay = try_rule(os.path.join(dest, "technique.py"), ref, ref, os.path.join(d, f"replay_in_r{rnd}.qasm"),
                                 os.path.join(d, f"replay_r{rnd}.qasm"), timeout=600, verify_fn=verifier_anc.verify)
        else:
            _, replay = try_rule(os.path.join(dest, "technique.py"), before, before, os.path.join(d, "round_start.qasm"),
                                 os.path.join(d, f"replay_r{rnd}.qasm"), timeout=600)
    card = open(os.path.join(dest, "technique.md")).read() if os.path.exists(os.path.join(dest, "technique.md")) else None
    entry = dict(circuit=name, arm=arm, run=os.path.relpath(d, HERE), round=rnd, T_before=T0, T_after=T1,
                 replay=replay, card=card)
    json.dump(entry, open(os.path.join(dest, "entry.json"), "w"), indent=1)
    log("PLAYBOOK: entry archived", card or "(no technique.md written)", folder=os.path.relpath(dest, HERE),
        replay=replay)


def main(name, rounds=ROUNDS, arm="isolated"):
    src = find_circuit(name)
    tk = tket(load(src))                                        # the TKET baseline
    d = workspace(name, arm, tk, src)
    log = Log(f"agent_{os.path.basename(d)}")
    log("start", "TKET baseline", circuit=name, arm=arm, model=MODEL, folder=os.path.relpath(d, HERE),
        T=t_count(tk), **stats(tk))
    start, message = tk, open(os.path.join(PROMPTS, ARMS[arm][0])).read()
    if ARMS[arm][3]:                                            # shared/opus: start from the best stored-rule result
        log("PLAYBOOK STAGE", f"try every valid rule in {os.path.relpath(os.path.join(PLAYBOOK, arm), HERE)}/")
        start, lines = playbook_stage(d, tk, os.path.join(PLAYBOOK, arm), log,
                                      **(dict(verify_fn=verifier_anc.verify, logical_path=os.path.join(d, "logical.qasm"))
                                         if is_anc(arm) else {}))
        for f in ("start.qasm", "circuit.qasm"):
            qasm2.dump(start, os.path.join(d, f))
        message += STAGE_NOTE.format(rules="\n".join(lines) or "(no stored rules yet)")
        log("playbook stage done", "agent starts from the best rule result", rules_tried=len(lines),
            T_tket=t_count(tk), T=t_count(start))
    best = (start, t_count(start))
    session, history = str(uuid.uuid4()), []
    for r in range(1, rounds + 1):
        log(f"ROUND {r}")
        qasm2.dump(best[0], os.path.join(d, "round_start.qasm"))   # the circuit at the start of this round
        before = fingerprint()
        run_agent(d, log, message, session, first=(r == 1))
        after = fingerprint()                                  # files that existed at round start must be unchanged;
        changed = [f for f in before if after.get(f) != before[f]]  # new files (e.g. a parallel run's entry) are fine
        if changed:
            log("TAMPER CHECK FAILED", "files outside the run folder changed; stopping", changed=changed)
            break
        log("tamper check", "harness code, prompt and circuits unchanged", files_checked=len(before))
        prev = best
        ref = tk if is_anc(arm) else start                     # ancilla arms: start may already hold ancillas
        best, message, accepted = judge(d, ref, best, log, arm)
        history.append(dict(round=r, best_T=best[1]))
        if accepted:
            record_technique(d, log, session, name, arm, r, prev[0], best[0], prev[1], best[1],
                             ref=tk if is_anc(arm) else None)
    qasm2.dump(best[0], os.path.join(d, "best.qasm"))
    v = verify(tk, best[0], log=log, label="(final: best.qasm vs the TKET start)")
    log("final", f"best circuit saved to {os.path.relpath(d, HERE)}/best.qasm", T_tket=t_count(tk),
        T_start=t_count(start), T_best=best[1], equivalent_to_tket=v["ok"],
        rotations_best=stats(best[0])["arbitrary_rz"], ancillas_best=best[0].num_qubits - tk.num_qubits,
        per_round=history)
    return dict(circuit=name, arm=arm, folder=os.path.relpath(d, HERE), T_tket=t_count(tk), T_start=t_count(start),
                T_best=best[1], ancillas_best=best[0].num_qubits - tk.num_qubits, equivalent_to_tket=v["ok"],
                rounds=history)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("circuit"); a.add_argument("rounds", nargs="?", type=int, default=ROUNDS)
    a.add_argument("--arm", choices=list(ARMS), default="isolated")
    a.add_argument("--model", default=MODEL)
    a = a.parse_args()
    MODEL = a.model
    print(json.dumps(main(a.circuit, a.rounds, a.arm)))
