# CircuitEvolve (overhaul branch)

LLM-written rewrite rules for Clifford+T T-count reduction, verified exactly and scored after the full pipeline.
Old code (v2-v4, cvdv) is on `main@b00f96c`.

## Structure (~1,100 lines)

| file | role |
|---|---|
| `circuitevolve/circuit.py` | the one circuit format and gate semantics; QASM in/out |
| `circuitevolve/verifier.py` | `check(old, new, Req, zero_init)`: is `new` an allowed replacement? |
| `circuitevolve/metric.py` | final T-count after gridsynth at total eps = 1e-3 |
| `circuitevolve/library.py` | TKET, pyzx, gridsynth wrappers (baselines and pipeline stages) |
| `circuitevolve/dpf.py` | BQSKit DPF wrapper (subprocess into `experiments/bqskit_baselines/.venv-pk`) |
| `circuitevolve/agents.py` | scout (ideas) and implementer (rule code); backend = any `ask(prompt) -> str` |
| `circuitevolve/loop.py` | `train` and `test` |
| `run.py`, `report.py` | command line; table and figures |
| `playbook/<arm>/NNN_*.py` | accepted rules; `log.jsonl` = every attempt and application |

A rule is a Python file with `rewrite(c: Circuit) -> (Circuit, Req)`. `Req(eps, ancillas, measure)` says what it may use.

## Training loop

```
for circuit i in train:            # Toffoli circuits first
    i' = apply every playbook rule (skip non-equivalent applications; keep worse ones; log all)
    ideas = scout(i')               # claude-opus-5, thinking off
    for idea: up to 3 implementer attempts (claude-sonnet-5, thinking off), verifier/metric feedback fed back
        accept if it verifies AND lowers the final T-count of i'
test: apply the final playbook to unseen circuits, no LLM calls; end-to-end re-check of every output
```

Arms. Rotation circuits: L0 = TKET -> playbook; L1 = TKET -> pyzx -> playbook; L2 = TKET -> DPF(k=3) -> playbook; then gridsynth.
Toffoli circuits: the playbook goes first, on the logical ccx/ccz form (TKET/pyzx dissolve the Toffolis), then TKET (L0)
or TKET+pyzx (L1), run piecewise between measurement gadgets. Baselines B0/B1 = L0/L1 with an empty playbook.

## Verifier

One check for every tag. Only the changed segment is simulated (dense <= 8 data qubits, else 8 random states).
- Fresh ancillas start in |0> and must end in an input-independent state.
- Every measurement branch must agree.
- Approximate rules are charged the measured distance.
- Benchmark clean ancillas (`zero_init` in `splits.json`) are |0> until first touched.
- Borrowed (dirty) qubits need no tag: existing qubits are checked on every input.
- Cost guards refuse, never accept: more than 4096 branches, too much work, or more than 60 s per check.

`tests/test_verifier_fuzz.py` compares the verifier against a naive whole-circuit reference on 3,000 random cases.

## Error budget (eps_total = 1e-3)
DPF spends 0.4 eps (L2 only); LLM approximate rules at most eps/4, charged the measured distance; gridsynth gets the rest.

## Run
```
python run.py train L1            # needs a logged-in `claude` CLI (scout opus, implementer sonnet)
python run.py test L1             # -> results/test_L1.csv
python report.py                  # -> results/t_counts.csv, t_counts_toffoli.png, t_counts_rotation.png
python -m pytest tests            # 26 tests
```

## First results (2026-10-27; train = 18 small circuits, test = the 13 plotted circuits)
All 39 test outputs re-verified end to end.
- L0: 5 rules (4 measured-uncompute / temporary-AND, 1 shared phase gadget). Better than B0 on 6/13
  (adder_6 59->54, modred_21 107->99, qpe_8 14787->13355, hhl_8 35315->32091); never worse.
- L1: 4 rules (measured-uncompute variants). adder_6 47->46. Worse than B1 on mcx_10 (100->141) and modred_21 (73->84):
  the gadgets block pyzx phase folding across measurements. This is the accepted "rules can make it worse" case, logged.
- L2: 1 rule, a re-derivation of phase folding (parity tracking through CX ladders), i.e. a known technique.
  Beats stored B2 on qpe_8 (7552->7212) and hhl_8 (18701->17601); 296 of the hhl_8 gap is our DPF wrapper's full use of the budget.
- A hand-written Gidney reference rule (`tests/fixtures/gidney_pairs.py`) gives tof_4 23->15 under L1. The LLM rules reached 21,
  so the mechanism is reachable but the LLM implementations are partial.

## Known issues / later
- B2 (PKAC DPF Synth) outputs with ancillas (qft_8, qae_13) fail an equivalence check upstream (bqskit-ft greedy_ntro @c04a322):
  missing |A> preps (75 on qft_8, fixed in our lowering) plus an unresolved ancilla leak. Stored values are shown, hatched.
- Coverage: L0 trained on 16/18 (mod5_4, cuccaro_8 skipped after the early scout failures); L1 on 17/18 (hubbard_4: token ceiling).
- Next: a rule-selection agent (which rules to apply per circuit); post-selection / RUS rules (`Req.postselect`, expected T-count).
