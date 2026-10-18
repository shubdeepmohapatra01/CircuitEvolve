# Tier 1 - compilation strategy (design + status)

**Question.** Given a LOGICAL circuit (Toffoli level), can an LLM pick or write better constructions per subroutine
than the classical optimizers, with every result verified against the logical circuit?

## Pipeline (`circuitevolve/v2/tier1/`)

| step | file | what it does |
|---|---|---|
| recognize | `recognize.py` | QASM -> ir.Circuit (literal parsing); `normalize` fuses `h t; ccz(..t..); h t` into ccx; `summarize` lists qubit roles (declared zero-init from the manifest, first touch, restored-to-0 by classical bit simulation), Toffolis `T<k>`, Toffoli pairs `P<k>` (same gate repeated with controls unchanged; class clean / mirror / controls_fixed), multi-controlled-X cascades `M<k>`, repeated blocks, rotation content. Deterministic. |
| plan | `plan.py` | JSON compilation plan: decisions `{element, route}` over the toolbox `toffoli_7T, relative_phase_toffoli, temporary_and (direct or via_ancilla), clean_and, jones_toffoli, ancilla_mcx, barenco_mcx, custom` + `global_pass` in {pyzx, tket, none, pyzx_then_tket}. Custom constructions in a literal gate DSL (h s sdg t tdg x z cx cz, measure q -> c, if(c) gate; fresh ancillas a<k>). json + regex only; never exec/eval. |
| compile | `compile.py` | executes the plan with the frozen IR gadgets (`and_compute` / `and_uncompute`), RCCX = qiskit rccx; ancilla pool with reuse; global pass applied per measurement-free segment, kept only where it lowers T (TKET outputs with non-pi/4 rotations are discarded). `evaluate` = parse + compile + `v2.verify` + `v2.metric`. |
| verify | `circuitevolve/v2/verify.py` | mode `exact` if no measurement / extra qubit / zero-init promise, else `relaxed` with `zero_qubits` = the declared zero-init qubits the routes rely on. Reference = normalized logical circuit (checked against the original QASM). |
| arms | `loop.py`, `control.py`, `prompt.py` | LLM arm (prompt = summary + toolbox + card INDEX + 3 selected cards + requested cards + best plan per leaderboard + last 4 results; targets alternate relaxed/exact) and the NO-LLM control (route sets V1 spec / V2 max_relaxed / V3 max_exact / V4 plain x global passes) at the same evaluation budget. |

`clean_and` (a compute-only Gidney AND into a declared-zero target) is an addition to the toolbox in the task brief;
it is a relaxed route because it relies on the zero-init promise.

## Status (2026-10-14, run `dev_v1`)

16 DEV circuits x 8 LLM calls (claude-sonnet-5, 905k input + 58k output tokens). LLM = control in exact mode
(16/16) and relaxed mode (13/16; worse on 2, no valid plan on 1). Relaxed T below the best unitary-preserving
classical T on 10/16 (Gidney / Jones constructions, also found by the control). The LLM never used the custom DSL.
Report: `results/v2/tier1/DEV_REPORT.md`; frozen prompt + toolbox: `results/v2/tier1/FROZEN.md`.

Run: platform kernel (env circuitevolve-dev) `from experiments.v2_tier1_dev import run_api; run_api(host, tag=...)`,
then `.venv/bin/python experiments/v2_tier1_report.py <tag>`. Tests: `tests/v2/test_tier1.py`.
