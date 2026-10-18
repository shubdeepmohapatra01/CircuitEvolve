# results/v2 — outputs of the two-tier v2 pipeline (append-only)

Code: `circuitevolve/v2/` (README there). Design: `docs/v2/DESIGN.md`. CLAUDE.md invariant 5 applies: add files and
rows, never edit an existing row; a corrected table is a new file (`..._v2.csv`) with a CHANGELOG entry.

## Layout

| path | written by | content |
|---|---|---|
| `reused/published_baselines.csv` | Scaffold (2026-10-14) | byte-identical copy of the project artifact `published_baselines.csv` (paper numbers, context only) |
| `baselines_new.csv` | Benchmarks track | NEW classical baselines (e.g. pyzx / TKET on the Nam et al. arithmetic suite); schema below |
| `tier1/`, `tier2/`, `heldout/` | later tracks | per-run records; every result row carries the verifier mode |

## Reused inputs (never recomputed; sha256 checked by `tests/v2/test_v2_scaffold.py`)

| source key | file | sha256 |
|---|---|---|
| `stage1_v2` | `results/bqskit_baselines/stage1/stage1_baselines_v2.csv` | `6a6897bd3bcd4a00fd0fef2bd919630f97710d20d087338d9388ecb21481c27b` |
| `reference_pipelines` | `results/bqskit_baselines/reference_pipelines.csv` | `33252f88e227268330f63f98fc6ecbcea00fbbacd642cf804cf1c6a39a8b6073` |
| `published` | `results/v2/reused/published_baselines.csv` | `6f44a3456110f0fa8a9af8fdada2a507b5b1817b717fdefb734288c673198aa9` |

Column choices are documented in `circuitevolve/v2/baselines.py`: stage 1 uses `t_count_canon`, valid arms only
(B0, B1, B2, B3m, B3g; B3 and B2ft exceed their eps by code accounting); reference pipelines are keyed by the old
per-rotation setting `eps_rz=1e-9` and never compared with a total-eps row; published rows are context only.

## `baselines_new.csv` schema (merge hook: `circuitevolve.v2.baselines.load_new`)

`circuit, source, arm, eps, t_count, qubits, notes`

- `eps` = TOTAL algorithmic error (BQSKit convention: gridsynth at eps_synth / N_Rz); exact Clifford+T rows (no
  synthesized rotations) still state the eps at which they are offered as a baseline.
- `source` = tool and version (e.g. `pyzx 0.10.7`); `arm` = short method label.
- a row whose `notes` starts with `INVALID` is loaded but never used as a bar.

## Reporting rule for every v2 result table

Each candidate row must carry `verify_mode` (`exact` | `approx` | `relaxed`), `certified` (True only for
exhaustive / dense-unitary checks) and `unitary_preserving`. Unitary-preserving results (`exact`, `approx`) and
relaxed results (extra ancillas, measurement + feed-forward) are reported in separate columns or tables.
