"""Evolvable optimizer programs (OpenEvolve / AlphaEvolve style) for Clifford+T circuit compilation.

An optimizer PROGRAM is Python source defining `optimize(circ, tools, budget)`. It may only call the fixed
toolbox `tools` (toolbox.py) and pure-Python control flow (checked statically, sandbox.py). Programs run in
a subprocess with time and memory limits (sandbox.run_program); the PARENT verifies every output against
the ORIGINAL qseed circuit with the frozen whole-circuit check (blocks/verify_block.circuit_check) and the
error accounting (evaluate.py). An invalid output gives the program no fitness.

Modules
  split.py     development / evaluation split (benchmarks/split.json); eval circuits are refused
  toolbox.py   the toolbox object handed to programs (runs in the child process)
  sandbox.py   static AST checks, restricted exec, subprocess runner with wall-time and RSS limits
  child.py     subprocess entry point
  evaluate.py  parent-side verification, cost, fitness, evaluation cache
  programs.py  seed program and the classical-control program generator
  evolve.py    MAP-Elites / island evolution loop with LLM proposals (rewrites or SEARCH/REPLACE diffs)
  control.py   classical control: random and greedy search over pass sequences at matched evaluations
See docs/EVOLVE_OPT.md.
"""
TOOLBOX_VERSION = "tb-v1"
ERROR_BUDGET = 1e-6          # total per-circuit error budget (operator norm, phase-aligned)
EPS_RZ = 1e-9                # gridsynth eps per synthesised rotation (fixed: same as the best-classical baseline)
NUMERIC_SLACK = 1e-8         # reserved for floating-point error of exact passes (pyzx Fraction angles ~1e-11)
