"""Reference rule for tests (hand-written, NOT part of any playbook): a Toffoli h-ccz-h / ccx onto a clean ancilla t
that is still |0>, later undone by the same Toffoli while t was only used as a control in between, becomes
Gidney's 4-T AND (compute) + measurement-based uncompute (0 T)."""
from circuitevolve.circuit import Circuit, Gate
from circuitevolve.verifier import Req

def _and(a, b, t):
    return [Gate("h", (t,)), Gate("t", (t,)), Gate("cx", (a, t)), Gate("cx", (b, t)), Gate("cx", (t, a)),
            Gate("cx", (t, b)), Gate("tdg", (a,)), Gate("tdg", (b,)), Gate("t", (t,)), Gate("cx", (t, a)),
            Gate("cx", (t, b)), Gate("h", (t,)), Gate("s", (t,))]

def _toffolis(gates):
    """Yield (start, end, a, b, t) for ccx(a,b,t) or h t; ccz(..t..); h t."""
    i = 0
    while i < len(gates):
        g = gates[i]
        if g.name == "ccx" and g.cond is None:
            yield i, i + 1, *g.qubits
        elif g.name == "h" and i + 2 < len(gates) and gates[i+1].name == "ccz" and g.qubits[0] in gates[i+1].qubits \
                and gates[i+2].name == "h" and gates[i+2].qubits == g.qubits:
            t = g.qubits[0]; a, b = [q for q in gates[i+1].qubits if q != t]
            yield i, i + 3, a, b, t
            i += 2
        i += 1

def rewrite(c):
    gates, zinit = c.gates, set(c.zero_init)
    tofs = list(_toffolis(gates))
    touched_before = set()
    repl, nc = {}, c.nc
    for k, (s, e, a, b, t) in enumerate(tofs):
        if t not in zinit or any(t in g.qubits for g in gates[:s]):
            continue
        for (s2, e2, a2, b2, t2) in tofs[k+1:]:
            if t2 == t and {a2, b2} == {a, b}:
                mid = gates[e:s2]
                # in between t may only be a control (not target of anything that changes it); a,b untouched as targets
                ok = all(not (t in g.qubits and (g.name not in ("ccx", "cx", "ccz") or (g.name in ("ccx","cx") and g.qubits[-1] == t))) for g in mid)
                ok = ok and all(not ((a in g.qubits or b in g.qubits) and g.name in ("h", "x", "ccx", "cx") and g.qubits[-1] in (a, b)) for g in mid)
                if ok and s not in repl and s2 not in repl:
                    repl[s] = (e, _and(a, b, t))
                    repl[s2] = (e2, [Gate("h", (t,)), Gate("measure", (t,), cbit=nc), Gate("cz", (a, b), cond=nc), Gate("x", (t,), cond=nc)])
                    nc += 1
                break
    out, i = [], 0
    while i < len(gates):
        if i in repl:
            e, seq = repl[i]; out += seq; i = e
        else:
            out.append(gates[i]); i += 1
    return Circuit(c.n, out, nc), Req(measure=nc > c.nc)
