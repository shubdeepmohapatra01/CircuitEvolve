# CircuitEvolve

**An LLM coding agent inside a verified Clifford+T circuit-optimization loop.**

A circuit goes in; a Clifford+T circuit with a lower T-count, checked against the original, comes out. The optimizer
is a Claude Code CLI session working in a folder; this repository is the harness around it — the gate-set
normalisation, the two exact verifiers, the T-count metric, the accept/reject judge, and the playbook that turns an
accepted rewrite into a reusable, LLM-free script.

The design principle is that **the LLM proposes and the harness disposes**. Nothing the agent says about its own
work is believed: every round ends with the harness independently re-deriving equivalence and T-count, and a round
is accepted only if that check passes and the T-count actually went down. The agent's own `check.py` is a
convenience for the agent, never the record.

## What it finds

Results tables are not in this repository: every number depends on the benchmark suite, and a clone builds its own
(stages 1–5 below). Two findings from the earlier campaign are worth naming, because both are mechanisms rather
than tuning, and they say what kind of thing the loop produces:

- **Free-fermion (Givens) resynthesis.** On TFIM circuits the agent replaced Pauli-rotation merging with a Gaussian
  re-synthesis, taking tfim_6 from 160 rotations to 66 = n(2n−1). Stored as a playbook script, it then transferred
  to tfim_4 with no LLM call at all (100 → 28 rotations). That script ships in `examples/givens_rule/`, and the two
  TFIM circuits it was found on are the familiarisation set below.
- **Hamming-weight phasing**, rediscovered on tfim_8 with 4 ancillas and a unitary uncompute, which transferred
  without an LLM call to the Heisenberg, QAOA and hamsim circuits. This is not new work — see Gidney, *Quantum*
  **2**, 74 (2018) and Kivlichan et al., *Quantum* **4**, 296 (2020) — but the agent was not told about it.

Both came out of single runs, and the harness measures T-count only: ancilla count, depth and two-qubit count are
not charged, and the success rate of a run is not measured. Keep that in mind when reading any table it writes.

## How a run works

`python agent.py <circuit> [rounds] --arm <arm>`

1. **Load and baseline.** The circuit is rebased to {cx, h, rz} with no optimization ("raw"), then TKET's
   `FullPeepholeOptimise` produces the *TKET start* — the circuit the agent must beat, and the reference every
   later check is made against.
2. **Workspace.** `runs/<circuit>_<arm>_<time>/` holds `start.qasm` (read-only), `circuit.qasm` (the file the agent
   edits), `check.py`, `./py` (the venv interpreter for scripts the agent writes) and *frozen copies* of the
   harness modules, so a run is scored by the code as it stood when the run began.
3. **Playbook stage** (shared arms only). Before the agent is called, every stored rule is run on the circuit.
   Outputs are kept only when verified and lower in T. The agent starts from the best such result and is given a
   one-line summary of each rule.
4. **Rounds.** One Claude Code turn per round, in the same session. The agent may read and write files in its own
   folder and run exactly two commands; it cannot reach the harness code, other runs, or the network.
5. **Tamper check.** sha256 of every file outside the run folder, before and after. Any change stops the run.
6. **Judge.** The harness re-verifies `circuit.qasm` and re-counts T. The gate is lexicographic — correctness
   first, then T-count — never a weighted blend, because a blended score is maximised by subtly wrong circuits.
   A rejected round resets `circuit.qasm` to the best so far and the agent is told why.
7. **Record.** After an accepted round the agent is asked for a general `technique.py` and a card. The harness
   *replays that script* on the round's own starting circuit and re-verifies the output before the entry counts as
   valid, so what is archived is a script that was checked to work, not a description of what the agent did.

The arms are `isolated` (never reads a playbook), `shared` (reads and grows one), `opus` (same, different model),
and `anc_isolated` / `anc_shared`, which allow ancillas.

## The two verifiers

| | `verifier/verifier_noanc.py` | `verifier/verifier_anc.py` |
|---|---|---|
| question | same unitary on the same qubits? | same action on the data, with fresh ancillas? |
| method | both full unitaries, compared up to global phase | deferred measurement, all 2^n inputs at once |
| metric | operator norm — worst case over all input states | operator norm of the residual against \|anc⟩ ⊗ U |
| accepts | — | clean ancillas, uncompute, measure-out, one-Clifford `if` fix-ups |
| limit | ~12 qubits (4^n memory) | 2^(data+ancilla+data) ≤ 2^26; ~60 s / 3.1 GiB at 10+6 |
| tolerance | 1e-8 | 1e-8 |

Both report a worst-case bound, not an average over sampled inputs, and both are tested against planted bugs:
`tests/test_verifier_noanc.py` (7 hand-made edits plus every baseline) and `tests/test_verifier_anc.py` (Gidney's AND gadget,
6 planted bugs, 8 out-of-scope constructions, and a 300-case fuzz against an independent reference).

## Layout

| path | role |
|---|---|
The four core modules sit at the root; everything that comes in pairs or sets lives in a folder of its own.

| path | role |
|---|---|
| `pipeline.py` | the measurement layer: `load`, the `tket` / `pyzx` / `bqskit_dpf` baselines, the `t_count` metric, `Log` |
| `agent.py` | the run loop: workspace, playbook stage, agent rounds, tamper check, judge, feedback, playbook entry |
| `playbook.py` | rule machinery outside the loop: `find_circuit`, `try_rule`, `valid_rules`, `playbook_stage` |
| `draw.py` | final Clifford+T exports and circuit drawings |
| `verifier/` | `verifier_noanc.py`, `verifier_anc.py` — the two exact verifiers |
| `sweep/` | `sweep.py`, `sweep_anc.py` — LLM-free passes: every stored rule × every circuit → `results/sweep_*.csv`; `final_sweep.py` builds the final per-circuit table |
| `prompts/` | the task prompts the agent receives (goal only, no techniques named) and the `check.py` templates |
| `tests/` | verifier tests and both arms end-to-end with a stand-in agent (no LLM call) |
| `baselines/` | `run_baselines.py` and `dpf/`, the BQSKit-FT DPF driver (see below) |
| `campaign/` | `run_anc_campaign.sh`, `progress.py` — the family-by-family campaign driver and its progress view |
| `examples/givens_rule/` | one playbook entry, shipped as a reference and used by the tests and `draw.py` |
| `circuits/` | the three small circuits the tests and smoke runs use |
| `benchmarks/` | `build_suite.py` plus `hamsim/tfim_4.qasm`, `hamsim/tfim_6.qasm`; the full suite is built locally |

Scripts put what they need on `sys.path` themselves, so every command below runs from the repo root with no install
beyond the dependencies.

Not in the repository, written at run time:

| path | what lands there |
|---|---|
| `runs/<circuit>_<arm>_<time>/` | the folder the agent works in, one per run (see stage 3) |
| `playbook/<arm>/<run>_r<n>/` | the rule library this harness grows: `technique.md`, `technique.py`, `before.qasm`, `after.qasm`, `entry.json` per accepted round |
| `results/` | every table, figure and final circuit the stages below write |
| `logs/` | `agent_<run>.md` (readable) and `.jsonl` (structured): every stage of every run |
| `test_out/`, `.cache/claude_config` | test scratch, and the CLI session store that `--resume` needs between rounds |
| `benchmarks/<family>/` | the benchmark suite itself, built locally |

## Install

Python 3.11 or newer, and eight packages. `requirements.txt` is the list, with a note on each; `pyproject.toml`
carries the same one, so either line below works.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt        # or: .venv/bin/pip install -e .

.venv/bin/python tests/test_verifier_noanc.py    # verifier tests, no LLM
.venv/bin/python tests/test_verifier_anc.py
.venv/bin/python tests/test_playbook.py          # the no-ancilla arm end to end with a stand-in agent, no LLM
.venv/bin/python tests/test_ancilla_arm.py       # the ancilla arm, same
.venv/bin/python pipeline.py                     # baselines on the two TFIM circuits (smoke test)
```

All four tests must pass before anything else is worth running: they are what says the verifiers, the judge and the
playbook replay work on this machine. They take about 20 seconds together and make no LLM call.

Two things are not in `requirements.txt`. Agent runs need the **Claude Code CLI** (`claude`) on `PATH`, a logged-in
session (`CLAUDE_CODE_OAUTH_TOKEN`) and network access to the API; everything else here runs offline. And the DPF
baseline needs **bqskit-ft**, which is not on PyPI and does not currently run out of the box — see the note at the
end of the stages section before installing it.

The four pinned versions (`qiskit`, `pytket`, `pyzx`, `pygridsynth`) are what the metric and the verifiers were
built against; a different gridsynth or TKET means different circuits, so keep them pinned in any environment whose
numbers you intend to compare.

## First runs: tfim_4 and tfim_6

The repository ships two small circuits (`benchmarks/hamsim/tfim_4.qasm`, `tfim_6.qasm`, also in `circuits/`) so a
new clone can be exercised end to end in a few minutes, on both arms, before any benchmark suite is downloaded.
Four qubits with 140 arbitrary rotations in the source file (100 after TKET) is small enough that a round takes a
minute or two and the verifier is instant, and TFIM is where the free-fermion finding came from, so there is
something real to find.

```bash
# 1. no LLM: the baselines, then the one shipped rule applied mechanically
.venv/bin/python baselines/run_baselines.py --workers 2 --out baselines_tfim tfim_4 tfim_6
.venv/bin/python sweep/sweep.py examples tfim_4 tfim_6

# 2. seed the shared playbook with the one shipped rule, so the playbook stage has something to try
mkdir -p playbook/shared && cp -r examples/givens_rule playbook/shared/

# 3. one agent run per arm, 3 rounds each (needs the claude CLI)
.venv/bin/python agent.py tfim_4 3 --arm isolated       # no-ancilla, never reads a playbook
.venv/bin/python agent.py tfim_4 3 --arm shared         # no-ancilla, reads and grows playbook/shared/
.venv/bin/python agent.py tfim_4 3 --arm anc_isolated   # ancilla arm (1-6 fresh ancillas)
.venv/bin/python agent.py tfim_6 3 --arm anc_shared     # ancilla arm, reads and grows playbook/anc_shared/
```

A fresh clone has an empty `playbook/`, so without step 2 the `shared` arm behaves exactly like `isolated`. The
ancilla arms start empty either way: there is no shipped ancilla rule, so `anc_shared`'s first run grows the library
from nothing.

What to look at afterwards:

| where | what it tells you |
|---|---|
| the JSON line printed at the end | `T_tket` → `T_start` → `T_best`, and `equivalent_to_tket` |
| `logs/agent_<run>.md` | every stage in order: prompt, each tool call, each verdict, the judge's reason |
| `runs/<circuit>_<arm>_<time>/` | the folder the agent worked in: `best.qasm`, its own scripts, `transcript.jsonl` |
| `playbook/<arm>/<run>_r<n>/` | what was archived: `technique.md`, `technique.py`, and `entry.json`'s `replay` block |
| `results/baselines_tfim/summary.md` | the baseline table the run has to beat |

The `isolated` and `anc_isolated` runs start from the TKET circuit every time, so they are the ones to repeat if you
want to see run-to-run variance. The `shared` arms are only interesting once the playbook has a few entries.

Reference points on these two circuits: TKET is 5,280 T on tfim_4 and 8,560 on tfim_6; the shipped Givens rule
(`examples/givens_rule/`) takes them to 1,338 and 3,354 with no LLM at all, which is what `sweep/sweep.py examples`
above reproduces. An agent run that lands above those numbers has found less than the stored rule already knows.

## Running the stages on a new benchmark set

The stages are ordered: each one reads what the one before it wrote. All commands run from the repo root with
`.venv/bin/python`; every stage writes its table under `results/` and appends to `logs/`. A fresh clone has no
benchmarks beyond the two TFIM circuits, no playbook and no runs, so this is the full path from clone to results.

### 1. Build the benchmark suite → `benchmarks/`

`benchmarks/build_suite.py` filters a set of upstream repositories into `benchmarks/<family>/<name>.qasm` and writes
`MANIFEST.csv` (name, family, upstream source, exact commit, licence, qubits, gates, path), plus `DROPPED.csv` with
the reason each rejected circuit was dropped. Kept: ≤ 8 qubits (9–10 for arithmetic), loads through `pipeline.load`,
no mid-circuit measurement / reset / classical control, and non-Clifford content after TKET.

The upstream repositories are not vendored. Clone them at the commits recorded in `MANIFEST.example.csv`
(QASMBench, SupermarQ, the Nam et al. arithmetic set via Quartz, the BQSKit qseed collection) into one directory and
point `SOURCE_DIR` at it:

```bash
SOURCE_DIR=/path/to/sources .venv/bin/python benchmarks/build_suite.py
```

Everything downstream is driven by `MANIFEST.csv`, so a different suite only means a different manifest. To work
with the two shipped circuits instead, `cp benchmarks/MANIFEST.example.csv benchmarks/MANIFEST.csv`.

### 2. Baselines → `results/<out>/baselines.{csv,json}`, `summary.md`

Four baselines per circuit — raw (rebased, unoptimized), TKET `FullPeepholeOptimise`, PyZX `full_reduce`, and
BQSKit-FT DPF on the TKET output — each verified against raw and T-counted at a total error of 1e-3. Failures and
timeouts become rows with an `error` and are never dropped, so the table always has one row per circuit × baseline.

```bash
.venv/bin/python baselines/run_baselines.py --workers 8                      # every row of MANIFEST.csv
.venv/bin/python baselines/run_baselines.py --workers 2 --out baselines_tfim tfim_4 tfim_6   # named circuits
```

`--out NAME` picks the subdirectory of `results/` (default `baselines_suite`, which is what the campaign driver and
`campaign/progress.py` read). Named circuits are resolved by `playbook.find_circuit` and need no manifest entry.
Run this before the agent stage: the campaign orders each family by TKET T-count, largest first, from this table,
and `summary.md` is the per-family reference the arms are compared against.

The DPF column needs the extra `bqskit-ft` package and does not run out of the box (see the note at the end of this
section); the other three baselines do.

### 3. Build the playbooks → `playbook/<arm>/`, `runs/`, `logs/`

The only stage that calls an LLM. One invocation = one circuit, one arm, N rounds. Every accepted round is archived
as `playbook/<arm>/<run>_r<round>/` holding `technique.md`, `technique.py`, `before.qasm`, `after.qasm` and
`entry.json`, whose `replay` block records the harness re-running that stored script and re-verifying its output.
Only entries whose recorded replay was equivalent **and** lowered T are ever used again, so the playbook is grown by
running the agent — there is no way to add a rule by hand.

```bash
.venv/bin/python agent.py <circuit> <rounds> --arm <arm>
```

The arms are `isolated` (never reads a playbook), `shared` (reads and grows `playbook/shared/`), `opus` (same, on
`playbook/opus/`, with `--model claude-opus-5`), and `anc_isolated` / `anc_shared`, which allow 1–6 fresh ancillas.

#### Shared arms, one circuit at a time

This is the whole thing: a sequential loop over the manifest, nothing parallel. The shared playbook grows as the
loop goes, so each circuit starts from every rule the earlier circuits produced, and the *order matters* — hardest
first is what the campaign used, because a rule found on a big circuit usually transfers down.

```bash
# largest TKET T-count first (needs stage 2); drop the sort and use the manifest order if the baselines are not in
ORDER=$(python3 -c "
import csv, os
names = [r['name'] for r in csv.DictReader(open('benchmarks/MANIFEST.csv'))]
b = 'results/baselines_suite/baselines.csv'
T = {r['name']: int(r['T'] or 0) for r in csv.DictReader(open(b)) if r['baseline'] == 'tket'} if os.path.exists(b) else {}
print(' '.join(sorted(names, key=lambda n: -T.get(n, 0))))")

# no-ancilla shared arm over the whole suite, one run at a time
for c in $ORDER; do
  .venv/bin/python agent.py "$c" 3 --arm shared      || break
done

# ancilla shared arm, same loop
for c in $ORDER; do
  .venv/bin/python agent.py "$c" 3 --arm anc_shared  || break
done
```

Run them one after the other, not at once: both write to `runs/` and `logs/` safely, but they compete for the same
account rate limit, and `agent.py` exits with `usage limit reached` when it is hit (hence the `|| break`). To do
both arms per circuit before moving on, put the two commands in one loop body instead. To resume after a stop, skip
what is done:

```bash
for c in $ORDER; do
  ls runs/${c}_shared_*/best.qasm >/dev/null 2>&1 && continue
  .venv/bin/python agent.py "$c" 3 --arm shared || break
done
```

Expect roughly 5–15 minutes per run (3 rounds plus the card request) and a few hundred MB of `runs/` per family.
`logs/agent_<run>.md` holds every prompt, tool call and verdict in order; that is the file to watch.

#### The folder the agent works in

Each invocation creates `runs/<circuit>_<arm>_<timestamp>/` and runs the Claude Code session with that as its
working directory. The agent sees nothing else: its tools are `Read`, `Edit`, `Write` and exactly two commands,
`python3 check.py` and `./py` (the venv interpreter, for scripts it writes). It has no network access, no access to
the harness code, and no access to other runs. After every round the harness re-hashes every file outside the folder
and stops the run if one changed.

| in the run folder | what it is |
|---|---|
| `circuit.qasm` | **the file the agent edits** — its answer, and the only file the judge reads |
| `start.qasm` | read-only: what it must beat (the TKET circuit, or the playbook stage's best result) |
| `tket_start.qasm` | read-only: the TKET circuit, which is what the ancilla arms are always verified against |
| `round_start.qasm` | the circuit as it stood at the start of the current round |
| `logical.qasm` | ancilla arms only: the source circuit with its `ccx` / custom gates intact |
| `check.py`, `py` | the agent's own verdict command, and the interpreter wrapper for scripts it writes |
| `pipeline.py`, `verifier_*.py` | frozen copies, so the run is scored by the code as it stood when it started |
| `playbook_cards/<rule>/` | shared arms: `technique.md` + `technique.py` of every stored rule it may read |
| `playbook_stage/` | the input and output of each stored rule the harness tried before round 1 |
| `technique.md`, `technique.py` | written by the agent after an accepted round; these two are what get archived |
| `replay_r<n>.qasm` | the harness's own replay of that stored script, which is what validates the entry |
| `best.qasm` | written at the end: the best verified circuit of the run |
| `transcript.jsonl` | every event of the session, as it happened |

Anything else in the folder is the agent's own scratch work — it writes and runs its own analysis scripts there, and
they are kept exactly as they were left.

#### The parallel campaign driver

`campaign/run_anc_campaign.sh` is the heavier alternative, used for the earlier ancilla campaign: per family it
runs three concurrent Claude Code sessions — one `anc_shared` chain largest-first, whose playbook grows as it goes,
and two `anc_isolated` workers on alternating circuits — then the family's ancilla sweep. It is resumable (a
circuit × arm that already has `runs/<c>_<arm>_*/best.qasm` is skipped) and survives an account usage limit by
parking the run in `runs/aborted/`, waiting 30 minutes and retrying. It needs three sessions' worth of rate limit;
the sequential loops above do not.

```bash
./campaign/run_anc_campaign.sh                           # all five families
FAMILIES="arithmetic other" ./campaign/run_anc_campaign.sh
python3 campaign/progress.py                             # or: watch -n 60 python3 campaign/progress.py
```

### 4. Sweep stage → `results/sweep_*.csv`

No LLM: every stored rule, run mechanically on circuits it was not discovered on. This is where a playbook's
transfer is measured, and where the numbers that go into the result tables come from. A rule's output is kept only
if the verifier accepts it and the T-count went down.

```bash
# no-ancilla: each rule alone on the TKET start, then a greedy chain of all rules in discovery order
.venv/bin/python sweep/sweep.py playbook/isolated heisenberg_5 tfim_6
.venv/bin/python sweep/sweep.py playbook/shared                 # default circuits: tfim_4 tfim_6

# ancilla: rules are never chained, each runs alone on the TKET start with logical.qasm beside it
.venv/bin/python sweep/sweep_anc.py hamsim playbook/anc_isolated,playbook/anc_shared --family hamsim
.venv/bin/python sweep/sweep_anc.py all playbook/anc_isolated,playbook/anc_shared       # all of MANIFEST.csv
.venv/bin/python sweep/sweep_anc.py tfim playbook/anc_shared tfim_4 tfim_6              # named circuits
```

Where the results land:

| command | output |
|---|---|
| `sweep/sweep.py <dir> [circuits]` | `results/sweep_<dir basename>.csv` — one row per circuit × rule, plus a `GREEDY` row per circuit |
| `sweep/sweep_anc.py TAG <dirs> …` | `results/sweep_anc_<TAG>.csv` — one row per circuit × rule, plus a `BEST` row per circuit, and the winning circuits in `results/sweep_anc_<TAG>/<circuit>_best.qasm` |

Each row carries the rule, whether the output verified, its T-count, the reason it was rejected, and for the ancilla
sweep the ancilla and measurement counts. The `BEST` row also records whether the winning circuit verified against
the *original* benchmark file, not just the TKET start. `sweep_anc.py` fills its `T_pyzx` / `T_noanc_final` columns
from `results/final_all.csv` (stage 5) when that table exists and leaves them empty otherwise.

### 5. Final table → `results/final_all.csv`, `results/circuits/<name>_final.qasm`

One row per circuit, and the circuit behind it: `sweep/final_sweep.py` collects every verified candidate from the
arms, re-sweeps the stored rules over each of them, and re-verifies the winner against the **original** benchmark
file rather than the TKET start. That last check is the one that matters for reporting, so nothing reaches the table
without it.

```bash
PRIOR_DIR=/path/to/intermediate_tables .venv/bin/python sweep/final_sweep.py results/
```

Read it before running it: this is the script as it was used, not a general driver. It reads the per-family
intermediate tables the earlier campaign wrote to a scratch directory outside the repository (`PRIOR_DIR`) and it
hard-codes which arms and which rule folders to collect, so a new campaign needs those two things adjusted to match
how its own runs are laid out. Figures were plotted ad hoc from the CSVs; no plotting script is committed.

### 6. Clifford+T exports and drawings → `results/clifford_t/`, `results/drawings/`, `results/summary.json`

Expands every arbitrary `rz` into its gridsynth word, re-counts T on the resulting Clifford+T circuit, and
re-verifies the whole thing against the original within the total error budget. Methods whose file is not on this
machine (the agent run bests, the DPF outputs) are skipped.

```bash
.venv/bin/python draw.py
```

**The DPF baseline needs one extra package, and does not run out of the box.** `pipeline.bqskit_dpf` drives
`baselines/dpf/pk/dpf_pre_gridsynth.py` as a subprocess, because that driver monkey-patches bqskit before importing
`bqskit.ft` and the patch must not leak into the interpreter that scores every other arm. Install it with
`pip install --no-deps "bqskit-ft @ git+https://github.com/BQSKit/bqskit-ft@2e99ba614d48970b9afefc0b8c32860c3a3dc9f1"`;
`baselines/dpf/pip_freeze_dpf.txt` records the exact environment it was last run in. The TKET and PyZX baselines
and the whole agent loop do not need it.

Two rough edges in that driver, both documented at their call sites. `bqskit.ft` references a class
(`MidCircuitMeasurement`) that exists in no published bqskit release, which is what `midmeasure_shim.py` supplies.
And `dpf_pk.serial_compiler()` expects a `make_serial_compiler()` helper that is not vendored here, because BQSKit's
own `Compiler` spawns a runtime server on a localhost socket; the fallback now calls `bqskit.compiler.Compiler()`,
which is the right object but dies with `Server connection unexpectedly closed` on a sandboxed machine. Until that
helper is restored, the `bqskit_dpf` rows of a baseline run carry that error and the other three baselines are
unaffected — so treat TKET as the baseline to beat, and add DPF back once it runs on your machine.

## Benchmarks

The earlier campaign used 76 circuits, filtered to ≤ 8 qubits (9–10 for arithmetic) with non-Clifford content and
no mid-circuit measurement, reset or classical control, from QASMBench (PNNL), SupermarQ (Infleqtion), the Nam et
al. arithmetic set via Quartz, and the BQSKit qseed collection. Those copies are **not** in this repository: only
`benchmarks/hamsim/tfim_4.qasm` and `tfim_6.qasm` ship, as a familiarisation set.

`benchmarks/build_suite.py` rebuilds the suite from the upstream repositories (stage 1 above) and writes
`MANIFEST.csv`, which records each circuit's upstream repository, exact commit and licence. The two shipped rows are
in `MANIFEST.example.csv`. Any other set of QASM files works as well: drop them in a family folder, give them a
manifest row, and every stage downstream follows.

## Scope

- T-count is the only objective. Ancilla count, depth and two-qubit count are not charged.
- One run per circuit per arm; the success rate of a single run is not measured.
- The no-ancilla verifier builds a full unitary, which caps circuit size at ~12 qubits; the ancilla verifier caps
  data + ancillas by the 2^26-amplitude work limit. Neither scales to circuits of practical size, and extending
  past them is a different problem from the one this harness solves.
