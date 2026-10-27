"""The two LLM roles. Both take an `ask(prompt) -> str` function, so the backend is swappable:
claude_cli() (default; run from a logged-in terminal) or any other callable (tests, other models).

    scout(ask, circuit, ...)      -> list of ideas (dicts)       "what could reduce the final T-count here?"
    implement(ask, idea, ...)     -> python source of one rule   "write rewrite(c) -> (Circuit, Req) for this idea"
"""
from __future__ import annotations

import json
import re
import subprocess

from . import circuit as _circuit_module
from . import verifier as _verifier_module
from .circuit import Circuit, counts, to_qasm

STAGES = {  # (before the playbook, after the playbook)
    ("L0", "rotation"): ("TKET FullPeepholeOptimise", "nothing (gridsynth only)"),
    ("L1", "rotation"): ("TKET FullPeepholeOptimise, then pyzx full_reduce (ZX phase folding)", "nothing (gridsynth only)"),
    ("L2", "rotation"): ("TKET FullPeepholeOptimise, then BQSKit Dyadic Phase Fixing with phase-kickback synthesis",
                         "nothing (gridsynth only)"),
    ("L0", "toffoli"): ("nothing (this is the logical ccx/ccz circuit)",
                        "TKET FullPeepholeOptimise on the unitary stretches between measurements"),
    ("L1", "toffoli"): ("nothing (this is the logical ccx/ccz circuit)",
                        "TKET FullPeepholeOptimise, then pyzx full_reduce (ZX phase folding), on the unitary stretches "
                        "between measurements"),
}
MAX_QASM_LINES = 400


def claude_cli(model: str = "sonnet", timeout: int = 180):
    """Backend using the Claude Code CLI subscription (`claude -p`, prompt on stdin)."""
    def ask(prompt: str) -> str:
        r = subprocess.run(["claude", "-p", "--model", model], input=prompt, capture_output=True, text=True,
                           timeout=timeout)
        if r.returncode != 0:                       # a non-zero exit is a failure even if stdout is non-empty
            raise RuntimeError(f"claude exited {r.returncode}: {(r.stderr or r.stdout)[-500:]}")
        return r.stdout
    return ask


def _context(arm: str, family: str, c: Circuit, eps_left: float, playbook: list, zinit=()) -> str:
    before, after = STAGES[(arm, family)]
    lines = to_qasm(c).splitlines()
    shown = "\n".join(lines[: MAX_QASM_LINES + 3])
    more = f"\n... ({len(lines) - MAX_QASM_LINES - 3} more lines not shown)" if len(lines) > MAX_QASM_LINES + 3 else ""
    rules = "\n".join(f"- {r['name']}: {r['doc']}" for r in playbook) or "(none yet)"
    anc = (f"Qubits {list(zinit)} are CLEAN ANCILLAS of this benchmark: they start in |0> and the circuit returns them "
           f"to |0>. The verifier knows this: a rewrite may rely on such a qubit being |0> before its first use "
           f"(e.g. to replace a compute/uncompute pair), never on anything else. In Python they are `c.zero_init`." if zinit else
           "This circuit has no declared clean ancillas; all its qubits may hold any input.")
    reprs = "\n".join(repr(g) for g in c.gates[:12])
    return f"""# Setting
Fault-tolerant compilation to Clifford+T. The ONLY metric is the T-count of the final circuit after every remaining
arbitrary rz is synthesized by gridsynth, at a fixed total error budget of 1e-3 (operator-norm distance). Toffoli
gates (ccx/ccz) left in the circuit count 7 T each. Lower is better. Extra qubits and measurements are allowed but
reported. Approximate rewrites are allowed: you may spend at most {eps_left:.2e} of error in total (measured by the
verifier), and every unit you spend is taken away from gridsynth, which then needs more T per rotation.

Before you see it, this circuit was processed by: {before}.
After your rules, the pipeline runs: {after}; then gridsynth. The T-count is measured at the very end, so a rewrite
only counts if it survives / helps those later stages (e.g. it must not just redo what they already do).
Do NOT re-implement those baselines (pyzx phase folding / full_reduce, TKET peephole, BQSKit dyadic phase fixing):
the goal is DIFFERENT mechanisms of similar strength that the baselines miss. Allowed tools: fresh ancilla qubits,
mid-circuit measurement with classically controlled corrections, exact rewrites, approximate rewrites within budget.
Known constructions from the literature are welcome if they apply.

# Rules already in the playbook (applied to this circuit before you see it)
{rules}

# The circuit ({counts(c)})
{anc}
```qasm
{shown}{more}
```
In Python (circuitevolve.circuit), its first gates are:
{reprs}
"""


def scout(ask, arm: str, family: str, c: Circuit, eps_left: float, playbook: list, n: int = 5, zinit=()) -> list:
    prompt = _context(arm, family, c, eps_left, playbook, zinit) + f"""
# Your task (scout)
Propose up to {n} concrete, distinct ideas that would reduce the final T-count of THIS circuit and that can be
written as a general Python rewrite rule (pattern match + replace, not hard-coded gate indices). For each give the
mechanism, where it applies here, which permissions it needs, and an honest estimate of the T saved.
Answer with ONLY a JSON list:
[{{"name": "snake_case_name", "idea": "...", "where": "...", "needs": "exact|approx|ancilla|measure (combine with +)",
  "expected_t_saving": 0}}]
"""
    text = ask(prompt)
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise ValueError(f"scout returned no JSON list: {text[:300]}")
    ideas = json.loads(m.group(0))
    return [i for i in ideas if isinstance(i, dict) and "name" in i][:n]


def _source(module) -> str:
    with open(module.__file__) as f:
        return f.read()


def implement(ask, arm: str, family: str, c: Circuit, eps_left: float, playbook: list, idea: dict,
              feedback: str = "", previous: str = "", zinit=()) -> str:
    retry = f"""
# Your previous attempt failed
```python
{previous}
```
Feedback: {feedback}
Fix it (or change approach if the idea cannot work).""" if previous else ""
    prompt = _context(arm, family, c, eps_left, playbook, zinit) + f"""
# Your task (implementer)
Implement this idea as ONE Python module:
{json.dumps(idea, indent=1)}

The module must define
    def rewrite(c: Circuit) -> tuple[Circuit, Req]
returning the rewritten circuit and the permissions it used. Requirements:
- Start with a docstring: what the rule does and why it is correct (2-6 lines).
- General: find the pattern anywhere it occurs in any circuit; return (c, Req()) unchanged when it does not occur.
- Do not mutate the input; build a new Circuit. New ancilla qubits get indices >= c.n (so Circuit(n=c.n + k, ...)),
  new classical bits indices >= c.nc. Deterministic, standard library + numpy only, must finish in < 30 s.
- Req(eps=..., ancillas=..., measure=...) must allow what the output uses: eps = the most error you allow it
  (<= {eps_left:.2e}), ancillas = number of extra qubits, measure = True if it adds measure/reset/cond gates.
- Imports: `from circuitevolve.circuit import Circuit, Gate` and `from circuitevolve.verifier import Req`.
The verifier simulates every changed block and rejects anything that is not equivalent (within eps). The rule is
accepted only if it verifies AND lowers the final T-count of this circuit.

# API: circuitevolve/circuit.py (complete source)
```python
{_source(_circuit_module)}
```
# Verifier semantics (docstring of circuitevolve/verifier.py)
{_verifier_module.__doc__}{retry}

Answer with ONLY the module in one ```python block, no text before or after it.
"""
    text = ask(prompt)
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
    if not m:
        raise ValueError(f"implementer returned no python block: {text[:300]}")
    return m.group(1)
