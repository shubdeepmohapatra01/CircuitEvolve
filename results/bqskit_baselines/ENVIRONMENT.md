# Baseline environment `bqskit-ft`

Created 2026-10-11 for the Baselines track (no LLM).

- Location: `experiments/bqskit_baselines/.venv` (Python venv; git-ignored by the repo's `.venv/` rule),
  registered with the session as environment `bqskit-ft`.
- Why a venv, not conda: `conda create` failed twice on 2026-10-11 (conda-forge repodata, proxy
  `CONNECT tunnel failed, response 502`); PyPI was reachable. Base interpreter is the session's
  conda `python` env, Python 3.11.15 macOS-26.6.2-arm64-arm-64bit. The venv does NOT include system site-packages.
- Recreate:
  ```
  python3.11 -m venv experiments/bqskit_baselines/.venv
  experiments/bqskit_baselines/.venv/bin/pip install bqskit pygridsynth pytket pyzx==0.10.7 qiskit pandas mpmath pytest
  experiments/bqskit_baselines/.venv/bin/pip install "git+https://github.com/BQSKit/bqskit-ft@4a288aee10e1735ea322ddb98d29b69fe16ec1d7"
  ```
  Full pin list: `pip_freeze.txt` (same directory).

| package | version | note |
|---|---|---|
| bqskit | 1.2.1 | |
| bqskit-ft | 0.2.0 | |
| bqskitrs | 0.4.1 | |
| mpmath | 1.3.0 | |
| numpy | 2.4.6 | |
| pandas | 3.0.6 | |
| pygridsynth | 2.0.0 | |
| pytket | 2.18.5 | |
| pyzx | 0.10.7 | |
| qiskit | 2.5.2 | |
| scipy | 1.17.1 | |

- bqskit-ft: installed from git, commit `4a288aee10e1735ea322ddb98d29b69fe16ec1d7` (2026-07-06), pyproject version 0.2.0.
- Gridsynth implementation: **pygridsynth** — required by bqskit-ft (`pyproject.toml` dependency;
  `bqskit/ft/ftpasses/gridsynth.py` calls `pygridsynth.gridsynth.gridsynth_gates(theta, precision)` at
  `mpmath.mp.dps = 128`). rsgridsynth/newsynth not needed.
- pyzx pinned to 0.10.7 to match the repo venv.

## Sandbox workaround
`bqskit.compiler.Compiler` binds a localhost TCP socket (`PermissionError: [Errno 1]` in this sandbox).
`experiments/bqskit_baselines/serial_runtime.py` installs an in-process serial runtime as
`bqskit.runtime.worker._worker` (methods `map`, `submit`, `get_cache`) and runs a pass list with
`asyncio.run(Workflow(passes).run(circuit, PassData(circuit)))`. Gridsynth calls are parallelised with
a `multiprocessing` spawn pool (12 cores) instead.
