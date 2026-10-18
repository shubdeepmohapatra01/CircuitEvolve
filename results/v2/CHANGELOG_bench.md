# v2 Benchmarks track - changelog (append-only; kept separate from results/CHANGELOG.md to avoid concurrent edits
# with the sibling v2 track - the parent should fold a one-line entry into results/CHANGELOG.md)

- 2026-10-14 - new `benchmarks/nam_arith/` (fetch_suite.py, normalize.py, COMMIT, PROVENANCE.md, SPLIT.md,
  MANIFEST.csv, split_v2.json; upstream/, logical/, cliffordt/, nam/, generated/): 34 Nam et al. 2018 / T-par circuits
  pinned at quartz@ce31db1c, njross/optimizer@8cd55d50, feynman@d2c382a2; cuccaro_4/8/16 generated; qseed
  shor_12/14/16 by reference. Split: 17 dev / 22 held-out / 1 large_optional (gf2^32_mult).
- 2026-10-14 - baselines (`experiments/v2_bench_*.py`): run1 (no QCEC, superseded), run2 (all but gf2^16/32;
  QCEC added, circuits saved), run3_large (gf2^16; gf2^32 produced no output; driver stopped at 01:57 after ~110 min, worker exited). Aggregates:
  baselines_new.csv / _detail.csv / _summary.md / baselines_consistency.json, published_arith.csv,
  rotations_gridsynth_run2_eps0.001.json. Finding: Nam et al. Heavy qcla_mod_7 (235 T) is not equivalent to its input.
- 2026-10-14 - `docs/v2/cards/` 11 technique cards + INDEX.md + CITATIONS.md; worked examples in
  cards_worked_examples.json (note: `temporary_and.uncompute_branches_phase_consistent` is serialized as [1.0, 1.0],
  i.e. True for both branches - numpy bools went through the float fallback of json.dump).
- No file under circuitevolve/, results/ (outside results/v2/), notebooks/ or benchmarks/bqskit_qseed/ was modified;
  the frozen verifier files were only imported.
