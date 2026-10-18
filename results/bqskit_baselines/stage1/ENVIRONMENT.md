# Stage-1 baseline environment (`.venv-dpf`)

Created 2026-10-13 for the stage-1 Baselines track. The older venv
`experiments/bqskit_baselines/.venv` (bqskit-ft `main` @ 4a288ae, pygridsynth) is untouched.

- Location: `experiments/bqskit_baselines/.venv-dpf` (git-ignored), Python **3.12.12** (Homebrew,
  `/opt/homebrew/bin/python3.12`); bqskit-ft at this commit declares `requires-python >= 3.12`.
  Host: macOS 26.6.2 arm64, 12 cores, 24 GiB.
- **bqskit-ft**: `git+https://github.com/BQSKit/bqskit-ft@2e99ba614d48970b9afefc0b8c32860c3a3dc9f1`
  (branch `algorithmic_error_dpf`, 2026-08-14 "CCZ skip flag added"), package version 0.2.0.
- **Gridsynth: rsgridsynth (the real dependency, NOT substituted).** `rsgridsynth @
  git+https://github.com/jkalloor3/rsgridsynth.git@v1.0.0` = commit
  `bff24e24b63d530f0f53851d9c0ae970a39ce0d4` (pip version 0.1.0, Cargo crate 0.2.0), built from source
  with maturin and a workspace-local Rust toolchain (rustup minimal profile, **rustc/cargo 1.99.0**).
  Build workarounds (sandbox only, no source changes): `RUSTUP_USE_CURL=1` + certifi CA bundle
  (`SSL_CERT_FILE`, `CARGO_HTTP_CAINFO`, `PIP_CERT`, `PIP_USE_DEPRECATED=legacy-certs`) because the
  macOS platform certificate verifier is blocked; the three `glam` crates (0.30.10, 0.31.1, 0.32.1)
  were unpacked from cargo's verified `.crate` archives without their `.gitmodules` file (the sandbox
  forbids writing files named `.gitmodules`; they are git metadata, not compiled sources).
- pygridsynth 2.0.0 is also installed (cross-check only). On 20 random angles rsgridsynth vs
  pygridsynth total T: 1254 vs 1246 at eps 1e-6, 1664 vs 1662 at 1e-8 (<= 0.7 % apart); every
  rsgridsynth word was re-multiplied and verified within its eps.

| package | version |
|---|---|
| bqskit | 1.2.1 |
| bqskit-ft | 0.2.0 @ 2e99ba6 |
| bqskitrs | 0.4.1 |
| rsgridsynth | 0.1.0 @ bff24e2 (tag v1.0.0) |
| pygridsynth | 2.0.0 (cross-check only) |
| pytket | 2.18.5 |
| pyzx | 0.10.7 |
| qiskit | 2.5.2 |
| numpy | 2.5.4 |
| scipy | 1.18.1 |
| pandas | 3.0.6 |
| mpmath | 1.3.0 |

Full pin list: `experiments/bqskit_baselines/pip_freeze_dpf.txt`.

Recreate (network + Rust needed):
```
/opt/homebrew/bin/python3.12 -m venv experiments/bqskit_baselines/.venv-dpf
# Rust: rustup-init -y --profile minimal (RUSTUP_HOME/CARGO_HOME anywhere writable), put cargo on PATH
.venv-dpf/bin/pip install "rsgridsynth @ git+https://github.com/jkalloor3/rsgridsynth.git@v1.0.0"
.venv-dpf/bin/pip install "git+https://github.com/BQSKit/bqskit-ft@2e99ba614d48970b9afefc0b8c32860c3a3dc9f1"
.venv-dpf/bin/pip install pytket==2.18.5 pyzx==0.10.7 qiskit==2.5.2 pandas mpmath pygridsynth==2.0.0 pytest
```

## Defects in the pinned branch and how they were handled (see ERROR_ACCOUNTING.md)

1. **Missing module.** `bqskit/ft/cliffordrz/defaultworkflow.py:35` imports
   `bqskit.passes.rules.u12rz.U1ToRZPass`, which exists in no bqskit release (1.2.1) and in no
   branch of github.com/BQSKit/bqskit (main @ 9324d64, checked 2026-10-13). Without it neither
   `CliffordRZModel` nor `alg_err_workflow.py` can be imported. `stage1/u12rz_shim.py` registers an
   in-memory module whose pass maps U1(t) -> RZ(t) (global phase only). It only ever acts on U1 gates;
   the stage-1 inputs contain only CX/H/Rz, so it is never exercised. No site-packages file is edited.
2. **Script crash.** `alg_err_workflow.py` calls `DPFPass(success_threshold=error / part_circ.num_operations)`,
   but `DPFPass.__init__` at this commit accepts only `(cost, k)` -> `TypeError`. The runner substitutes a
   subclass that accepts the keyword and passes it to DPF through `PassData['algorithmic_error']`
   (the only channel `DPFPass.run` reads). Everything else in the script runs verbatim
   (`stage1/vendor/alg_err_workflow.py`, sha256 80b47c9f...cc2a2, identical to the file at 2e99ba6).
3. **Sockets.** `bqskit.compiler.Compiler` binds localhost TCP (PermissionError here). `SerialCompiler`
   (`stage1/run_bqskit_arms.py`) runs each task in-process on `serial_runtime.py`, deep-copying circuit and
   workflow per task (the real runtime pickles both). Parallelism is across jobs (6 processes).
