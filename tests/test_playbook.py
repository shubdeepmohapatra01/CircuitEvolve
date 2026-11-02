"""Playbook machinery with a stand-in agent (no Claude Code call). Run: python tests/test_playbook.py
Output goes to test_out/<time>/ (runs/, playbook/); the agent logs to logs/agent_<run>.md as usual.
The stand-in copies examples/givens_rule's tfim_4 output into circuit.qasm (round 2; round 1 changes nothing) and, when
asked for a card, copies CARD_FROM's technique.md / technique.py. playbook/shared/ is seeded with that entry,
a no-gain identity rule, a rule that adds a qubit, and an entry whose replay was not equivalent (must be skipped).
"""
import json, os, shutil, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "verifier")]
from qiskit import QuantumCircuit
import agent
from pipeline import HERE, Log, load, t_count, tket

RULE = os.path.join(HERE, "examples", "givens_rule")        # the one playbook entry that ships
OUT = os.path.join(HERE, "test_out", time.strftime("%Y%m%d_%H%M%S"))
agent.RUNS, agent.PLAYBOOK = os.path.join(OUT, "runs"), os.path.join(OUT, "playbook")
READ = "import sys\nfrom qiskit import QuantumCircuit, qasm2\nqc = QuantumCircuit.from_qasm_file(sys.argv[1])\n"
RULES = {"identity": (READ + "qasm2.dump(qc, sys.argv[2])\n", True),
         "ancilla": (READ + "b = QuantumCircuit(qc.num_qubits + 1)\nb.compose(qc, range(qc.num_qubits), inplace=True)\n"
                     "qasm2.dump(b, sys.argv[2])\n", True),
         "not_equivalent": (READ + "qasm2.dump(qc, sys.argv[2])\n", False)}
MESSAGES, CARD_FROM, FAILED = [], RULE, []


def stand_in(d, log, message, session, first):
    MESSAGES.append(message)
    log("stand-in agent", message.splitlines()[0])
    if message.startswith("Your change was ACCEPTED"):
        for f in ("technique.md", "technique.py"):
            shutil.copy(os.path.join(CARD_FROM, f), d)
    elif not first:
        shutil.copy(os.path.join(RULE, "tfim_4_out.qasm"), os.path.join(d, "circuit.qasm"))


def check(what, ok):
    print(("PASS " if ok else "FAIL ") + what, flush=True)
    FAILED.extend([] if ok else [what])


def seed():
    shared = os.path.join(agent.PLAYBOOK, "shared")
    shutil.copytree(RULE, os.path.join(shared, "givens_rule"))      # copy2 keeps the old mtime: tried first
    for name, (code, equivalent) in RULES.items():
        e = os.path.join(shared, name); os.makedirs(e); time.sleep(0.05)
        open(os.path.join(e, "technique.py"), "w").write(code)
        open(os.path.join(e, "technique.md"), "w").write(f"# {name} rule\n**Applies when:** test fixture\n")
        json.dump(dict(circuit="fixture", T_before=10, T_after=5, replay=dict(equivalent=equivalent, T=5)),
                  open(os.path.join(e, "entry.json"), "w"))


def tries(res):
    lines = open(os.path.join(HERE, "logs", f"agent_{os.path.basename(res['folder'])}.jsonl")).read().splitlines()
    return [x for x in map(json.loads, lines) if x["stage"] == "playbook try"]


if __name__ == "__main__":
    agent.run_agent = stand_in
    seed()
    iso = agent.main("tfim_4", 2, "isolated"); print(json.dumps(iso))
    d = os.path.join(HERE, iso["folder"])
    check("isolated: starts from TKET 5280, never reads playbook", iso["T_start"] == 5280 and
          not os.path.exists(os.path.join(d, "playbook_stage")) and "Rules from earlier" not in MESSAGES[0])
    check("isolated: round 1 rejected, round 2 accepted, best 1338 = TKET-equivalent",
          [h["best_T"] for h in iso["rounds"]] == [5280, 1338] and iso["T_best"] == 1338 and iso["equivalent_to_tket"])
    (ent,) = [os.path.join(agent.PLAYBOOK, "isolated", x) for x in os.listdir(os.path.join(agent.PLAYBOOK, "isolated"))]
    e = json.load(open(os.path.join(ent, "entry.json"))); print(json.dumps({k: v for k, v in e.items() if k != "card"}))
    check("isolated: entry holds only the 5 lean files", sorted(os.listdir(ent)) ==
          ["after.qasm", "before.qasm", "entry.json", "technique.md", "technique.py"])
    check("isolated: entry step 5280 -> 1338, round 2, replay equivalent T 1338 same qubits",
          (e["T_before"], e["T_after"], e["round"], e["arm"]) == (5280, 1338, 2, "isolated") and e["replay"]["ran"]
          and e["replay"]["equivalent"] and e["replay"]["T"] == 1338 and e["replay"]["qubits_same"])

    MESSAGES.clear()
    sh = agent.main("tfim_4", 2, "shared"); print(json.dumps(sh))
    d, tr = os.path.join(HERE, sh["folder"]), tries(sh)
    for t in tr:
        print("  try:", t["rule"], "kept" if t["kept"] else "not kept", t["T_before"], "->", t["T"], "|", t["reason"][:70])
    check("shared: 3 valid rules tried, not_equivalent entry skipped",
          [t["rule"] for t in tr] == ["givens_rule", "identity", "ancilla"])
    check("shared: the shipped rule reproduces tfim_4 5280 -> 1338 and is kept", tr[0]["kept"] and
          (tr[0]["T_before"], tr[0]["T"]) == (5280, 1338))
    check("shared: identity (no gain) and ancilla (qubit count) rejected", not tr[1]["kept"] and "not below" in
          tr[1]["reason"] and not tr[2]["kept"] and "qubit count changed" in tr[2]["reason"])
    check("shared: agent starts from 1338, final best verified vs TKET start", sh["T_tket"] == 5280 and
          sh["T_start"] == 1338 and t_count(QuantumCircuit.from_qasm_file(os.path.join(d, "start.qasm"))) == 1338
          and sh["equivalent_to_tket"])
    check("shared: prompt lists the rules, cards copied", "Rules from earlier runs" in MESSAGES[0] and
          "kept, T 5280 -> 1338" in MESSAGES[0] and sorted(os.listdir(os.path.join(d, "playbook_cards"))) ==
          ["ancilla", "givens_rule", "identity"] and os.listdir(os.path.join(d, "playbook_cards", "identity"))
          and set(os.listdir(os.path.join(d, "playbook_cards", "givens_rule"))) == {"technique.md", "technique.py"})
    print("shared prompt section:" + MESSAGES[0].split("## Rules from earlier runs (playbook)")[1])

    CARD_FROM = os.path.join(agent.PLAYBOOK, "shared", "identity")       # replay input must be the round start
    tk, mid = tket(load(agent.find_circuit("tfim_4"))), QuantumCircuit.from_qasm_file(os.path.join(RULE, "tfim_4_out.qasm"))
    d = agent.workspace("tfim_4", "isolated", tk)                        # a scratch run folder for the call below
    agent.record_technique(d, Log(f"agent_{os.path.basename(d)}"), "s", "tfim_4", "isolated", 2, mid, mid, 1338, 1338)
    e = json.load(open(os.path.join(agent.PLAYBOOK, "isolated", f"{os.path.basename(d)}_r2", "entry.json")))
    check("replay runs on the round-start circuit (identity -> 1338), not start.qasm (5280)", e["replay"]["T"] == 1338)
    print(f"{len(FAILED)} failed" if FAILED else "ALL PASSED", "| output in", os.path.relpath(OUT, HERE))
    sys.exit(1 if FAILED else 0)
