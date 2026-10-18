# PLAN_P3 — method cascade: reconstruction + angle + lifting

SELF-CONTAINED HANDOFF: written for an implementing agent with NO prior context. Read §0-§2
before writing any code. The plan is append-only once execution starts; deviations are
documented in results/CHANGELOG.md, never silently.

## 0. Briefing — what this repo is and what already exists

LLM-assisted quantum circuit optimizer, verifier-first. CLAUDE.md holds 7 standing invariants —
read it FIRST; the load-bearing ones here: fitness is lexicographic (never a weighted blend);
verifiers are FROZEN during search (circuitevolve/integrity.py digest + cvdv/FROZEN.sha256,
checked start/end of every run); results/ is append-only; self-evolving parts change PROPOSALS,
never acceptance.

Already built and gated (do not rebuild):
- `circuitevolve/engine/` — generic loop (EvolveLoop), DomainPlugin contract, deterministic
  tier-0 router (router.py), optimize() entry (run.py), playbook tiers, graduation machinery
  (graduate.py; G1 = same_pauli_merge pass, dev replay -8.27% T), accept-anatomy reflector
  (reflector.py). docs/ENGINE.md is the architecture doc.
- `circuitevolve/domains/dv_windows/` — rotation-polish plugin (the "angle" method's engine).
- `circuitevolve/domains/cvdv/` — certified CV-DV compiler plugin (frozen stack, wrap-in-place).
- `circuitevolve/v2/tier1/` — recognizer (recognize.py: Toffoli pairs w/ classes, MCX, repeated
  blocks, qubit roles via bit-trace), plan/compile/control, relaxed verifier (v2/verify.py,
  same frozen digest). This is the RECONSTRUCTION method's machinery, currently standalone.
- Benchmarks: `benchmarks/nam_arith/generated/` (cuccaro_4/8/16, ccx INTACT) and
  `benchmarks/nam_arith/cliffordt/` (adder_8, barenco_tof_*, gf2^N_mult, mod_mult_55, ...,
  already Clifford+T-decomposed). Stage-1 rotation benchmarks + B0/B1/B2/B3g baselines:
  `results/bqskit_baselines/stage1/` (stage1_baselines_v2.csv). v2 deterministic-control
  results: `results/v2/bench_runs/run1..3`, `results/v2/eval/eval_results.csv`.
- Campaign contract for the angle method: docs/P2_CAMPAIGN.md (real-LLM campaigns are
  budget-approved separately; NOT part of this plan).

Working rules: env `circuitevolve-dev` is the repo venv (`.venv/bin/python -m pytest -q`,
expect 341 passed + 2 skips at start); cvdv tests run in conda env `cvdv-opt`
(`cd cvdv && python -m pytest tests -q`, 33 passed). One commit per phase; every phase gate =
full suite green + `circuitevolve.integrity.frozen_digest()` unchanged (bc3eac23...) +
`bash cvdv/scripts/check_frozen.sh` OK + tests/engine/test_manifest.py green. Never edit:
files in integrity.FROZEN, blocks/verify_block.py, anything under cvdv/, results/** (append
new files only), playbooks/dev_v1.json & other stage-1 originals, graduated/ existing entries
(G1), search/playbook.py A/B semantics.

## 1. Settled design decisions (from the design sessions; binding)

1. **Playbooks are METHOD-scoped, not circuit-class-scoped**: `reconstruction` (construction
   substitution, relaxed contract), `angle` (rotation/window polish, approx contract — the
   existing dv.windows stack), `cvdv` (certified subspace, term input). No circuit taxonomy
   anywhere; an "adder" is never detected as an adder, only as structure.
2. **Routing = applicability predicates + cascade, NOT classification.** Each method has a
   deterministic structural predicate; ALL applicable methods run, most-structural first:
   [reconstruction?] -> [angle?]; cvdv is input-type-disjoint. Pure-Clifford input: no method
   fires -> return input unchanged (not an error). NO LLM in routing. No triage call.
   Manifest override (`{"family": ...}`) stays as the manual escape hatch.
3. **Recognize/route on the RAW input; decompose late.** TKET FullPeepholeOptimise moves
   INSIDE the angle method as its entry pass (applied only when the input isn't already a
   stage-1 pre-TKET'd circuit). It must NEVER run before reconstruction - it dissolves ccx
   into 7-T networks and destroys the structure reconstruction needs.
4. **Structure lifting is the fallback** for inputs that arrive already decomposed: a
   deterministic template matcher first (7-T Toffoli network, Maslov RCCX, h-CCZ-h — the last
   already exists in recognize.normalize), every claimed span verified EXACTLY (D[omega],
   3-qubit span vs ccx unitary) before anything trusts it; an optional LLM structure-spotter
   sits behind the SAME verify-exact gate, OFF by default, budgeted when on. A wrong
   hypothesis costs one check, never correctness (invariant 7 intact).
5. **Contracts never mix in reports**: reconstruction gains live in the relaxed column; the
   angle stage after it is unitary-preserving RELATIVE to the reconstructed circuit. Per-stage
   attribution in every summary (`pre_opt` pattern from P2.3: deterministic gains are never
   sold as LLM gains).
6. **Candidates-per-call is a config knob** (today hardcoded "at most three" in the angle
   mutator prompt): plumb it, default 3 (golden fixture must pass unchanged at 3), fixed
   within any campaign arm. The 3-vs-5 question is answered by a REAL-LLM mini-A/B whose
   harness this plan builds but whose execution is budget-gated (user approval).

## 2. Renames: method vocabulary without breaking frozen provenance

router.json goes to format `/1` with top-level `methods`: keys `reconstruction`, `angle`,
`cvdv`. Each row: predicate parameters, contract, plugin id, playbook path, cascade rank.
DO NOT rename existing files or identifiers that frozen/recorded state references:
`playbooks/families/dv.windows.json` keeps its filename (the angle method's playbook path
points at it); the graduated index keeps family key `dv.windows` (G1's entry is frozen —
router row `angle` carries `graduated_family: "dv.windows"` as the lookup alias);
`cvdv.bosonic.json` likewise becomes the `cvdv` method's playbook path. New reconstruction
playbook: `playbooks/families/reconstruction.json`. Update tests that assert the `/0` table
format; keep a format-migration note in results/CHANGELOG.md.

## 3. Phases (one commit each; gates listed are HARD)

**P3.0 — start-state record.** Run both suites + both digest checks; append a plan-start
CHANGELOG entry recording commit hash, suite counts, digests. No code. Gate: all green.

**P3.1 — reconstruction benchmark suite.** Curate from benchmarks/nam_arith (BOTH dirs) +
stage-1 where applicable. For every candidate circuit run the v2 recognizer on the RAW form
and keep it iff structural features fire (>=1 mirror pair OR MCX cascade OR >=20% naive-T in
Toffolis). Store `results/engine/recon_bench/MANIFEST.json`: per circuit — source path,
sha256, feature evidence (pairs/mcx/clean ancillas/rotation content), dev|held-out assignment
(split balanced on feature mix; suggested dev: cuccaro_4, cuccaro_8, barenco_tof_5, tof_5*,
rc_adder_6*; held-out: cuccaro_16, adder_8, qcla_adder_10*, barenco_tof_10*, mod_adder_1024*,
gf2^4_mult — *if present in benchmarks/, else take from results/v2 bench circuit lists and
record provenance). Generate the TKET-DECOMPOSED twin of every suite circuit ONCE
(blocks/classical.tket_optimise), store under recon_bench/decomposed/ with sha256s — these
are the lifting stress set. Baselines per circuit, append-only CSV recon_bench/baselines.csv:
B0 (TKET+gridsynth path where rotations exist, else plain T-count), B1 (pyzx,
circuitevolve/baselines), and the v2 tier-1 DETERMINISTIC CONTROL under the relaxed contract
(v2/tier1/control.py route) as the bar — relaxed column separate. Gate: manifest + baselines
committed; every row's features reproduce deterministically (a test re-runs the recognizer on
2 circuits and compares); no existing file modified.

**P3.2 — router v1: method predicates + cascade.** Implement §1.2/§1.3 + §2 in
engine/router.py + run.py: `route()` returns an ordered list of MethodBindings; optimize()
executes the cascade, threading the verified output of stage k into stage k+1 and emitting
per-stage sections in the summary (`stages: [{method, contract, in/out metrics, verified}]`).
Angle-stage TKET entry pass per §1.3 (flag `tket="auto"|"off"`; stage-1 named inputs = off,
raw qasm = auto). Gates: (a) all P1/P2 behavior reproduced bit-exact — the existing B0
identity, graduated on/off, golden, dry-run tests pass UNCHANGED (pure-rotation input must
produce a single-stage cascade identical to today's run); (b) pure-Clifford input returns
input unchanged with an explanatory summary; (c) cuccaro_4 raw routes [reconstruction, angle];
(d) routing log rows carry the predicate evidence.

**P3.3 — reconstruction method plugin.** `circuitevolve/domains/reconstruction/plugin.py`
wrapping v2/tier1 behind the DomainPlugin contract: state = logical circuit + plan;
select = recognizer elements ranked by naive-T share; mutate = plan proposals (LLM) with the
DETERMINISTIC CONTROL route (v2/tier1/control.py) available as the no-LLM arm; verify = the
frozen v2 relaxed verifier (v2/verify.py — call check_integrity, never reimplement);
measure = (T, qubits, T-depth) in the relaxed column; ledger: exact-relaxed constructions
charge 0 (they are exact branch-wise — follow v2 conventions). Playbook
`playbooks/families/reconstruction.json` seeded (origin="seed") from the tier-1 toolbox:
temporary_and (Gidney 2018), jones_toffoli / measurement-based uncompute, clean-AND
compute-only, relative_phase_toffoli pairing (Maslov), + the routing lesson "mirror pair into
declared-zero target => temporary-AND" — provenance-tagged like P2.2 seeds. Gates: (a) plugin
with scripted control-route plans reproduces the v2 deterministic-control numbers on >= 4
suite circuits (compare against results/v2 records; equal T, qubits); (b) zero-accept run
returns the input unchanged; (c) fake-LLM cascade e2e on cuccaro_4 or _8: reconstruction
(control route) then angle (G1 pass + declining loop) — final T strictly below the
angle-only arm on the same input, per-stage attribution correct; (d) both frozen digests
unchanged (v2 shares the dv digest).

**P3.4 — structure lifting (deterministic core).** New engine/lift.py: template matcher for
the standard 7-T Toffoli network and Maslov RCCX over {h,t,tdg,cx} (commuting-gate
interleaving tolerated: match on the per-qubit projected subsequences, then take the minimal
op span), EVERY claimed span verified exactly against the ccx/rccx unitary in the D[omega]
ring before substitution into the lifted LogicalCircuit; unverified claims are dropped, never
guessed. Wire as pre-recognition inside route(): fires only when toffolis==0 AND t+tdg count
>= 7. The LLM spotter hook: define the call-site interface (prompt = gate stream + structural
hints; reply = claimed spans; same verify gate) but implement as a STUB raising
NotImplementedError behind flag lift_llm=False — building it is a later, budgeted step.
Gates: (a) on the decomposed twins from P3.1, report per-circuit recovery rate (recovered
toffolis / original) in results/engine/recon_bench/lifting_report.json — NO minimum is
imposed (honest measurement), but every reported recovery must be verify-exact (test asserts
zero false structures by re-verifying); (b) e2e: decomposed cuccaro_4 lifts -> routes
[reconstruction, angle] -> cascade beats angle-only on that input; (c) raw-path behavior
unchanged (lift must not fire when ccx present).

**P3.5 — candidates-per-call knob + 3v5 harness.** Plumb `max_candidates` (default 3) from
FamilyBinding/loop kwargs into the angle mutator prompt text + parser cap (core/mutator.py is
proposal-side, editable; the DV plugin threads it). Harness
experiments/engine_ab_candidates.py: arm 3 vs arm 5, dev circuits of P2_CAMPAIGN (angle) at
fixed seeds/budget (>= 12 calls/circuit/arm), paired per-circuit report (accept rate, T delta,
tokens) appended under results/engine/. EXECUTION is budget-gated: the script exists and is
tested with a fake backend; running it with a real LLM requires explicit user approval —
print that in the script header and do NOT run it in this plan. Gates: golden fixture passes
UNCHANGED at default 3; a fake-LLM test shows the 5-cap parsing 5 candidates.

**P3.6 — cascade demo + docs + close.** Deterministic (zero-LLM) demo table,
results/engine/recon_bench/DEMO.md: for one raw adder (cuccaro_8) and one mixed circuit (an
adder composed with a rotation payload — build it in the demo script and commit the qasm):
arms = angle-only | reconstruction-only (control route) | cascade | per-circuit best classical
arm (B0/B1), relaxed column separated, per-stage attribution shown. Update docs/ENGINE.md
(method cascade section, lifting, knob), CLAUDE.md layout lines, CHANGELOG close entry with
final suite counts + digests. Gate: full suite + cvdv suite + manifest guard green; demo
numbers reproduce from committed scripts.

## 4. Explicitly OUT of this plan

Real-LLM anything: the angle campaign (docs/P2_CAMPAIGN.md governs it), the 3v5 A/B execution,
the lifting LLM spotter implementation, reconstruction-method LLM campaigns. Each needs user
budget approval. Also out: touching acceptance/ledger semantics, cvdv/ internals, any frozen
file, MAP-Elites archive changes.

## 5. Open decisions the implementer may settle (document in CHANGELOG)

1. Exact threshold values in the applicability predicates (suggested: reconstruction fires at
   >=1 verified mirror pair or mcx, OR toffoli-naive-T share >= 20%; angle fires at >=1
   non-Clifford rotation).
2. Whether tof_5 / rc_adder_6 / qcla_adder_10 / mod_adder_1024 enter the suite from
   benchmarks/ or from results/v2 bench circuit copies (record provenance either way).
3. Internal shape of MethodBinding vs reusing FamilyBinding with a rank field.
4. Where the mixed demo circuit lives (benchmarks/mixed/ suggested).
