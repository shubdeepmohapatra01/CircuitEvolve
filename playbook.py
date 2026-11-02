"""The playbook rules, outside the agent loop (used by agent.py's shared arm and by sweep.py).

A playbook entry is a general, self-contained script (technique.py) that reads one circuit and writes another: the
transfer mechanism, re-running a technique the agent found on one circuit, with no LLM, on circuits it never saw.
A rule runs in a subprocess under a timeout, and its output is kept only if the verifier accepts it and T went down.

    find_circuit(name)        circuits/<name>.qasm, else benchmarks/**/<name>.qasm
    try_rule(script, qc, ref) run `script IN OUT`; keep OUT only if it parses, uses allowed gates, keeps the qubit
                              count and verifies against ref (1e-8); returns (circuit or None, verdict)
    valid_rules(folder)       entries (oldest first) whose recorded replay was equivalent and lowered T
    playbook_stage(d, tk, ..) try every valid rule in turn on the current circuit, keep only verified T gains
"""
import glob, json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [ROOT, os.path.join(ROOT, "verifier")]
from qiskit import QuantumCircuit, qasm2
from pipeline import HERE, t_count
from verifier_noanc import verify

ALLOWED = {"h", "x", "z", "s", "sdg", "t", "tdg", "cx", "rz"}
ENTRY_FILES = ("technique.py", "technique.md")
RULE_TIMEOUT_S = 300


def find_circuit(name):
    """circuits/<name>.qasm, else the first benchmarks/**/<name>.qasm."""
    hits = [p for p in [os.path.join(HERE, "circuits", f"{name}.qasm")] if os.path.exists(p)]
    hits += sorted(glob.glob(os.path.join(HERE, "benchmarks", "**", f"{name}.qasm"), recursive=True))
    if not hits:
        raise FileNotFoundError(f"{name}.qasm not in circuits/ or benchmarks/")
    return hits[0]


def try_rule(script, qc, ref, inp, out, timeout=RULE_TIMEOUT_S, verify_fn=None, logical_path=None):
    """Write qc to inp, run `script inp out`, check out: parses, allowed gates, same qubits, equivalent to ref.
    verify_fn (ancilla arm: verifier_anc.verify) replaces the gate / qubit-count / equivalence checks; logical_path is
    copied next to inp as logical.qasm. Returns (verified circuit or None, verdict dict(ran, equivalent, distance, T,
    qubits_same, reason[, ancillas, measurements])).
    Subprocess, not import: a stored rule is agent-written code, so it gets its own interpreter and a wall-clock
    timeout. A rule that crashes, hangs or emits nothing is simply not applied."""
    script, inp, out = map(os.path.abspath, (script, inp, out))
    qasm2.dump(qc, inp)
    if logical_path and os.path.abspath(logical_path) != os.path.join(os.path.dirname(inp), "logical.qasm"):
        shutil.copy(logical_path, os.path.join(os.path.dirname(inp), "logical.qasm"))
    v = dict(ran=False, equivalent=False, distance=None, T=None, qubits_same=None)
    try:
        r = subprocess.run([sys.executable, script, inp, out], cwd=os.path.dirname(inp), capture_output=True,
                           text=True, timeout=timeout)
        if r.returncode != 0:
            return None, v | dict(reason=f"exit {r.returncode}: {r.stderr[-300:]}")
        new = QuantumCircuit.from_qasm_file(out)
    except Exception as e:                                      # timeout, no output, does not parse
        return None, v | dict(reason=f"{type(e).__name__}: {str(e)[:200]}")
    v |= dict(ran=True, qubits_same=new.num_qubits == ref.num_qubits)
    if verify_fn is not None:                                   # ancilla arm: the verifier does every check
        e = verify_fn(ref, new)
        v |= dict(equivalent=e["ok"], distance=e["distance"], T=t_count(new) if e["ok"] else None, reason=e["reason"],
                  ancillas=e.get("ancillas"), measurements=e.get("measurements"))
        return (new if e["ok"] else None), v
    # Gate set before equivalence: a gate outside the basis could be "equivalent" while hiding non-Clifford cost
    # the T-metric cannot charge.
    bad = set(new.count_ops()) - ALLOWED
    if bad or not v["qubits_same"]:
        return None, v | dict(reason=f"gates not allowed: {sorted(bad)}" if bad else
                              f"qubit count changed {ref.num_qubits} -> {new.num_qubits}")
    e = verify(ref, new)
    v |= dict(equivalent=e["ok"], distance=e["distance"], T=t_count(new) if e["ok"] else None, reason=e["reason"])
    return (new if e["ok"] else None), v


def valid_rules(folder):
    """[(entry folder, entry)] oldest first, for entries whose replay was equivalent and lowered T. Oldest first, so
    a chained (shared-arm) stage applies rules in discovery order and is reproducible from the folder alone."""
    out = []
    for p in sorted(glob.glob(os.path.join(folder, "*", "entry.json")), key=os.path.getmtime):
        e = json.load(open(p)); r = e.get("replay", {})
        if (r.get("equivalent") and (r.get("qubits_same", True) or (r.get("ancillas") or 0) > 0)
                and r.get("T") is not None and r["T"] < e["T_before"]
                and os.path.exists(os.path.join(os.path.dirname(p), "technique.py"))):
            out.append((os.path.dirname(p), e))
    return out


def card_line(folder):
    """(name, first line of 'Applies when') from technique.md."""
    p = os.path.join(folder, "technique.md")
    lines = open(p).read().splitlines() if os.path.exists(p) else []
    name = next((l.lstrip("# ").strip() for l in lines if l.strip()), os.path.basename(folder))
    when = next((l.split(":", 1)[-1].strip(" *") for l in lines if "applies when" in l.lower()), "?")
    return name, when[:200]


def playbook_stage(d, tk, folder, log, verify_fn=None, logical_path=None):
    """Try every valid rule in folder in turn on the current circuit; keep only verified T gains.
    Ancilla arms (verify_fn given): NOT chained, every rule runs alone on the TKET start (logical.qasm next to its
    input) and the lowest-T valid output is kept. Copies the cards to d/playbook_cards/.
    Returns (best circuit, one prompt line per rule)."""
    best, T, lines = tk, t_count(tk), []
    os.makedirs(os.path.join(d, "playbook_stage"))
    for entry, _ in valid_rules(folder):
        rule, (name, when) = os.path.basename(entry), card_line(entry)
        shutil.copytree(entry, os.path.join(d, "playbook_cards", rule), ignore=lambda _, fs: set(fs) - set(ENTRY_FILES))
        io = [os.path.join(d, "playbook_stage", f"{rule}_{x}.qasm") for x in ("in", "out")]
        new, v = try_rule(os.path.join(entry, "technique.py"), tk if verify_fn else best, tk, *io,
                          verify_fn=verify_fn, logical_path=logical_path)
        kept = new is not None and v["T"] < T
        why = "lower T" if kept else v["reason"] if new is None else f"T {v['T']} is not below {T}"
        log("playbook try", name, rule=rule, kept=kept, T_before=T, T=v["T"], reason=why)
        lines.append(f"- {rule} ({name}): applies when {when} -- on this circuit: "
                     + (f"kept, T {T} -> {v['T']}" if kept else "no change"))
        if kept:
            best, T = new, v["T"]
    return best, lines
