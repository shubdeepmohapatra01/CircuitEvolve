# experiments/bqskit_baselines — classical Clifford+T baselines (no LLM)

Environment: `.venv/` (registered as `bqskit-ft`; see `results/bqskit_baselines/ENVIRONMENT.md`).

| file | purpose |
|---|---|
| `serial_runtime.py` | in-process stand-in for the BQSKit runtime (Compiler needs a localhost socket) |
| `common.py` | paths, published Table-3 values, pygridsynth wrapper (cached, parallel, word re-verified) |
| `bygate_exact.py` | exact gate-level Clifford+RZ lowering: `paramzsx` (paper convention) and `minrz` (minimal RZ per 1q run) |
| `run_bygate_exact.py` | runs a lowering + gridsynth(1e-9) on circuits -> CSV |
| `run_table3.py` | bqskit-ft `build_circuit_workflow` as shipped (or `--workflow pergate`) + gridsynth |
| `shor_param_convention.py` | diagnostic: one gridsynth per non-pi/4 cp/ccp/u1 parameter (explains Shor-16 = 816) |
| `make_aqft.py` | textbook approximate QFT generator (diagnostic input for QFT-32) |
| `run_reference.py` | TKET FullPeepholeOptimise and pyzx full_reduce reference pipelines, 30-min limit each |
| `verify_equiv.py` | statevector spot-check of pipeline outputs (n <= 20) |
| `profile_partitions.py` | QuickPartitioner(2/3) block profile |
| `run_all_table3.sh` | the Table-3 runs as executed on 2026-10-11 |
| `test_bygate_exact.py` | tests for the 1q minimal decomposition (`.venv/bin/python -m pytest -q test_bygate_exact.py`) |

All outputs go to `results/bqskit_baselines/` (append-only; scripts refuse to overwrite a CSV).

## stage1/ — B0-B3 on the stage-1 qseed circuits (2026-10-13, venv `.venv-dpf`)

Environment `.venv-dpf/` (Python 3.12, bqskit-ft `algorithmic_error_dpf` @ 2e99ba6, rsgridsynth v1.0.0 built
with Rust; see `results/bqskit_baselines/stage1/ENVIRONMENT.md`, pins in `pip_freeze_dpf.txt`). The old `.venv/`
and all scripts above are unchanged.

| file | purpose |
|---|---|
| `stage1/s1_common.py` | paths, circuit list, rsgridsynth / pygridsynth wrappers, Clifford+Rz -> Clifford+T lowering, statevector distance |
| `stage1/make_inputs.py` | the shared TKET FullPeepholeOptimise inputs -> `results/.../stage1/inputs/` |
| `stage1/run_b0_b1.py` | B0 TKET+gridsynth, B1 pyzx+gridsynth |
| `stage1/run_bqskit_arms.py` | B2, B3 (published `alg_err_workflow.py`, vendored verbatim in `stage1/vendor/`), suppl. B2ft/B3m/B3g; in-process SerialCompiler; one job per process (`--job CIRCUIT ARM EPS`) |
| `stage1/u12rz_shim.py` | in-memory stand-in for the missing `bqskit.passes.rules.u12rz` |
| `stage1/canonical.py` | pygridsynth recount of every arm's pre-gridsynth circuit (needs `S1_RUN_VERSION=v2` runs) |
| `stage1/collect.py`, `stage1/collect_v2.py` | tables `stage1_baselines.csv` (first pass) and `stage1_baselines_v2.csv` (authoritative) |

Order used: `make_inputs.py`; `run_b0_b1.py`; `S1_RUN_VERSION=v2 run_bqskit_arms.py --job ...` for all
(circuit, arm, eps) (8 in parallel, `OMP/VECLIB/RAYON_NUM_THREADS=1`); `S1_RUN_VERSION=v2 canonical.py`;
`collect_v2.py`. Export `XDG_CONFIG_HOME=.venv-dpf/xdg` (pytket writes a config file).
