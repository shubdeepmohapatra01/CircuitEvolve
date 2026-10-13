# BQSKit-group benchmark circuits (logical, unmapped)

Source: https://github.com/mtweiden/qseed (M. Weiden, first author of arXiv:2504.15990 and 2409.00433),
commit eb9ccab7a0736ba9c8793899b155dd4c20c5ccb1, directory `qasm/`, `mapped-*` variants excluded.
Repo declares no license — treat as research-use copies; cite the source papers.

117 circuits, 13 families (add, grover, heisenberg, hhl, hubbard, mult, qae, qft, qml, qpe, shor, tfim, vqe).
Basis {U3, CX} except shor (cp/ccp/swap/ccx/h/u1/x/cx). Stats in MANIFEST.csv
(`nonclifford_angles` = rotation parameters not a multiple of pi/2; a proxy, not a T-count).

Coverage of published BQSKit experiments:
- arXiv:2504.15990 Table I / 2409.00433 Table 2 (QuickPartitioner 2q/3q blocks): 7 of 8 families present; QAOA (MQTBench) absent;
  instance sizes not published.
- arXiv:2409.00433 Table 3 (whole circuit): add_17, hhl_6, mult_16, qft_32, shor_16 present; QAE-50 and QPE-30 absent.

Re-fetch: `python fetch_suite.py`.
