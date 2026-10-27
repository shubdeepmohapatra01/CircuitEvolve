# CircuitEvolve v4 — how to run it

The build plan is `V4_README.md`. What each phase actually delivered, with measurements, is
`BUILD_LOG.md`. What the floor guarantee still needs, and why, is `SCOPE.md`.

v4 **imports** `v3/` and `circuitevolve/`; it does not fork them. No frozen file was edited: `v3`'s
`FROZEN.sha256` still verifies, and `CLAUDE.md` invariant 4 holds. The one capability v3's verifier
lacked (ancillas together with continuous rotations) is new code in `v4/judge/kraus.py` that composes the
frozen primitives.

---

## Run the training loop

```bash
cd /Users/shubdeepmohapatra/Documents/CircuitEvolve
caffeinate -dimsu &                       # keep the machine awake; lid must stay OPEN

# 0. check the harness is intact and the gates still pass  (~3 min)
.venv/bin/python -m pytest v4/tests -q
.venv/bin/python -m v4.tools.planted_gate          # must print 4/4 correct -> PASS

# 1. look at what the scout will be shown, without spending anything
.venv/bin/python -m v4.agent.run --dry-run --tag dry

# 2. run it.  `claude` must be logged in in this terminal.
.venv/bin/python -m v4.agent.run --tag run1 --budget 60 --loops 4

# stop it cleanly after the attempt in flight:
touch v4/results/run1/STOP
```

`--budget` is **one global pool of attempts**, not a per-circuit quota — that is the point of section 5.
`--loops` bounds how many times the loop passes over `CIRCUIT_ORDER`. Re-running the same `--tag`
continues in the same directory (`attempts.jsonl` is append-only); start a new `--tag` for a clean run.

While it runs:

```bash
tail -f v4/results/run1/attempts.jsonl | .venv/bin/python -c 'import sys,json
for l in sys.stdin:
    r=json.loads(l); print(f"{r[\"label\"]:<11} {r[\"kind\"]:<14} {r[\"level\"] or \"-\":<14} T={r[\"current_t\"]}")'
cat v4/results/run1/tokens.jsonl | .venv/bin/python -c 'import sys,json
rows=[json.loads(l) for l in sys.stdin]; print(f"{len(rows)} LLM calls, ${sum(r.get(\"cost_usd\") or 0):.2f}")'
```

Then report:

```bash
.venv/bin/python -m v4.report --tag p8        # per-circuit vs 4 baselines, hatched on resource_class
cat v4/results/p8/RESULTS.md
```

## The other commands

| command | what it does |
|---|---|
| `python -m v4.tools.sweep --tag <t>` | run the book over the whole DV suite, one JSON line per circuit |
| `python -m v4.tools.floor_gate --tag <t>` | the floor tier ALONE vs the best baseline, per circuit |
| `python -m v4.tools.planted_gate` | the P5 planted-bug gate (4 controls, 4 known-correct decisions) |
| `python -m v4.tools.test_rule <file> --target <c>` | what the implementer agent is allowed to run |
| `python -m v4.tools.reevaluate --tag <t>` | re-run v3's rejected rules under v4's verifier, no clock |
| `python -m v4.report --tag <t>` | the results table, CSV and figures |

## What the loop does, in one paragraph

The book starts as the **floor tier** — reimplementations of the baselines, in Python over `v4.api`, which
never retire. For each circuit in a fixed `CIRCUIT_ORDER`, the book's own result is fetched from a memo
keyed on `(book digest, circuit, eps)` so it is computed once ever. A **scout** sees that residual
circuit, its **lever fingerprint** (how much headroom each of four levers has LEFT, and which baseline
consumed it), the baselines, the book and the circuit's own history, and returns one rule card. A free
**prefilter** rejects cards whose lever has no headroom, that overclaim, or that propose to improve
rotation synthesis. Otherwise an **implementer** writes the rule as a Python file over `v4.api`, and it is
applied to the cached residual so that only its own applications are verified. If it fires, verifies and
lowers T, the **admission** re-run re-measures the whole suite under
`min(book_order, gain_order, best_single_rule)` and refuses anything that raises T anywhere or lowers it
nowhere. The book is one mutable object handed along the chain, so the next circuit sees whatever the
previous one left; a rule with no accepted application for two global loops retires, unless it is floor.

## Where things are

```
v4/
  loop.py        the training loop (V4_README 5)        agent/run.py   the LLM driver
  runner.py      applies a book to a circuit            agent/scout.md, implementer.md, api.md
  book.py        tiers, credit, retirement              fingerprint.py  lever headroom + prefilter
  baselines.py   TKET / pyzx / BQSKit-FT / DPF Synth     ledger.py       the shared error budget
  contracts.py   error_class x resource_class            caps.py         the opcode budget
  memo.py        optimize_memo + the residual cache      report.py       P8 tables and figures
  judge/   frozen.py (once per process), dv.py (caches), certify.py (certificates), kraus.py (P5)
  api/     what a rule may import: dv pauli phasepoly blocks sim refit angles budget fermion
  rules/   floor/ (never retired) accepted/ rejected/ never_fires/ retired/ candidates/ handwritten/
  tests/   test_p0.py test_p3.py test_p4.py test_p7.py
  results/ append-only
```

## Rules of the road

* **Results are append-only.** Add files under `results/`; never edit a row.
* **A rule may import** stdlib, numpy, scipy, sympy and `v4.api` — nothing else. `book.static_check`
  enforces it before a rule is ever executed.
* **Verification is never capped on a clock.** Rule code is capped on opcodes; LLM subprocesses are
  capped on wall clock and dollars. A timed-out agent call retries; a timed-out verification would throw
  away correct work, which is what v3's 300 s limit did to two of its best rules.
* **`eps = 1e-3` is the primary budget** for every comparison. 1e-5 is a secondary sweep. Never compare
  across eps.
