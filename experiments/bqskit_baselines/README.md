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
