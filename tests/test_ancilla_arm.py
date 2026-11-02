"""The ancilla arm end to end with a stand-in agent (no Claude Code call). Run: .venv/bin/python tests/test_ancilla_arm.py
Output goes to test_out/<time>_ancilla/ (runs/, playbook/ancilla/); the harness logs to logs/agent_<run>.md as usual.
Stand-in rewrite: every Toffoli of logical.qasm becomes Gidney's temporary AND into a fresh ancilla (4 T) + cx onto
the target + X-basis measurement with a CZ fix-up (0 T). Circuit: circuits/cuccaro_2.qasm (TKET 24 T).
anc_isolated, 3 rounds: r1 the rewrite + 2 wasted T (18, accepted), r2 the rewrite (16, accepted; its card replay starts
from a circuit that already HAS ancillas and must verify against the TKET start), r3 one fix-up dropped (rejected).
anc_shared, 1 round: playbook/anc_shared seeded with the r2 entry; the stage (not chained) must give start = 16 T with
ancillas; the stand-in changes nothing; best.qasm must verify against the TKET start.
"""
import glob, json, os, shutil, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "verifier")]
from qiskit import QuantumCircuit
import agent
from playbook import valid_rules

OUT = os.path.join(agent.HERE, "test_out", time.strftime("%Y%m%d_%H%M%S") + "_ancilla")
agent.RUNS, agent.PLAYBOOK = os.path.join(OUT, "runs"), os.path.join(OUT, "playbook")
RULE = '''"""Per-Toffoli temporary AND (Gidney 2018): each ccx(a, b, t) of the logical circuit becomes AND(a, b -> fresh
ancilla) with 4 T, cx(ancilla, t), then the ancilla is measured in the X basis and CZ(a, b) fixes outcome 1 (0 T).
One ancilla per Toffoli (no reuse after measurement), at most 6. Reads logical.qasm from the folder of IN.qasm.
Usage: technique.py IN.qasm OUT.qasm"""
import os, sys
from qiskit import QuantumCircuit, qasm2, transpile
from qiskit.circuit import ClassicalRegister
inp = QuantumCircuit.from_qasm_file(sys.argv[1])
src = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "logical.qasm")
DROP_FIXUP, PAD = sys.argv[3:] == ["drop"], sys.argv[3:] == ["pad"]   # test hooks: planted bug / 2 wasted T
lg = transpile(QuantumCircuit.from_qasm_file(src), basis_gates=["ccx", "cx", "h", "rz", "x"], optimization_level=0) \\
    if os.path.exists(src) else None
tofs = [] if lg is None else [g for g in lg.data if g.operation.name == "ccx"]
if not tofs or len(tofs) > 6 or lg.num_qubits != inp.num_qubits:
    qasm2.dump(inp, sys.argv[2]); sys.exit(0)                # does not apply: unchanged copy
n = lg.num_qubits
out = QuantumCircuit(n + len(tofs))
k = 0
for g in lg.data:
    qs = [lg.find_bit(q).index for q in g.qubits]
    if g.operation.name != "ccx":
        out.append(g.operation, qs); continue
    a, b, t = qs; c = n + k
    cr = ClassicalRegister(1, f"m{k}"); out.add_register(cr)
    out.h(c); out.t(c); out.cx(a, c); out.cx(b, c); out.cx(c, a); out.cx(c, b)
    out.tdg(a); out.tdg(b); out.t(c); out.cx(c, b); out.cx(c, a); out.h(c); out.s(c)     # c = a AND b
    out.cx(c, t)
    out.h(c); out.measure(c, cr[0])
    if not (DROP_FIXUP and k == 0):
        with out.if_test((cr, 1)):
            out.cz(a, b)
    k += 1
if PAD:
    out.t(0); out.tdg(0)
qasm2.dump(out, sys.argv[2])
'''
CALLS, FULL, MODE = [], [], ["isolated"]


def stand_in(d, log, message, session, first):
    CALLS.append(message.splitlines()[0]); FULL.append(message)
    log("stand-in agent", message.splitlines()[0])
    open(os.path.join(d, "stand_in_rule.py"), "w").write(RULE)
    if message.startswith("Your change was ACCEPTED"):
        open(os.path.join(d, "technique.py"), "w").write(RULE)
        open(os.path.join(d, "technique.md"), "w").write(
            "# Per-Toffoli temporary AND\nEach Toffoli becomes a 4-T AND into a fresh ancilla, measured out.\n"
            "**Applies when:** logical.qasm has 1-6 Toffolis.\n**Does not apply when:** no Toffolis or more than 6.\n")
        return
    if MODE[0] == "shared":
        return                                                  # change nothing
    rnd = len([c for c in CALLS if not c.startswith("Your change")])
    hook = {1: ["pad"], 2: [], 3: ["drop"]}[rnd]
    args = [os.path.join(d, "tket_start.qasm"), os.path.join(d, "circuit.qasm")] + hook
    os.system(f'cd "{d}" && CHECK_IN_VENV=1 "{sys.executable}" stand_in_rule.py ' + " ".join(f'"{x}"' for x in args))


agent.run_agent = stand_in
res = agent.main("cuccaro_2", rounds=3, arm="anc_isolated")
run = os.path.join(agent.HERE, res["folder"])
entries = sorted(glob.glob(os.path.join(agent.PLAYBOOK, "anc_isolated", "*", "entry.json")))
E = [json.load(open(f)) for f in entries]
best = QuantumCircuit.from_qasm_file(os.path.join(run, "best.qasm"))
r2 = [os.path.dirname(f) for f, e in zip(entries, E) if e["round"] == 2]
checks = {
    "logical.qasm + tket_start.qasm in run folder": all(os.path.exists(os.path.join(run, f)) for f in ("logical.qasm", "tket_start.qasm")),
    "check.py is the ancilla check (vs tket_start)": "tket_start.qasm" in open(os.path.join(run, "check.py")).read(),
    "verifier_anc.py copied, verifier_noanc.py not": os.path.exists(os.path.join(run, "verifier_anc.py"))
                                                      and not os.path.exists(os.path.join(run, "verifier_noanc.py")),
    "prompt is prompt_anc.md": CALLS[0] == open(os.path.join(agent.PROMPTS, "prompt_anc.md")).readline().strip(),
    "per-round best T = 18, 16, 16": [h["best_T"] for h in res["rounds"]] == [18, 16, 16],
    "2 cards (after r1 and r2)": sum(c.startswith("Your change") for c in CALLS) == 2,
    "card text has the ancilla OUT rule": any(m.startswith("Your change") and agent.CARD_ANC_OUT in m for m in FULL),
    "feedback says valid / ancillas": any("valid replacement for start.qasm" in m for m in FULL),
    "r2 replay (round start had ancillas) valid vs TKET, T 16": len(E) == 2 and all(e["replay"]["equivalent"] for e in E)
                                                                and [e["replay"]["T"] for e in E] == [16, 16],
    "valid_rules(anc_isolated) finds both": len(valid_rules(os.path.join(agent.PLAYBOOK, "anc_isolated"))) == 2,
    "final best.qasm verified vs TKET start, has ancillas": res["equivalent_to_tket"] and best.num_qubits > 6,
}
print(f"anc_isolated: TKET {res['T_tket']} -> {[h['best_T'] for h in res['rounds']]}, {res['ancillas_best']} ancillas")

MODE[0] = "shared"
os.makedirs(os.path.join(agent.PLAYBOOK, "anc_shared"))
shutil.copytree(r2[0], os.path.join(agent.PLAYBOOK, "anc_shared", os.path.basename(r2[0])))
res2 = agent.main("cuccaro_2", rounds=1, arm="anc_shared")
run2 = os.path.join(agent.HERE, res2["folder"])
start2 = QuantumCircuit.from_qasm_file(os.path.join(run2, "start.qasm"))
checks |= {
    "anc_shared stage: start = 16 T with ancillas": res2["T_start"] == 16 and start2.num_qubits > 6,
    "anc_shared prompt lists the stored rule": any("Rules from earlier runs" in m and os.path.basename(r2[0]) in m for m in FULL),
    "anc_shared final verified vs TKET start": res2["equivalent_to_tket"] and res2["T_best"] == 16,
}
print(f"anc_shared: TKET {res2['T_tket']} -> start {res2['T_start']} -> best {res2['T_best']}")
for k, ok in checks.items():
    print(f"{'OK ' if ok else 'BUG'} {k}")
print("\nALL PASS" if all(checks.values()) else "\nFAILURES")
