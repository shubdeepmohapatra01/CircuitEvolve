# v2 held-out evaluation (track "Evaluation")

Protocol for evaluating the frozen v2 artifacts on the HELD-OUT circuits of split `v2-nam-arith-1`
(`benchmarks/nam_arith/SPLIT.md`). Results: `results/v2/eval/EVAL_REPORT.md`, `eval_results.csv`, `eval_figure.png`.

## What is evaluated (no LLM arms)

The DEV phase gave null results for both LLM arms (tier 1: LLM never beat the deterministic control; tier 2: both
primary libraries froze at v0 = empty). By user decision the held-out evaluation runs WITHOUT LLM arms:

| arm | what | contract |
|---|---|---|
| `tier1_control` exact / relaxed | frozen deterministic control `circuitevolve/v2/tier1/control.py`, 8 evaluations (`ORDER[:8]`, the DEV budget rule) | exact = unitary-preserving; relaxed = clean ancillas + measurement + declared zero-init promise |
| `tier2_final` | frozen primary library `results/v2/tier2/library_final.json` (v0, 0 rules) on the best classical exact Clifford+T output | unitary-preserving |
| `tier2_lexsec` | secondary control library `library_lex_secondary_control.json` (30 gate-count rules, dT = 0) | unitary-preserving |
| `tier1+tier2_*` | both libraries on the tier-1 control's exact output (tier 2 is unitary-only, so not on relaxed outputs) | unitary-preserving |
| `best_classical_ours` | lowest verified T of our pyzx_fr / tket_fpo / tket_fpo_logical runs and the Nam Light file (`results/v2/baselines_new.csv`) | reused, not recomputed |
| `best_published` | lowest KvdW2020 / Nam2018 table value (published, not run by us) | reused |

## Freeze rule

Before every circuit `experiments/v2_eval_heldout.py` re-hashes every file listed in `results/v2/tier1/FROZEN.md`,
checks the frozen verifier digest, and loads both tier-2 libraries with exact re-verification of every rule and a
content-hash check against the `.sha256` files. Any mismatch aborts the circuit. Nothing in `circuitevolve/v2/tier1`,
`tier2`, the prompts, cards, toolbox or libraries was changed.

## Verification

Every output is verified with `circuitevolve.v2.verify` against the ccx-normalized LOGICAL circuit (normalization itself
checked against the original QASM first), with the frozen limits `compile.DEFAULT_LIMITS`. The verdict mode and the
`certified` flag are recorded; every sampled verdict is re-run with sampling seeds 1 and 2 (the control itself is
deterministic, so seeds apply to the verifier). A time-limit outcome is recorded as inconclusive, never as a pass.

## Skips and blocks

* `shor_14`, `shor_16`: rotation-dominated; tier1-toolbox-v1 has no rotation route (as `shor_12` on DEV). Not run.
* `qcla_adder_10`, `qcla_com_7`: blocked by verifier coverage: the recognizer normalization keeps unfused h/ccz gates,
  the reference is then not permutation-like and n > 14 makes the exact check infeasible. Stopped and reported
  (tier-1 code is frozen and may not be changed during evaluation).

## Reproduce

    .venv/bin/python experiments/v2_eval_heldout.py --circuit <name> [--tag eval_v1]   # one process per circuit
    .venv/bin/python experiments/v2_eval_report.py [--tag eval_v1]                      # CSV + EVAL_REPORT.md
    python experiments/v2_eval_figure.py                                                # figure (matplotlib)

Run `eval_v1` used `xargs -P 6` over the 22 held-out names (wall time ~70 min on a 12-core laptop).
