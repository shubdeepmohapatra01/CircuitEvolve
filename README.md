# CircuitEvolve v3: a verified rule book for circuit optimization

An LLM agent looks at a circuit, recognizes an optimization it knows (from the literature or its training),
and writes it down as a **rule**: a small Python file with a `trigger` (where does it apply?) and an `apply`
(what does the circuit become?). Code, not the LLM, applies the rule everywhere it matches. A **frozen judge**
verifies every single application and measures the cost. Rules that pass **admission** go into a rule book;
rules that fail are kept with the reason. The LLM never edits a circuit by hand and never decides whether
something is correct.

```
            circuit + history of earlier attempts
                          |
        scout (LLM)  ->  rule card (identity, why it is correct, where it fires, expected saving)
                          |
  implementer (LLM)  ->  v3/rules/candidates/<name>.py   (may only run tools/test_rule.py)
                          |
   admission (code)  ->  full suite, every application verified by the frozen judge
                          |
          accepted/ | rejected/ | never_fires/   (+ reason JSON; superseded rules -> retired/)
```

## Setup

```bash
python3.11 -m venv .venv            # must be at the repo root (.venv/); the tools look for it there
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q v3/tests     # 26 pass, 1 skipped (CV-DV control, needs a CV-DV setup)
```

Run everything from the repo root with `.venv/bin/python`.

## Benchmarks (`benchmarks/`)

The ten DV circuits the results are reported on, as QASM files named by label (byte-identical to the suite
inputs in `v3/suite/inputs/`, which the judge loads):

| Folder | Circuits | What the file is |
|---|---|---|
| `dv_angle/` | qft_8, qpe_8, hhl_8, qae_13, tfim_6 | Clifford+Rz, already TKET FullPeepholeOptimise output (the common start for every method) |
| `dv_reconstruction/logical/` | adder_6, adder_8, mult_4, mcx_10, modred_21 | Toffoli level (ccx / ccz + Clifford), from the Nam arithmetic suite (rc_adder_6, adder_8, gf2^4_mult, barenco_tof_10, mod_red_21) |
| `dv_reconstruction/cliffordt/` | same five | the suite's own Clifford+T version (7 T per Toffoli), the input for BQSKit and pyzx |
| `cvdv/` | five `*_small` Hamiltonians + IR | CV-DV suite (not used in the reported results) |

## Baselines

The frozen numbers used in every comparison are in `v3/baselines/baselines.csv` (eps 1e-3 and 1e-5 for angle
circuits; reconstruction circuits are exact). Methods: TKET, pyzx, BQSKit-FT, BQSKit-DPF.

TKET and pyzx can be recomputed from the benchmark files:

```bash
.venv/bin/python benchmarks/run_baselines.py              # all ten, eps 1e-3; prints them next to the frozen numbers
.venv/bin/python benchmarks/run_baselines.py qft_8 mult_4
```

It reproduces the frozen TKET and pyzx T-counts exactly. BQSKit-FT and BQSKit-DPF come from the bqskit-ft research
branch (Dyadic Phase Fixing, Kalloor et al., arXiv:2606.05397) with TKET pre-optimization; that setup is not part
of this repo, so those two columns are used as recorded. On the reconstruction circuits BQSKit-FT/DPF return the
Clifford+T input unchanged (399, 77, 112, 224, 119 T).

T-count convention (all methods, and ours): every Rz that is not a multiple of pi/4 is synthesized by gridsynth at
eps_rz = eps / N_Rz, so the total synthesis error is at most eps; pi/4 multiples are exact.

## How it works

### Rules

A rule is a Python file that defines `RULE = Rule(...)` (`v3/api/__init__.py`):

| Field | Meaning |
|---|---|
| `name` | identifier, also the file name |
| `domain` | `dv` (or `cvdv`) |
| `kind` | `rewrite` (local), `procedure` (non-local pass), `reconstruction` (re-synthesize a subroutine), `resource` (uses ancillas / measurement as a resource) |
| `contract` | `exact` (same unitary up to global phase), `approx` (within an error allowance that is charged to the budget), `relaxed` (same function with clean ancillas returned to 0 and measurement-based uncompute; not unitary-preserving) |
| `source`, `idea` | where the identity comes from and why it is correct |
| `trigger(circuit)` | list of matches, pure and deterministic |
| `apply(circuit, match)` | the new circuit, pure and deterministic |

A rule may import only the standard library, numpy, scipy, sympy and `v3.api` (circuit access, rotations,
Pauli conjugation tables, Toffoli-level IR helpers). It may not call pyzx, TKET or BQSKit. A short complete example
is `v3/rules/handwritten/same_pauli_merge.py`.

### The judge (`v3/judge/`, frozen)

- **DV verification** wraps exact, tested code in `circuitevolve/`: an exact check over the ring Z[omega]/sqrt2^k
  (omega = e^{i pi/4}) whenever both sides are Clifford+T (floating point never accepts a Clifford+T candidate);
  otherwise a dense operator-norm distance; for `relaxed` rules a branch-wise check of every basis input and
  measurement outcome, with ancillas starting and ending in |0>.
- Exhaustive above 2^14 basis inputs is too expensive, and some relaxed circuits have too many measurement
  branches; those checks are sampled. Results that rely on a sampled check are marked "sampled check, not a
  proof".
- **Cost**: T-count in the convention above, plus rotations, CNOTs, qubits.
- `v3/judge/FROZEN.sha256` lists the hashes of the judge, the upstream modules it wraps, the suite inputs and the
  baselines. Every tool checks it at start and refuses to run if anything changed.

### The runner (`v3/runner.py`)

`optimize(circuit, book, eps)` applies a book of rules:

- Each application is verified on its **window** (the changed middle of the circuit, re-indexed to the qubits it
  touches), and kept only if the cost drops.
- After a rule stops firing in a pass, the **whole circuit** is checked once against the original input. If that
  fails, the runner bisects to the first bad application, reverts to before it, and stops using the rule.
- **Error ledger**: total eps per circuit; eps/2 for approximate rewrites (each charged its measured distance),
  eps/2 for the final gridsynth synthesis.
- **Rule order**: reconstruction rules first; within a group, rules ordered per circuit by their solo gain, so a
  weaker rule cannot consume matches a stronger one needs. Both that order and the book order are run and the
  better result is kept.
- Per-circuit time limit 300 s.

### Admission (`v3/tools/admit.py`, `v3/tools/evaluate.py`)

The candidate is added to the current book and run on every DV circuit. In this order:

1. **static**: imports only what is allowed, defines a valid `RULE`;
2. **verification**: any failed application anywhere rejects the rule, so a wrong rule is rejected for being
   wrong, not for not improving;
3. **never fires**: a correct rule whose trigger matches nothing is filed under `never_fires/`, not rejected;
4. **runtime** below the limit on every circuit;
5. **improvement**: it must lower the T-count on at least one circuit beyond the current book;
6. **superseding**: if it fires wherever an accepted rule fires and does at least as well everywhere and
   strictly better somewhere, the old rule moves to `retired/`.

### The agent loop (`v3/agent/`)

`v3/agent/run.py` runs the P2 experiment: round-robin over the circuits with a per-circuit attempt budget. One
attempt = scout call -> implementer call -> admission, with one retry for implementation-level failures and one
for idea-level failures. The scout sees the circuit, its costs, the baselines and the history of earlier
attempts (estimated vs measured gain, and why). The implementer can only write under `v3/rules/candidates/` and
only run `test_rule`; a hash snapshot of `v3/` before and after every call stops the run if anything else changed.
Results are written after every attempt, and the run can be resumed.

It drives an agent command-line tool in non-interactive mode, configured by environment variables:

```bash
export V3_AGENT_CLI=<agent CLI command>    # called as: $V3_AGENT_CLI -p <prompt> --model <id> --output-format json ...
export V3_SCOUT_MODEL=<model id>
export V3_IMPL_MODEL=<model id>
.venv/bin/python -m v3.agent.run [--max-attempts N]      # start or resume; touch v3/results/p2/STOP to stop
```

The prompts are in `v3/agent/prompts/`, the API description the implementer sees in `v3/agent/api.md`.

## Small experiments

**Run the current book on a circuit**

```python
from v3.judge import dv as J
from v3 import runner as R
from v3.tools.evaluate import accepted_book

res = R.optimize(J.load("qft_8"), accepted_book(), 1e-3)
print(res.cost["t_count"], res.summary())
```

**Write and test your own rule**

```bash
cp v3/rules/handwritten/same_pauli_merge.py v3/rules/candidates/my_rule.py     # then edit name / trigger / apply
.venv/bin/python -m v3.tools.test_rule v3/rules/candidates/my_rule.py --target qft_8   # read-only JSON report
.venv/bin/python -m v3.tools.admit v3/rules/candidates/my_rule.py --eps 1e-3           # decides and moves the file
```

`test_rule` runs the target plus the small circuits (qft_8, adder_6, mult_4, modred_21) and stops at the first
verification failure; it allows 5 calls per file (counter in `v3/results/test_rule_calls.json`). `admit` runs the
full suite and changes the book, so experiment on your own branch.

**Regenerate figures and summary**

```bash
.venv/bin/python -m v3.report.ours --reason "my run"   # current book on all DV circuits -> v3/results/p2/ours.jsonl
.venv/bin/python -m v3.report.p2_report                # v3/report/figures/*.png and v3/results/p2/SUMMARY.md
```

## Results (P2, eps 1e-3)

36 agent attempts: 8 rules admitted (2 later superseded, 6 in the book), 13 rejected (9 of them on the runtime
limit, 4 by verification), 13 never fired, 2 produced no rule card. Full summary: `v3/results/p2/SUMMARY.md`;
figures: `v3/report/figures/p2_*.png`.

| Circuit | Ours (T) | Best baseline (T) | Check |
|---|---|---|---|
| tfim_6 | 3354 | TKET 8560 | proof |
| mult_4 | 36 | pyzx 68 | relaxed, sampled |
| modred_21 | 68 | pyzx 73 | relaxed, sampled |
| adder_6 | 44 | pyzx 47 | relaxed, sampled |
| qae_13 | 4526 | pyzx 4527 | sampled |
| qft_8 | 1583 | pyzx 1577 | proof |
| adder_8 | 216 | pyzx 173 | relaxed, sampled |
| mcx_10 | 128 | pyzx 100 | relaxed, sampled |
| qpe_8 | 11485 | BQSKit-DPF 8020 | proof |
| hhl_8 | 28509 | BQSKit-DPF 19443 | proof |

Relaxed results use one extra clean ancilla and measurement-based uncompute.

## Layout

| Path | What it is |
|---|---|
| `benchmarks/` | benchmark QASM files and `run_baselines.py` |
| `v3/judge/` | frozen judge (`dv.py`), frozen-file check, CV-DV judge |
| `v3/suite/` | `manifest.json` and the inputs the judge loads |
| `v3/baselines/` | frozen `baselines.csv`; BQSKit run records for the reconstruction circuits |
| `v3/api/` | what rules may import |
| `v3/runner.py` | applies a book to a circuit |
| `v3/tools/` | `test_rule`, `admit`, `evaluate`, `empty_book`, `progress` |
| `v3/rules/` | `accepted/` (the book), `retired/`, `rejected/`, `never_fires/`, `handwritten/` (controls, not in the book), `BOOK.md` |
| `v3/agent/` | agent loop, prompts, API notes |
| `v3/report/` | figure and summary scripts, figures |
| `v3/results/` | P0 gate, P1 reference, P2 attempts / tokens / book runs / summary |
| `circuitevolve/`, `cvdv/src/cvdv/` | upstream verification and cost modules the judge wraps (frozen) |

## Ground rules

- Never edit the judge, the suite inputs, the baselines or the manifest (hash-checked).
- Results are append-only: one JSON line per event; a corrected table is a new file.
- Never compare numbers at different eps. Never report a relaxed result as unitary-preserving (hatched in figures).
- Fitness is lexicographic: correctness first, then T-count, then qubits.
